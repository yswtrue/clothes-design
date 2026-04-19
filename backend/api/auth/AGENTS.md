# BACKEND AUTH LAYER

**Generated:** 2026-04-05

## OVERVIEW
JWT-based authentication with stateful revocation and password security. Uses access and refresh token pairs with Redis-backed blacklisting.

## STRUCTURE
- `security.py`: Core logic for JWT issuance, validation, password hashing, and token revocation.
- `dependencies.py`: FastAPI security dependencies for user session retrieval from tokens.
- `schemas.py`: Pydantic models for login, registration, and token responses.

## CONVENTIONS
- **JWT Claims**: Always include `sub` (user_id), `type` (access/refresh), `iat`, `exp`, and `jti` (UUID).
- **Algorithms**: HS256 for all token signing. Requires `JWT_SECRET` environment variable.
- **Expiry Logic**: Managed via `JWT_EXPIRY` (default 15m) and `JWT_REFRESH_EXPIRY` (default 7d). Supports shorthand formats (e.g., "15m", "7d").
- **Stateful Revocation**: Every token carries a `jti`. Revoked tokens are stored in Redis (key: `revoked:{jti}`) until expiry.
- **In-Memory Fallback**: Local dictionary `_revoked_tokens` used if `REDIS_URL` is missing or Redis is unavailable.
- **Dependency Pattern**: Use `Depends(get_current_user)` for routes requiring authentication. Extracts `sub` and queries `User` model.
- **Async Redis**: Uses `redis.asyncio` for non-blocking revocation checks.

## ANTI-PATTERNS
- **NO Plaintext**: Never log or store raw passwords. Use `verify_password` for comparisons.
- **NO Sync Redis**: Never use synchronous Redis clients; all token checks must be `await`.
- **NO Generic JWT Errors**: Catch `jose.JWTError` and raise uniform `ValueError` or 401 `HTTPException`.
- **NO Token Overlap**: Don't accept refresh tokens in access-only routes. Check `type` claim explicitly.
- **NO Hardcoded Expiry**: Never hardcode durations in logic; use `_parse_duration` helpers.

## NOTES
- **Password Strength**: Validation resides in `schemas.py` or `security.py` utilities.
- **Refresh Flow**: Refresh tokens only allow issuing new access tokens; they cannot access protected resources directly.
- **Subject Persistence**: Subjects (`sub`) are cast to strings in tokens but coerced back to integers for DB lookups.
