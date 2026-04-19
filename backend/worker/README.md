# Clothes Design Worker (Celery)

The asynchronous task processing engine for the Clothes Design platform. This service uses Celery to consume background jobs from Redis and execute long-running AI operations.

## 🚀 Features

- **Celery Task Queue**: Industry-standard distributed task queue with powerful scheduling and monitoring.
- **Robust Retry Logic**: Built-in exponential backoff for transient failures and job timeouts.
- **Graceful Shutdown**: Properly finishes current tasks before shutting down on SIGTERM/SIGINT.
- **Task Routing**: Different queues for different task types (analyze, generate, upscale, etc.).
- **Result Backend**: Task results stored in Redis for retrieval.
- **Async Processing**: High-concurrency support using Python's `asyncio` wrapped in Celery tasks.

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.13 |
| **Task Queue** | Celery 5.3+ |
| **Broker** | Redis |
| **I/O** | asyncio (wrapped in Celery tasks) |
| **Backend Integration** | Shared `backend.task_queue` + `backend.celery_app` |

## 🏗 Directory Structure

```text
worker/
├── handlers/         # Task-specific logic (async handlers)
│   ├── base.py       # Handler ABC and registry
│   ├── analyze.py    # AI design analysis
│   ├── generate.py   # Stability AI / OpenAI generation
│   ├── upscale.py    # Real-ESRGAN / AI upscaling
│   ├── vectorize.py  # SVG tracing
│   └── mockup.py     # Garment preview generation
├── celery_tasks.py   # Celery task wrappers
└── main.py           # [DEPRECATED] Old worker entry point
```

## ⚡ Quick Start

### 1. Prerequisites

Ensure you have a running Redis instance. If using the project's `devenv`, enter the shell.

```bash
devenv shell
```

### 2. Configure Environment Variables

The worker uses the same `.env` as the backend. Ensure `REDIS_QUEUE_URL` (or `REDIS_URL`) and AI API keys are configured.

```bash
cp .env.example .env
```

### 3. Run the Worker

**Option 1: Using Python module (推荐):**
```bash
cd backend
python -m worker
```

**Option 2: Using Celery directly:**
```bash
cd backend
celery -A celery_app worker --loglevel=info
```

**Option 3: With specific queue:**
```bash
cd backend
celery -A celery_app worker --loglevel=info --queues=generate,upscale
```

**Option 4: With Flower monitoring:**
```bash
cd backend
celery -A celery_app worker --loglevel=info &
celery -A celery_app flower
```
Access Flower UI at http://localhost:5555

## 🔄 Task Lifecycle

1. **Enqueue**: API submits task to Celery via `celery_task.apply_async()`.
2. **Routing**: Celery routes task to appropriate queue based on task type.
3. **Pickup**: Worker pulls task from queue (managed by Celery).
4. **Validate**: The corresponding handler validates the `task_data`.
5. **Processing**: Handler executes the AI logic (with configurable timeout).
6. **Completion**: Celery stores result in Redis backend.
7. **Error Handling**: On failure, Celery retries the task up to 3 times with exponential backoff.

## 🛠 Adding New Tasks

1. Create a new handler class in `worker/handlers/` inheriting from `TaskHandler`.
2. Implement the `handle()` and `validate_input()` async methods.
3. Add a Celery task wrapper in `worker/celery_tasks.py`:

```python
@celery_app.task(name="worker.tasks.new_task", bind=True, max_retries=3)
def new_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.new_handler import NewHandler
    try:
        return run_async_handler(NewHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)
```

4. Add task to `TASK_MAP` in `backend/task_queue/celery_integration.py`.

## 🧪 Monitoring & Debugging

- **Logs**: Worker logs are sent to `stdout`. Use `tail -f` to monitor processing.
- **Celery Flower**: Web-based monitoring tool (install separately):
  ```bash
  pip install flower
  celery -A backend.celery_app flower
  ```
  Access at http://localhost:5555
- **Task Status**: Check via API endpoint `/api/generate/status/{task_id}` or Celery's `AsyncResult`.
- **Inspect Workers**: `celery -A backend.celery_app inspect active`
- **Purge Queue**: `celery -A backend.celery_app purge`

## 📄 Related Documentation

- [Project Root README](../README.md)
- [Backend Documentation](../backend/README.md)
