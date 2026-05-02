from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool

from config import get_settings

_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings().redis
        _pool = ConnectionPool.from_url(
            settings.connection_url,
            max_connections=settings.max_connections,
            decode_responses=True,
        )
    return _pool


def get_redis() -> Any:
    return aioredis.Redis(connection_pool=get_redis_pool())


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
