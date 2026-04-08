"""Task queue operations."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import redis.asyncio as redis

from .redis_client import get_redis_client
from .schemas import TaskStatus


class QueueError(Exception):
    """Task queue operation error."""

    pass


async def enqueue_task(task_type: str, user_id: int, data: dict[str, Any] | None = None) -> str:
    """Enqueue a new task.

    Args:
        task_type: Task type identifier (e.g., 'generate_pattern', 'upscale_image')
        user_id: User ID submitting the task
        data: Task-specific parameters

    Returns:
        Task ID (UUID)

    Raises:
        QueueError: If Redis connection fails or task enqueue fails
    """
    client = await get_redis_client()
    if not client:
        raise QueueError("Redis not available")

    task_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    task_data = data or {}

    task_metadata = {
        "task_type": task_type,
        "user_id": str(user_id),
        "status": "pending",
        "data": json.dumps(task_data),
        "result": "",
        "error": "",
        "created_at": now,
        "updated_at": now,
    }

    try:
        # Store task metadata in hash with TTL
        await client.hset(f"task:{task_id}", mapping=task_metadata)  # type: ignore[misc]
        await client.expire(f"task:{task_id}", 86400)  # type: ignore[misc]

        # Add task ID to queue (FIFO)
        await client.rpush("task:queue", task_id)  # type: ignore[misc]

        return task_id
    except redis.RedisError as exc:
        raise QueueError(f"Failed to enqueue task: {exc}") from exc


async def get_task_status(task_id: str) -> TaskStatus | None:
    """Get task status and metadata.

    Args:
        task_id: Task ID to retrieve

    Returns:
        TaskStatus if found, None otherwise

    Raises:
        QueueError: If Redis connection fails
    """
    client = await get_redis_client()
    if not client:
        raise QueueError("Redis not available")

    try:
        metadata = await client.hgetall(f"task:{task_id}")  # type: ignore[misc]

        if not metadata:
            return None

        data = {}
        if metadata.get("data"):
            data = json.loads(metadata["data"])

        result = None
        if metadata.get("result"):
            result = json.loads(metadata["result"])

        error = metadata.get("error") or None

        return TaskStatus(
            task_id=task_id,
            task_type=metadata["task_type"],
            user_id=int(metadata["user_id"]),
            status=metadata["status"],  # type: ignore[arg-type]
            created_at=datetime.fromisoformat(metadata["created_at"]),
            updated_at=datetime.fromisoformat(metadata["updated_at"]),
            data=data,
            result=result,
            error=error,
        )
    except redis.RedisError as exc:
        raise QueueError(f"Failed to get task status: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise QueueError(f"Failed to parse task metadata: {exc}") from exc


async def get_task_result(task_id: str) -> dict[str, Any] | None:
    """Get task result data if completed.

    Args:
        task_id: Task ID to retrieve

    Returns:
        Result dict if task completed, None otherwise

    Raises:
        QueueError: If Redis connection fails
    """
    status = await get_task_status(task_id)
    if not status or status.status != "completed":
        return None
    return status.result


async def update_task_status(
    task_id: str, status: str, result: dict[str, Any] | None = None, error: str | None = None
) -> None:
    """Update task status (used by worker).

    Args:
        task_id: Task ID to update
        status: New status (processing, completed, failed)
        result: Result data if completed
        error: Error message if failed

    Raises:
        QueueError: If Redis connection fails or task not found
    """
    client = await get_redis_client()
    if not client:
        raise QueueError("Redis not available")

    try:
        # Check if task exists
        exists = await client.exists(f"task:{task_id}")  # type: ignore[misc]
        if not exists:
            raise QueueError(f"Task {task_id} not found")

        now = datetime.now(UTC).isoformat()

        updates = {
            "status": status,
            "updated_at": now,
        }

        if result is not None:
            updates["result"] = json.dumps(result)

        if error is not None:
            updates["error"] = error

        await client.hset(f"task:{task_id}", mapping=updates)  # type: ignore[misc]

    except redis.RedisError as exc:
        raise QueueError(f"Failed to update task status: {exc}") from exc


async def dequeue_task(timeout: int = 0) -> str | None:
    """Dequeue a task from the queue (blocking).

    Args:
        timeout: Timeout in seconds (0 = non-blocking)

    Returns:
        Task ID if available, None if timeout

    Raises:
        QueueError: If Redis connection fails
    """
    client = await get_redis_client()
    if not client:
        raise QueueError("Redis not available")

    try:
        result = await client.blpop("task:queue", timeout=timeout)  # type: ignore[misc]
        if result:
            return result[1]  # blpop returns (key, value)
        return None
    except redis.RedisError as exc:
        raise QueueError(f"Failed to dequeue task: {exc}") from exc
