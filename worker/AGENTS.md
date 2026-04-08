# WORKER WORKSPACE

**Generated:** 2026-04-05
**Workspace:** worker (Async Task Consumer)

## OVERVIEW
Redis-backed task worker consuming asynchronous jobs from the backend. Uses a registry-based handler pattern with built-in retry logic and graceful shutdown support.

## STRUCTURE
- `main.py`: Entry point; contains `Worker` loop, signal handling, and task orchestration.
- `handlers/`: Task-specific processing logic.
    - `base.py`: Defines `TaskHandler` ABC, `HandlerRegistry`, and `WorkerError` exception.
- `__init__.py`: Package initialization.

## CONVENTIONS
- **Handler Registration**: All tasks must implement `TaskHandler` and be registered via `worker.register_handler(type, class)`.
- **Async Processing**: Handlers must be `async` and use `asyncio.wait_for` for timeouts (default: 600s).
- **Validation**: Override `validate_input` in handlers to verify `task_data` before execution.
- **Graceful Shutdown**: Listen for `SIGTERM`/`SIGINT` to stop dequeuing and finish the current task.
- **Status Updates**: Worker automatically updates backend task status (`processing`, `completed`, `failed`).
- **Retry Strategy**: Exponential backoff (2^retry) for transient `QueueError` or `asyncio.TimeoutError`.

## ANTI-PATTERNS
- **NO Blocking I/O**: Never use synchronous `time.sleep` or blocking requests inside handlers.
- **NO Manual Dequeue**: Do not call `dequeue_task` directly outside the main `Worker.run` loop.
- **NO Silenced Exceptions**: Always raise `WorkerError` for expected failures; let the loop catch unexpected ones.
- **NO Hardcoded Timeouts**: Use `TASK_TIMEOUT` constant in `main.py` for job limits.

## COMMANDS
- `python -m worker.main` - Start the worker consumer process.
- `uv sync` - Ensure worker dependencies are isolated and up-to-date.

## NOTES
- **Retries**: Fixed at `MAX_RETRIES = 3`. Critical failures (unregistered handlers) fail immediately without retry.
- **Logging**: Configured at `INFO` level with timestamp, logger name, and level.
- **Backend Dependency**: Depends on `backend.task_queue` for Redis interaction and status reporting.
