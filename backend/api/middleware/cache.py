"""Simple in-memory cache decorator for FastAPI."""

import asyncio
import time
from functools import wraps
from typing import Any, Callable


_cache: dict[str, tuple[Any, float]] = {}


def cache(expire: int = 60):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__module__}.{func.__name__}:{str(args)}:{str(kwargs)}"

            if cache_key in _cache:
                value, timestamp = _cache[cache_key]
                if time.time() - timestamp < expire:
                    return value

            result = await func(*args, **kwargs)
            _cache[cache_key] = (result, time.time())

            return result

        return wrapper

    return decorator


async def clear_expired_cache():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired_keys = [k for k, (_, ts) in _cache.items() if now - ts > 300]
        for key in expired_keys:
            del _cache[key]
