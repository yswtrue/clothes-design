# BACKEND WORKSPACE

**Generated:** 2026-04-19
**Workspace:** backend (Python 3.13 + FastAPI + Celery)
**Package Manager:** UV

## OVERVIEW
Unified Python workspace containing FastAPI REST API, Celery worker, and shared modules. Async-first architecture with strict dependency isolation via pyproject.toml.

## STRUCTURE
```
backend/
├── api/              # FastAPI REST API
│   ├── routes/       # REST endpoints
│   ├── auth/         # JWT + password security
│   ├── db/           # SQLAlchemy 2.0 async models
│   ├── rbac/         # Permission logic
│   ├── storage/      # S3/Local abstraction
│   ├── middleware/   # Error handlers, cache
│   ├── materials/    # Material service
│   └── alembic/      # Schema migrations
├── shared/           # Cross-workspace utilities
│   ├── ai/           # Provider interface + schemas
│   ├── providers/    # AI provider implementations
│   └── task_queue/   # Celery + Redis integration
├── worker/           # Celery task consumer
│   └── handlers/     # Async job processing
├── celery_app.py     # Celery configuration
└── pyproject.toml    # Dependencies + tool config
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Start API | `python -m api` | Uses `api/__main__.py` |
| Start Worker | `python -m worker` | Uses `worker/__main__.py` |
| Add Dependencies | `pyproject.toml` | `uv sync` to install |
| DB Models | `api/db/models.py` | SQLAlchemy 2.0 Declarative |
| API Routes | `api/routes/` | 11 route modules |
| Auth Logic | `api/auth/security.py` | JWT + bcrypt |
| Permissions | `api/rbac/service.py` | RBAC evaluation |
| Storage | `api/storage/factory.py` | S3/Local via factory |
| AI Providers | `shared/providers/` | Stability, GPT4V, ESRGAN, etc. |
| Task Queue | `shared/task_queue/` | Celery + Redis enqueue |
| Worker Handlers | `worker/handlers/` | Async task processing |
| Migrations | `api/alembic/` | `alembic upgrade head` |

## CONVENTIONS
- **Async Everywhere**: All DB and I/O operations must be `async`. Use `await` for all session/execute/commit calls.
- **Dependency Injection**: Use `Depends(get_session)` for DB access. Use `Depends(get_current_user)` for auth. Use `Depends(require_permission("perm"))` for RBAC.
- **Module Entrypoints**: Start services via `python -m api` or `python -m worker` (not direct uvicorn/celery commands in docs).
- **Package Boundary**: api/, shared/, worker/ are Python packages under backend/. Worker handlers import shared via `from shared.xxx`.
- **Monorepo Isolation**: Backend manages all Python dependencies via `pyproject.toml`. No cross-workspace imports to frontend.

## ANTI-PATTERNS (THIS PROJECT)
- **NO Sync SQL**: Never use `session.execute()` or `session.commit()` synchronously.
- **NO bcrypt >= 5**: Pinned to `< 5` for compatibility. Check `pyproject.toml`.
- **NO manual schema.sql**: All DDL must go through Alembic migrations.
- **NO sys.path hacks**: Use proper PYTHONPATH or `uv sync` to install backend as editable package instead of `sys.path.insert()`.
- **NO user deletion**: Set `deleted_at` or `SET NULL` to preserve design audit trails.

## COMMANDS
- `uv sync` - Install dependencies
- `python -m api --reload` - Start FastAPI dev server
- `python -m worker` - Start Celery worker
- `pytest` - Run test suite (expects `api/tests/`)
- `alembic upgrade head` - Apply migrations
- `alembic revision --autogenerate -m "msg"` - Create migration
- `ruff format .` - Format code
- `ruff check .` - Lint code

## NOTES
- **Worker Location**: Worker code lives under `backend/worker/`, not at repo root.
- **Shared Modules**: `backend/shared/` provides AI providers, task queue, and common schemas. Imported via `from shared.xxx`.
- **Storage**: Abstracted to support S3-compatible (MinIO) or local filesystem. Configure via `STORAGE_TYPE` env var.
- **Celery Config**: `celery_app.py` at backend root. Broker/backend use `REDIS_URL` env var.
- **Test Location**: Tests expected at `api/tests/` per `pyproject.toml` testpaths config. Directory currently empty—add async test fixtures.
- **Development Services**: PostgreSQL and Redis are already running on host. DO NOT use Docker Compose to start them.

## DIRECTORY-SPECIFIC AGENTS.MD
- `api/AGENTS.md` - FastAPI REST API patterns
- `api/routes/AGENTS.md` - REST endpoint conventions
- `api/auth/AGENTS.md` - JWT authentication
- `api/db/AGENTS.md` - Database models
- `api/rbac/AGENTS.md` - RBAC system
- `api/storage/AGENTS.md` - Storage abstraction
- `shared/AGENTS.md` - Shared utilities
- `worker/AGENTS.md` - Task queue worker
