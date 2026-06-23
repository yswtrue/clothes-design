import json
from datetime import UTC, datetime
from typing import Any

from taskiq import TaskiqResult
from taskiq_redis.exceptions import ResultIsMissingError

from taskiq_app import broker
from worker.tasks import (
    analyze_task,
    ecommerce_poster_task,
    export_pattern_task,
    generate_task,
    mockup_task,
    model_preview_task,
    upscale_task,
    vectorize_task,
)

from .redis_client import get_redis_client
from .schemas import TaskStatus


class QueueError(Exception):
    pass


TASK_MAP = {
    "analyze": analyze_task,
    "generate": generate_task,
    "upscale": upscale_task,
    "vectorize": vectorize_task,
    "mockup": mockup_task,
    "model_preview": model_preview_task,
    "export_pattern": export_pattern_task,
    "ecommerce_poster": ecommerce_poster_task,
}


async def enqueue_task(task_type: str, user_id: int, data: dict[str, Any] | None = None) -> str:
    task_data = data or {}

    taskiq_task = TASK_MAP.get(task_type)
    if not taskiq_task:
        raise QueueError(f"Unknown task type: {task_type}")

    try:
        result = await taskiq_task.kiq(task_data)
        task_id = result.task_id

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
            }
            await client.hset(f"task:{task_id}", mapping=task_metadata)
            await client.expire(f"task:{task_id}", 86400)

        return task_id

    except Exception as exc:
        raise QueueError(f"Failed to enqueue task: {exc}") from exc


async def get_task_status(task_id: str) -> TaskStatus | None:
    client = await get_redis_client()
    if not client:
        return None

    try:
        metadata = await client.hgetall(f"task:{task_id}")

        if not metadata:
            return None

        data = {}
        if metadata.get("data"):
            data = json.loads(metadata["data"])

        result = None
        if metadata.get("result"):
            result = json.loads(metadata["result"])

        error = metadata.get("error") or None
        status = metadata.get("status", "pending")

        try:
            taskiq_result: TaskiqResult | None = await broker.result_backend.get_result(task_id)
            if taskiq_result is not None:
                if taskiq_result.is_err:
                    status = "failed"
                    error = str(taskiq_result.error) if taskiq_result.error else "Unknown error"
                else:
                    status = "completed"
                    result = taskiq_result.return_value
        except ResultIsMissingError:
            pass

        return TaskStatus(
            task_id=task_id,
            task_type=metadata["task_type"],
            user_id=int(metadata["user_id"]),
            status=status,
            created_at=datetime.fromisoformat(metadata["created_at"]),
            updated_at=datetime.fromisoformat(metadata["updated_at"]),
            data=data,
            result=result,
            error=error,
        )
    except Exception as exc:
        raise QueueError(f"Failed to get task status: {exc}") from exc


async def get_task_result(task_id: str) -> dict[str, Any] | None:
    status = await get_task_status(task_id)
    if not status or status.status != "completed":
        return None
    return status.result


async def update_task_status(
    task_id: str, status: str, result: dict[str, Any] | None = None, error: str | None = None
) -> None:
    client = await get_redis_client()
    if not client:
        return

    try:
        now = datetime.now(UTC).isoformat()

        updates: dict[str, Any] = {
            "status": status,
            "updated_at": now,
        }

        if result is not None:
            updates["result"] = json.dumps(result)

        if error is not None:
            updates["error"] = error

        await client.hset(f"task:{task_id}", mapping=updates)

    except Exception:
        pass


async def dequeue_task(timeout: int = 0) -> str | None:
    return None
