"""Redis client management for task queue."""

import os
from typing import Any

try:
    import redis.asyncio as redis
except Exception:
    redis = None  # type: ignore[assignment]

RedisType = Any

_redis_available = redis is not None
_redis_client: RedisType | None = None


async def get_redis_client() -> RedisType | None:
    """Get or create Redis client for task queue.

    Returns None if REDIS_QUEUE_URL is not configured.
    Falls back to REDIS_URL if REDIS_QUEUE_URL is not set.
    """
    global _redis_client

    redis_url = os.getenv("REDIS_QUEUE_URL") or os.getenv("REDIS_URL")

    if not redis_url or not _redis_available:
        return None

    if _redis_client is None:
        _redis_client = redis.from_url(redis_url, decode_responses=True)

    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
