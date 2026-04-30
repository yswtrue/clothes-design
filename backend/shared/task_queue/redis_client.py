from typing import Any

from api.redis import get_redis, close_redis

RedisType = Any


async def get_redis_client() -> RedisType:
    return get_redis()


async def close_redis_client() -> None:
    await close_redis()
