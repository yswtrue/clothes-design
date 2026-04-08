import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

try:
    import redis.asyncio as redis
except Exception:
    redis = None

_redis_available = redis is not None


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_revoked_tokens: dict[str, int] = {}


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
    return _parse_duration(os.getenv("JWT_EXPIRY"), 900)


def _refresh_expiry_seconds() -> int:
    return _parse_duration(os.getenv("JWT_REFRESH_EXPIRY"), 604800)


def create_access_token(subject: str | int) -> str:
    return _create_token(subject, "access", _access_expiry_seconds())


def create_refresh_token(subject: str | int) -> str:
    return _create_token(subject, "refresh", _refresh_expiry_seconds())


def _create_token(subject: str | int, token_type: str, expires_seconds: int) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=expires_seconds)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def verify_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if expected_type and payload.get("type") != expected_type:
        raise ValueError("Invalid or expired token")
    if not payload.get("sub") or not payload.get("jti"):
        raise ValueError("Invalid or expired token")
    return payload


async def _get_redis_client():
    if not _redis_available:
        return None
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    if redis is None:
        return None
    return redis.from_url(redis_url, decode_responses=True)


async def revoke_token(jti: str, expires_at: int) -> None:
    if not jti:
        return
    now = int(datetime.now(UTC).timestamp())
    ttl = max(expires_at - now, 0)
    client = await _get_redis_client()
    if client:
        await client.setex(f"revoked:{jti}", ttl, "1")
        return
    _revoked_tokens[jti] = expires_at


async def is_token_revoked(jti: str) -> bool:
    if not jti:
        return True
    now = int(datetime.now(UTC).timestamp())
    expired = [key for key, exp in _revoked_tokens.items() if exp <= now]
    for key in expired:
        _revoked_tokens.pop(key, None)
    client = await _get_redis_client()
    if client:
        return bool(await client.exists(f"revoked:{jti}"))
    return jti in _revoked_tokens
