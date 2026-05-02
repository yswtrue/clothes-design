from taskiq_redis import RedisAsyncResultBackend, ListQueueBroker

from config import get_settings

_settings = get_settings()

result_backend = RedisAsyncResultBackend(
    redis_url=_settings.redis.broker_url,
    keep_results=True,
    result_ex_time=3600,
)

broker = ListQueueBroker(
    url=_settings.redis.broker_url,
    queue_name="tasks",
).with_result_backend(result_backend)
