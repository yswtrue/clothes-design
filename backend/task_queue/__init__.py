"""Task queue module for asynchronous AI processing."""

from .redis_client import close_redis_client, get_redis_client
from .schemas import TaskPayload, TaskResult, TaskStatus
from .tasks import (
    QueueError,
    dequeue_task,
    enqueue_task,
    get_task_result,
    get_task_status,
    update_task_status,
)

__all__ = [
    "QueueError",
    "TaskPayload",
    "TaskResult",
    "TaskStatus",
    "close_redis_client",
    "dequeue_task",
    "enqueue_task",
    "get_redis_client",
    "get_task_result",
    "get_task_status",
    "update_task_status",
]
