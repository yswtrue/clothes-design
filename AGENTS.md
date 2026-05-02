# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-19
**Commit:** 52d2078
**Branch:** main
**Environment:** devenv (Nix) + direnv

## OVERVIEW

Clothes design platform platform featuring a FastAPI backend, Next.js 16 frontend, and Redis-backed task worker. Optimized for async performance and strictly enforced schema migrations.

## STRUCTURE

```
clothes-design/
├── backend/          # FastAPI REST API (Python 3.11+, UV)
│   ├── api/          # REST route handlers
│   ├── auth/         # JWT + PWD security (bcrypt < 5)
│   ├── rbac/         # Permission logic
│   ├── db/           # SQLAlchemy 2.0 models + Session injection
│   ├── storage/      # S3/Local abstraction
│   ├── task_queue/   # Redis producer
│   ├── tests/        # Pytest (async-first)
│   └── alembic/      # Schema migrations
├── frontend/         # Next.js 16.2 + React 19 (Bun)
│   └── app/          # App Router architecture
├── worker/           # Queue consumer (Python)
│   └── handlers/     # Async job processing
└── shared/           # Cross-workspace logic (placeholder)
```

## WHERE TO LOOK

| Task          | Location               | Notes                      |
| :------------ | :--------------------- | :------------------------- |
| API Endpoints | `backend/api/`         | FastAPI routers            |
| DB Models     | `backend/api/db/models.py` | SQLAlchemy 2.0 Declarative |
| Admin Panel   | `backend/api/admin.py` | Starlette-Admin (管理 AI Provider, Prompt Templates 等) |
| UI Components | `frontend/components/` | React 19 / Tailwind 4      |
| Auth Logic    | `backend/api/auth/`    | JWT + bcrypt < 5           |
| Permissions   | `backend/api/rbac/`    | RBAC + JSONB logic         |
| Migrations    | `backend/api/alembic/` | `alembic -c alembic.ini`   |
| Worker Jobs   | `backend/worker/handlers/` | Celery tasks           |
| AI Providers  | `backend/shared/providers/` | OpenAI, GPTProto, Replicate, etc. |

## CONVENTIONS

- **Async Everywhere**: All DB and I/O operations must be `async`.
- **Dependency Injection**: Use `Depends(get_session)` for DB access in FastAPI.
- **Monorepo Isolation**: Workspaces manage dependencies independently (UV for Python, Bun for JS).
- **JSONB Usage**: Prefer JSONB for permissions, design metadata, and flexible schema extensions.
- **Reproducible Env**: Use `devenv shell` or `direnv allow` for development.

## ANTI-PATTERNS (THIS PROJECT)

- **NO Sync SQL**: Never use `session.execute()` or `session.commit()` synchronously.
- **NO bcrypt >= 5**: Pinned to `< 5` for compatibility. Check `pyproject.toml`.
- **NO manual schema.sql**: All DDL must go through Alembic migrations.
- **NO npm/yarn**: Frontend requires `bun`.
- **NO user deletion**: Set `deleted_at` or `SET NULL` to preserve design audit trails.
- **NO legacy Next.js**: Next.js 16.2 + React 19 has breaking changes. Avoid Pages router.

## COMMANDS

**Environment:**

- `devenv shell` - Enter development environment
- `direnv allow` - Auto-activate environment

**Backend:**

- `cd backend && uv sync` - Install Python dependencies
- `cd backend && python -m api --reload` - Start FastAPI dev server
- `cd backend && python -m worker` - Start Celery worker
- `cd backend && pytest` - Run test suite
- `cd backend && alembic upgrade head` - Apply migrations
- `cd backend && alembic revision --autogenerate -m "msg"` - Create migration

**Frontend:**

- `cd frontend && bun install` - Install dependencies
- `cd frontend && bun run dev` - Start Next.js dev server (port 3000)
- `cd frontend && bun run build` - Production build
- `cd frontend && bun run test:e2e` - Run Playwright E2E tests

**Docker:**

- `docker-compose build` - Build images
- `docker-compose up -d` - Start all services
- `docker-compose exec backend alembic upgrade head` - Run migrations in container

## NOTES

- **Admin Panel**: 访问 `/admin` 管理 AI Provider 配置、Prompt Templates、用户、角色等。需要 admin 权限登录。
- **Auth Roles**: Default roles (admin, designer, viewer) seeded on backend startup.
- **Storage**: Abstracted to support S3-compatible or local filesystem storage.
- **Data Integrity**: DB constraints handle design versioning logic; do not reimplement in app layer.
- **Metadata**: Detailed schema info in `docs/SCHEMA_DOCUMENTATION.md`.

## DIRECTORY-SPECIFIC AGENTS.MD

- `backend/AGENTS.md` - Backend-specific patterns
- `backend/api/AGENTS.md` - REST API routes
- `backend/tests/AGENTS.md` - Testing conventions
- `backend/db/AGENTS.md` - Database layer
- `backend/auth/AGENTS.md` - Authentication
- `backend/rbac/AGENTS.md` - Authorization
- `frontend/AGENTS.md` - Next.js 16 frontend
- `worker/AGENTS.md` - Task queue worker
