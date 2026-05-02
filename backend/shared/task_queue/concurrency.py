from shared.redis import get_redis

EXPORT_CONCURRENCY_KEY = "export:active_count"
EXPORT_MAX_CONCURRENT = 3
EXPORT_TTL_SECONDS = 600


async def acquire_export_slot() -> bool:
    redis = get_redis()
    current = await redis.incr(EXPORT_CONCURRENCY_KEY)
    if current == 1:
        await redis.expire(EXPORT_CONCURRENCY_KEY, EXPORT_TTL_SECONDS)
    if current > EXPORT_MAX_CONCURRENT:
        await redis.decr(EXPORT_CONCURRENCY_KEY)
        return False
    return True


async def release_export_slot() -> None:
    redis = get_redis()
    current = await redis.decr(EXPORT_CONCURRENCY_KEY)
    if current <= 0:
        await redis.delete(EXPORT_CONCURRENCY_KEY)


async def get_export_slot_count() -> int:
    redis = get_redis()
    count = await redis.get(EXPORT_CONCURRENCY_KEY)
    return int(count) if count else 0
