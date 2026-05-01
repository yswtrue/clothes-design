import logging
import os
import re
from calendar import timegm
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import delete, select

from api.db.base import AsyncSessionLocal
from api.redis import get_redis

_logger = logging.getLogger(__name__)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_revoked_tokens: dict[str, int] = {}

LOGIN_SESSION_PREFIX = "login_session:"
REDIS_CACHE_TTL = 3600


def _utc_timestamp() -> int:
    return timegm(datetime.utcnow().utctimetuple())


def get_password_hash(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def _parse_duration(value: str | None, default_seconds: int) -> int:
    if not value:
        return default_seconds
    match = re.fullmatch(r"(\d+)([smhd])", value.strip())
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        return amount * multipliers[unit]
    if value.isdigit():
        return int(value)
    raise ValueError("Invalid duration format")


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise ValueError("JWT_SECRET is not set")
    return secret


def _access_expiry_seconds() -> int:
    return _parse_duration(os.getenv("JWT_EXPIRY"), 604800)


def _refresh_expiry_seconds() -> int:
    return _parse_duration(os.getenv("JWT_REFRESH_EXPIRY"), 604800)


async def create_login_session(user_id: int, token_type: str, ttl_seconds: int) -> str:
    from api.db.models import LoginSession
    
    login_token = str(uuid4())
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    
    async with AsyncSessionLocal() as session:
        login_session = LoginSession(
            user_id=user_id,
            login_token=login_token,
            token_type=token_type,
            expires_at=expires_at,
        )
        session.add(login_session)
        await session.commit()
    
    try:
        client = get_redis()
        await client.setex(f"{LOGIN_SESSION_PREFIX}{login_token}", REDIS_CACHE_TTL, str(user_id))
    except Exception:
        pass
    
    return login_token


async def get_user_id_from_login_token(login_token: str) -> int | None:
    from api.db.models import LoginSession
    
    try:
        client = get_redis()
        user_id_str = await client.get(f"{LOGIN_SESSION_PREFIX}{login_token}")
        if user_id_str:
            return int(user_id_str)
    except Exception:
        pass
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LoginSession).where(
                LoginSession.login_token == login_token,
                LoginSession.expires_at > datetime.utcnow(),
            )
        )
        login_session = result.scalar_one_or_none()
        if login_session:
            try:
                client = get_redis()
                await client.setex(
                    f"{LOGIN_SESSION_PREFIX}{login_token}",
                    REDIS_CACHE_TTL,
                    str(login_session.user_id),
                )
            except Exception:
                pass
            return login_session.user_id
    
    return None


async def revoke_login_session(login_token: str) -> None:
    from api.db.models import LoginSession
    
    try:
        client = get_redis()
        await client.delete(f"{LOGIN_SESSION_PREFIX}{login_token}")
    except Exception:
        pass
    
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(LoginSession).where(LoginSession.login_token == login_token)
        )
        await session.commit()


async def create_access_token(user_id: int) -> str:
    ttl = _access_expiry_seconds()
    login_token = await create_login_session(user_id, "access", ttl)
    return _create_token(login_token, "access", ttl)


async def create_refresh_token(user_id: int) -> str:
    ttl = _refresh_expiry_seconds()
    login_token = await create_login_session(user_id, "refresh", ttl)
    return _create_token(login_token, "refresh", ttl)


def _create_token(subject: str | int, token_type: str, expires_seconds: int) -> str:
    now = _utc_timestamp()
    expires_at = now + expires_seconds
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def verify_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
    except JWTError as exc:
        _logger.debug(f"JWT decode failed: {type(exc).__name__}")
        raise ValueError("Invalid or expired token") from exc
    if expected_type and payload.get("type") != expected_type:
        raise ValueError("Invalid or expired token")
    if not payload.get("sub") or not payload.get("jti"):
        raise ValueError("Invalid or expired token")
    return payload


async def revoke_token(jti: str, expires_at: int) -> None:
    if not jti:
        return
    now = _utc_timestamp()
    ttl = max(expires_at - now, 0)
    try:
        client = get_redis()
        await client.setex(f"revoked:{jti}", ttl, "1")
    except Exception:
        _revoked_tokens[jti] = expires_at


async def is_token_revoked(jti: str) -> bool:
    if not jti:
        return True
    now = _utc_timestamp()
    expired = [key for key, exp in _revoked_tokens.items() if exp <= now]
    for key in expired:
        _revoked_tokens.pop(key, None)
    try:
        client = get_redis()
        return bool(await client.exists(f"revoked:{jti}"))
    except Exception:
        return jti in _revoked_tokens
