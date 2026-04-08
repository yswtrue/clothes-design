# Clothes Design Worker

The asynchronous task processing engine for the Clothes Design platform. This service consumes background jobs from a Redis queue and executes long-running AI operations.

## 🚀 Features

- **Registry-Based Handlers**: Easily extensible architecture for adding new task types.
- **Robust Retry Logic**: Built-in exponential backoff for transient failures and job timeouts.
- **Graceful Shutdown**: Properly finishes current tasks before shutting down on SIGTERM/SIGINT.
- **Status Updates**: Real-time task status reporting to the backend database.
- **Async Processing**: High-concurrency support using Python's `asyncio`.

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.13 |
| **Queue** | Redis |
| **I/O** | asyncio |
| **Backend Integration** | Shared `backend.task_queue` logic |

## 🏗 Directory Structure

```text
worker/
├── handlers/         # Task-specific logic
│   ├── base.py       # Handler ABC and registry
│   ├── analyze.py    # AI design analysis
│   ├── generate.py   # Stability AI / OpenAI generation
│   ├── upscale.py    # Real-ESRGAN / AI upscaling
│   ├── vectorize.py  # SVG tracing
│   └── mockup.py     # Garment preview generation
└── main.py           # Worker entry point and loop
```

## ⚡ Quick Start

### 1. Prerequisites

Ensure you have a running Redis instance. If using the project's `devenv`, enter the shell.

```bash
devenv shell
cd worker
```

### 2. Configure Environment Variables

The worker uses the same `.env` as the backend. Ensure `REDIS_QUEUE_URL` and AI API keys are configured.

```bash
cp ../.env.example .env
```

### 3. Run the Worker

```bash
python -m worker.main
```

## 🔄 Task Lifecycle

1. **Dequeue**: Worker waits for a task ID from the Redis queue (`BRPOP`).
2. **Validate**: The corresponding handler validates the `task_data`.
3. **Processing**: Handler executes the AI logic (with a 300s default timeout).
4. **Completion**: Worker updates the task status to `completed` with results.
5. **Error Handling**: On failure, the worker retries the task up to 3 times with exponential backoff.

## 🛠 Adding New Handlers

1. Create a new handler class in `worker/handlers/` inheriting from `TaskHandler`.
2. Implement the `handle()` and `validate_input()` methods.
3. Register the new handler in `worker/main.py`:

```python
worker.register_handler("new_task_type", NewHandlerClass)
```

## 🧪 Monitoring & Debugging

- **Logs**: Worker logs are sent to `stdout`. Use `tail -f` to monitor processing.
- **Status**: Check the `tasks` table in the database or the `/api/generate/status/{task_id}` endpoint.

## 📄 Related Documentation

- [Project Root README](../README.md)
- [Backend Documentation](../backend/README.md)

