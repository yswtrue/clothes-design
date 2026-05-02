from typing import Any

from shared.redis import get_redis as _get_redis, close_redis as _close_redis

RedisType = Any


async def get_redis_client() -> RedisType:
    return _get_redis()


async def close_redis_client() -> None:
    await _close_redis()
