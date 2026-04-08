"""Tests for task queue operations."""

import json
from datetime import datetime

import pytest
from fakeredis import FakeAsyncRedis

from task_queue import (
    QueueError,
    dequeue_task,
    enqueue_task,
    get_task_result,
    get_task_status,
    update_task_status,
)


@pytest.fixture
async def redis_client():
    """Create a fake Redis client for testing."""
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def mock_redis(redis_client, monkeypatch):
    """Mock get_redis_client to return fake Redis."""

    async def mock_get_redis():
        return redis_client

    monkeypatch.setattr("task_queue.redis_client.get_redis_client", mock_get_redis)
    monkeypatch.setattr("task_queue.tasks.get_redis_client", mock_get_redis)
    return redis_client


@pytest.mark.asyncio
async def test_enqueue_task_success(mock_redis):
    """Test successful task enqueue."""
    task_id = await enqueue_task("generate_pattern", 123, {"material_id": 456})

    assert task_id is not None
    assert isinstance(task_id, str)
    assert len(task_id) > 0

    # Verify task metadata in Redis
    metadata = await mock_redis.hgetall(f"task:{task_id}")
    assert metadata["task_type"] == "generate_pattern"
    assert metadata["user_id"] == "123"
    assert metadata["status"] == "pending"
    assert metadata["data"] == json.dumps({"material_id": 456})

    # Verify task is in queue
    queue_len = await mock_redis.llen("task:queue")
    assert queue_len == 1


@pytest.mark.asyncio
async def test_enqueue_task_no_data(mock_redis):
    """Test enqueue task with no data."""
    task_id = await enqueue_task("simple_task", 456)

    metadata = await mock_redis.hgetall(f"task:{task_id}")
    assert metadata["data"] == "{}"


@pytest.mark.asyncio
async def test_get_task_status_pending(mock_redis):
    """Test getting status of pending task."""
    task_id = await enqueue_task("test_task", 789, {"key": "value"})

    status = await get_task_status(task_id)

    assert status is not None
    assert status.task_id == task_id
    assert status.task_type == "test_task"
    assert status.user_id == 789
    assert status.status == "pending"
    assert status.result is None
    assert status.error is None


@pytest.mark.asyncio
async def test_get_task_status_not_found(mock_redis):
    """Test getting status of non-existent task."""
    status = await get_task_status("nonexistent-task-id")
    assert status is None


@pytest.mark.asyncio
async def test_update_task_status_processing(mock_redis):
    """Test updating task status to processing."""
    task_id = await enqueue_task("test_task", 123)

    await update_task_status(task_id, "processing")

    status = await get_task_status(task_id)
    assert status.status == "processing"


@pytest.mark.asyncio
async def test_update_task_status_completed(mock_redis):
    """Test updating task status to completed with result."""
    task_id = await enqueue_task("test_task", 123)

    result_data = {"output_url": "s3://bucket/file.png", "status": "success"}
    await update_task_status(task_id, "completed", result=result_data)

    status = await get_task_status(task_id)
    assert status.status == "completed"
    assert status.result == result_data
    assert status.error is None


@pytest.mark.asyncio
async def test_update_task_status_failed(mock_redis):
    """Test updating task status to failed with error."""
    task_id = await enqueue_task("test_task", 123)

    error_msg = "Image processing failed: invalid format"
    await update_task_status(task_id, "failed", error=error_msg)

    status = await get_task_status(task_id)
    assert status.status == "failed"
    assert status.error == error_msg
    assert status.result is None


@pytest.mark.asyncio
async def test_update_task_status_not_found(mock_redis):
    """Test updating non-existent task."""
    with pytest.raises(QueueError, match="not found"):
        await update_task_status("nonexistent-task-id", "processing")


@pytest.mark.asyncio
async def test_get_task_result_completed(mock_redis):
    """Test getting result of completed task."""
    task_id = await enqueue_task("test_task", 123)

    result_data = {"url": "s3://bucket/result.png"}
    await update_task_status(task_id, "completed", result=result_data)

    result = await get_task_result(task_id)
    assert result == result_data


@pytest.mark.asyncio
async def test_get_task_result_pending(mock_redis):
    """Test getting result of pending task returns None."""
    task_id = await enqueue_task("test_task", 123)

    result = await get_task_result(task_id)
    assert result is None


@pytest.mark.asyncio
async def test_get_task_result_not_found(mock_redis):
    """Test getting result of non-existent task returns None."""
    result = await get_task_result("nonexistent-task-id")
    assert result is None


@pytest.mark.asyncio
async def test_dequeue_task_non_blocking(mock_redis):
    """Test non-blocking dequeue."""
    task_id = await enqueue_task("test_task", 123)

    dequeued_id = await dequeue_task(timeout=0)

    assert dequeued_id == task_id
    queue_len = await mock_redis.llen("task:queue")
    assert queue_len == 0


@pytest.mark.asyncio
async def test_dequeue_task_empty_queue(mock_redis):
    """Test dequeue from empty queue with non-blocking timeout."""
    dequeued_id = await dequeue_task(timeout=1)
    assert dequeued_id is None


@pytest.mark.asyncio
async def test_dequeue_task_fifo_order(mock_redis):
    """Test FIFO order of dequeuing."""
    task1 = await enqueue_task("task1", 123)
    task2 = await enqueue_task("task2", 123)
    task3 = await enqueue_task("task3", 123)

    # Dequeue in FIFO order (first in, first out)
    assert await dequeue_task(timeout=0) == task1
    assert await dequeue_task(timeout=0) == task2
    assert await dequeue_task(timeout=0) == task3


@pytest.mark.asyncio
async def test_task_ttl_expiration(mock_redis):
    """Test task metadata expires after TTL."""
    task_id = await enqueue_task("test_task", 123)

    # Check TTL is set
    ttl = await mock_redis.ttl(f"task:{task_id}")
    assert ttl > 0
    assert ttl <= 86400  # Should be <= 24 hours

    # Simulate TTL expiration
    await mock_redis.delete(f"task:{task_id}")

    status = await get_task_status(task_id)
    assert status is None


@pytest.mark.asyncio
async def test_timestamps_are_valid_iso(mock_redis):
    """Test that timestamps are valid ISO format."""
    task_id = await enqueue_task("test_task", 123)

    status = await get_task_status(task_id)

    # Should not raise ValueError
    created = datetime.fromisoformat(status.created_at.isoformat())
    updated = datetime.fromisoformat(status.updated_at.isoformat())

    assert created is not None
    assert updated is not None


@pytest.mark.asyncio
async def test_multiple_tasks_concurrent(mock_redis):
    """Test multiple tasks can exist concurrently."""
    task_ids = []
    for i in range(5):
        task_id = await enqueue_task(f"task_{i}", i, {"index": i})
        task_ids.append(task_id)

    # Verify all tasks exist
    for i, task_id in enumerate(task_ids):
        status = await get_task_status(task_id)
        assert status is not None
        assert status.task_type == f"task_{i}"


@pytest.mark.asyncio
async def test_json_serialization_complex_data(mock_redis):
    """Test complex JSON data is properly serialized."""
    complex_data = {
        "nested": {
            "array": [1, 2, 3],
            "boolean": True,
            "null_value": None,
            "float": 3.14,
        },
        "string": "test",
    }

    task_id = await enqueue_task("complex_task", 123, complex_data)

    status = await get_task_status(task_id)
    assert status.result is None  # Pending, no result

    await update_task_status(task_id, "completed", result=complex_data)

    status = await get_task_status(task_id)
    assert status.result == complex_data
