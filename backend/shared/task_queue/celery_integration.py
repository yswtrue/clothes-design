"""Celery-based task queue integration.

This module provides a bridge between the old Redis-based task queue API
and the new Celery task system.
"""

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


# Import Celery tasks
try:
    from worker.celery_tasks import (
        analyze_task,
        compose_tif_task,
        export_pattern_task,
        generate_task,
        generate_variants_task,
        mockup_task,
        upscale_task,
        vectorize_task,
    )

    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


# Map task types to Celery tasks
TASK_MAP = {
    "analyze": analyze_task,
    "generate": generate_task,
    "generate_variants": generate_variants_task,
    "upscale": upscale_task,
    "vectorize": vectorize_task,
    "mockup": mockup_task,
    "export_pattern": export_pattern_task,
    "compose_tif": compose_tif_task,
}


async def enqueue_task(task_type: str, user_id: int, data: dict[str, Any] | None = None) -> str:
    """Enqueue a new task using Celery.

    Args:
        task_type: Task type identifier (e.g., 'analyze', 'generate')
        user_id: User ID submitting the task
        data: Task-specific parameters

    Returns:
        Task ID (Celery task ID)

    Raises:
        QueueError: If Celery is not available or task submission fails
    """
    if not CELERY_AVAILABLE:
        raise QueueError("Celery not available")

    task_data = data or {}

    # Get Celery task function
    celery_task = TASK_MAP.get(task_type)
    if not celery_task:
        raise QueueError(f"Unknown task type: {task_type}")

    try:
        # Submit task to Celery
        result = celery_task.apply_async(args=[task_data])
        task_id = result.id

        # Store task metadata in Redis for compatibility
        client = await get_redis_client()
        if client:
            now = datetime.now(UTC).isoformat()
            task_metadata = {
                "task_type": task_type,
                "user_id": str(user_id),
                "status": "pending",
                "data": json.dumps(task_data),
                "result": "",
                "error": "",
                "created_at": now,
                "updated_at": now,
                "celery_task_id": task_id,
            }
            await client.hset(f"task:{task_id}", mapping=task_metadata)  # type: ignore[misc]
            await client.expire(f"task:{task_id}", 86400)  # type: ignore[misc]

        return task_id

    except Exception as exc:
        raise QueueError(f"Failed to enqueue task: {exc}") from exc


async def get_task_status(task_id: str) -> TaskStatus | None:
    """Get task status from Celery.

    Args:
        task_id: Celery task ID

    Returns:
        TaskStatus if found, None otherwise

    Raises:
        QueueError: If status cannot be retrieved
    """
    if not CELERY_AVAILABLE:
        raise QueueError("Celery not available")

    # First try to get from Redis metadata
    client = await get_redis_client()
    if client:
        try:
            metadata = await client.hgetall(f"task:{task_id}")  # type: ignore[misc]

            if metadata:
                data = {}
                if metadata.get("data"):
                    data = json.loads(metadata["data"])

                result = None
                if metadata.get("result"):
                    result = json.loads(metadata["result"])

                error = metadata.get("error") or None

                # Get actual status from Celery
                from celery.result import AsyncResult

                celery_result = AsyncResult(task_id)
                celery_status = celery_result.state.lower()

                # Map Celery states to our status
                status_map = {
                    "pending": "pending",
                    "started": "processing",
                    "success": "completed",
                    "failure": "failed",
                    "retry": "processing",
                    "revoked": "failed",
                }
                status = status_map.get(celery_status, metadata["status"])

                # Update result if completed
                if celery_status == "success" and celery_result.result:
                    result = celery_result.result

                # Update error if failed
                if celery_status == "failure" and celery_result.info:
                    error = str(celery_result.info)

                return TaskStatus(
                    task_id=task_id,
                    task_type=metadata["task_type"],
                    user_id=int(metadata["user_id"]),
                    status=status,  # type: ignore[arg-type]
                    created_at=datetime.fromisoformat(metadata["created_at"]),
                    updated_at=datetime.fromisoformat(metadata["updated_at"]),
                    data=data,
                    result=result,
                    error=error,
                )
        except Exception as exc:
            raise QueueError(f"Failed to get task status: {exc}") from exc

    return None


async def get_task_result(task_id: str) -> dict[str, Any] | None:
    """Get task result data if completed.

    Args:
        task_id: Task ID to retrieve

    Returns:
        Result dict if task completed, None otherwise

    Raises:
        QueueError: If result cannot be retrieved
    """
    status = await get_task_status(task_id)
    if not status or status.status != "completed":
        return None
    return status.result


async def update_task_status(
    task_id: str, status: str, result: dict[str, Any] | None = None, error: str | None = None
) -> None:
    """Update task status in Redis (for backward compatibility).

    Note: With Celery, status is managed by Celery itself.
    This function is kept for compatibility but does minimal work.

    Args:
        task_id: Task ID to update
        status: New status
        result: Result data if completed
        error: Error message if failed
    """
    client = await get_redis_client()
    if not client:
        return

    try:
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

    except Exception:
        # Silently fail - Celery manages its own state
        pass


async def dequeue_task(timeout: int = 0) -> str | None:
    """Deprecated: Celery workers pull tasks automatically.

    This function is kept for backward compatibility but returns None.
    """
    return None
