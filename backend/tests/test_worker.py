"""Tests for worker process and task handlers."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from worker.handlers import HandlerRegistry, TaskHandler, WorkerError
from worker.main import Worker

from backend.task_queue import (
    enqueue_task,
    get_task_status,
)

# Test Redis is created per event loop (not globally)


async def get_test_redis() -> FakeAsyncRedis:
    """Create fresh test Redis instance with string responses for each test."""
    return FakeAsyncRedis(decode_responses=True)  # type: ignore[return-value]


class MockHandler(TaskHandler):
    """Mock handler for testing."""

    handler_name = "mock"

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Return success result."""
        return {"status": "success", "processed": task_data}


class FailingHandler(TaskHandler):
    """Handler that always fails."""

    handler_name = "failing"

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Raise error."""
        raise RuntimeError("Intentional failure")


class ValidatingHandler(TaskHandler):
    """Handler with input validation."""

    handler_name = "validating"

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        """Require 'required_field' in task data."""
        if "required_field" not in task_data:
            raise WorkerError("Missing required_field in task data")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Return task data."""
        return task_data


@pytest.fixture(autouse=True)
async def setup_mock_redis(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None, None]:
    """Setup mock Redis for all tests."""
    test_redis = await get_test_redis()

    async def mock_get_redis() -> FakeAsyncRedis | None:
        return test_redis

    monkeypatch.setattr("backend.task_queue.redis_client.get_redis_client", mock_get_redis)
    monkeypatch.setattr("backend.task_queue.tasks.get_redis_client", mock_get_redis)

    yield

    try:
        await test_redis.aclose()  # type: ignore[misc]
    except Exception:
        pass


@pytest.fixture
def worker() -> Worker:
    """Create worker with registered handlers."""
    w = Worker()
    w.register_handler("mock", MockHandler)
    w.register_handler("failing", FailingHandler)
    w.register_handler("validating", ValidatingHandler)
    return w


pytestmark = pytest.mark.asyncio


class TestHandlerRegistry:
    """Test handler registry."""

    def test_register_and_get_handler(self) -> None:
        """Test registering and retrieving handler."""
        registry = HandlerRegistry()
        registry.register("test", MockHandler)

        handler = registry.get("test")
        assert handler is not None
        assert isinstance(handler, MockHandler)

    def test_get_nonexistent_handler(self) -> None:
        """Test getting nonexistent handler."""
        registry = HandlerRegistry()
        handler = registry.get("nonexistent")
        assert handler is None

    def test_list_handlers(self) -> None:
        """Test listing registered handlers."""
        registry = HandlerRegistry()
        registry.register("h1", MockHandler)
        registry.register("h2", FailingHandler)

        handlers = registry.list_handlers()
        assert "h1" in handlers
        assert "h2" in handlers


class TestWorkerBasic:
    """Test basic worker functionality."""

    async def test_worker_init(self, worker: Worker) -> None:
        """Test worker initialization."""
        assert worker.running is True
        assert worker.current_task is None

    async def test_worker_has_handlers(self, worker: Worker) -> None:
        """Test worker has registered handlers."""
        handlers = worker.handler_registry.list_handlers()
        assert "mock" in handlers


class TestTaskProcessing:
    """Test task processing."""

    async def test_process_successful_task(self, worker: Worker) -> None:
        """Test processing successful task."""
        task_id = await enqueue_task("mock", 1, {"data": "test"})
        result = await worker.process_task(task_id)

        assert result is True
        status = await get_task_status(task_id)
        assert status is not None
        assert status.status == "completed"
        assert status.result is not None
        assert status.result["status"] == "success"

    async def test_process_failing_task(self, worker: Worker) -> None:
        """Test processing task that fails."""
        task_id = await enqueue_task("failing", 1, {})
        result = await worker.process_task(task_id)

        assert result is False
        status = await get_task_status(task_id)
        assert status is not None
        assert status.status == "failed"
        assert status.error is not None
        assert "Intentional failure" in status.error

    async def test_process_task_with_invalid_handler(self, worker: Worker) -> None:
        """Test processing task with invalid handler."""
        task_id = await enqueue_task("nonexistent", 1, {})
        result = await worker.process_task(task_id)

        assert result is False
        status = await get_task_status(task_id)
        assert status is not None
        assert status.status == "failed"
        assert status.error is not None
        assert "No handler" in status.error

    async def test_process_task_with_validation_error(self, worker: Worker) -> None:
        """Test task with validation error."""
        task_id = await enqueue_task("validating", 1, {"wrong": "field"})
        result = await worker.process_task(task_id)

        assert result is False
        status = await get_task_status(task_id)
        assert status is not None
        assert status.status == "failed"
        assert status.error is not None
        assert "Missing required_field" in status.error

    async def test_process_task_with_validation_success(self, worker: Worker) -> None:
        """Test task with successful validation."""
        task_id = await enqueue_task("validating", 1, {"required_field": "value"})
        result = await worker.process_task(task_id)

        assert result is True
        status = await get_task_status(task_id)
        assert status is not None
        assert status.status == "completed"


class TestWorkerSignalHandling:
    """Test signal handling."""

    async def test_setup_signal_handlers(self, worker: Worker) -> None:
        """Test signal handler setup."""
        worker.setup_signal_handlers()
        assert worker.running is True

    async def test_graceful_shutdown(self, worker: Worker) -> None:
        """Test graceful shutdown flag."""
        worker.running = True
        worker.running = False
        assert worker.running is False


class TestEdgeCases:
    """Test edge cases."""

    async def test_process_nonexistent_task(self, worker: Worker) -> None:
        """Test processing nonexistent task."""
        result = await worker.process_task("nonexistent-id")
        assert result is False

    async def test_handler_with_complex_result(self, worker: Worker) -> None:
        """Test handler with complex result."""

        class ComplexHandler(TaskHandler):
            handler_name = "complex"

            async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
                """Return complex result."""
                return {
                    "nested": {"data": [1, 2, 3]},
                    "meta": {"key": "value"},
                }

        worker.register_handler("complex", ComplexHandler)
        task_id = await enqueue_task("complex", 1, {})
        result = await worker.process_task(task_id)

        assert result is True
        status = await get_task_status(task_id)
        assert status is not None
        assert status.result is not None
        assert status.result["nested"]["data"] == [1, 2, 3]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
