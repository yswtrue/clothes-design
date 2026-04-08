# BACKEND WORKSPACE

**Workspace:** backend (FastAPI + SQLAlchemy 2.0)
**Package Manager:** UV

## OVERVIEW
High-performance async API leveraging FastAPI and SQLAlchemy 2.0. Enforces strict schema migrations via Alembic and async-first patterns for all I/O.

## WHERE TO LOOK
| Task | Location | Notes |
| :--- | :--- | :--- |
| API Routes | `api/` | Organized by resource (auth, users, materials, etc.) |
| Authentication | `auth/` | JWT issuance and password hashing logic |
| DB Layer | `db/` | `base.py` for sessions, `models.py` for schema |
| Permissions | `rbac/` | RBAC logic + seed data |
| Storage | `storage/` | S3-compatible abstraction |
| Tasks | `task_queue/` | Redis producer logic |
| Migrations | `alembic/` | DDL changes |
| Tests | `tests/` | Pytest suite with `fakeredis` and `moto` |

## CONVENTIONS
- **Dependency Injection**: Use `Depends(get_session)` for database access in all route handlers.
- **Pydantic V2**: Use `BaseModel` for all request/response schemas. Enforce strict typing.
- **Async DB**: All SQL operations must use `await session.execute()`. No exceptions.
- **Lifespan**: App startup (seeding) and shutdown logic managed in `main.py:lifespan`.
- **Package Management**: Use `uv` for dependency management (`uv sync`, `uv add`).
- **Testing**: Use `@pytest.mark.asyncio` for all DB/API tests. Mock S3 with `moto` and Redis with `fakeredis`.

## ANTI-PATTERNS
- **NO Sync SQL**: Never import or use synchronous SQLAlchemy session methods.
- **NO manual commit in routes**: Prefer middleware or context-managed commits where possible, though `lifespan` seeds do use explicit commits.
- **NO bcrypt >= 5**: Pinned to `< 5` due to breaking changes in dependency tree.
- **NO hardcoded secrets**: All configuration must go through `pydantic-settings` in `config.py` (if applicable).
- **NO manual schema edits**: Never modify the database schema without an Alembic migration.

## SUB-WORKSPACE AGENTS
- `api/AGENTS.md`: Detailed router patterns and error handling
- `db/AGENTS.md`: SQLAlchemy 2.0 async patterns and model mixins
- `auth/AGENTS.md`: JWT and security implementation details
- `tests/AGENTS.md`: Testing strategy and mock configurations
- `rbac/AGENTS.md`: Permission logic and role hierarchy
