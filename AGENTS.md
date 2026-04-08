# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-05
**Workspace:** clothes-design (Monorepo)
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
| Task | Location | Notes |
| :--- | :--- | :--- |
| API Endpoints | `backend/api/` | FastAPI routers |
| DB Models | `backend/db/models.py` | SQLAlchemy 2.0 Declarative |
| UI Components | `frontend/components/` | React 19 / Tailwind 4 |
| Auth Logic | `backend/auth/` | JWT + bcrypt < 5 |
| Permissions | `backend/rbac/` | RBAC + JSONB logic |
| Migrations | `backend/alembic/` | `alembic -c alembic.ini` |
| Worker Jobs | `worker/handlers/` | Redis tasks |

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
**Backend:**
- `uv sync` - Install dependencies
- `uvicorn main:app --reload` - Start dev server
- `pytest` - Run test suite
- `alembic upgrade head` - Apply migrations

**Frontend:**
- `bun install` - Install dependencies
- `bun run dev` - Start Next.js dev server
- `bun run build` - Production build

**Worker:**
- `python -m worker.main` - Start consumer

## NOTES
- **Auth Roles**: Default roles (admin, designer, viewer) seeded on backend startup.
- **Storage**: Abstracted to support S3-compatible or local filesystem storage.
- **Data Integrity**: DB constraints handle design versioning logic; do not reimplement in app layer.
- **Metadata**: Detailed schema info in `SCHEMA_DOCUMENTATION.md`.

## DIRECTORY-SPECIFIC AGENTS.MD
- `backend/AGENTS.md` - Backend-specific patterns
- `backend/api/AGENTS.md` - REST API routes
- `backend/tests/AGENTS.md` - Testing conventions
- `backend/db/AGENTS.md` - Database layer
- `backend/auth/AGENTS.md` - Authentication
- `backend/rbac/AGENTS.md` - Authorization
- `frontend/AGENTS.md` - Next.js 16 frontend
- `worker/AGENTS.md` - Task queue worker
