# Clothes Design API

The high-performance FastAPI backend for the Clothes Design platform. This service manages business logic, user roles (RBAC), database persistence, and task orchestration via Redis.

## 🚀 Features

- **FastAPI Framework**: High-performance, type-safe API with automatic OpenAPI documentation.
- **SQLAlchemy 2.0 Async**: Fully asynchronous database interactions with PostgreSQL.
- **Granular RBAC**: Permission-based access control using JSONB storage for roles and permissions.
- **JWT Authentication**: Secure user sessions with access and refresh tokens.
- **Task Orchestration**: Redis-backed producer logic for long-running AI jobs.
- **Storage Abstraction**: Support for local filesystem and S3-compatible object storage.

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.13 |
| **Framework** | FastAPI |
| **ORM** | SQLAlchemy 2.0 (Async) |
| **Migrations** | Alembic |
| **DB** | PostgreSQL |
| **Cache/Queue** | Redis |
| **Dependencies** | uv |

## 🏗 Directory Structure

```text
backend/
├── alembic/          # Database migration scripts (DDL)
├── api/              # REST API route handlers
├── auth/             # Authentication & Security logic
├── db/               # SQLAlchemy models and session management
├── middleware/       # Custom FastAPI middleware (CORS, Error handling)
├── rbac/             # Role-Based Access Control logic
├── storage/          # Storage abstraction (Local/S3)
├── task_queue/       # Redis task producer
└── tests/            # Pytest test suite
```

## ⚡ Quick Start

### 1. Prerequisites

Ensure you have `uv` installed. If using the project's `devenv`, simply enter the shell.

```bash
devenv shell
cd backend
```

### 2. Environment Configuration

Copy `.env.example` from the root directory to `backend/.env` (or use the root `.env`) and configure:

```bash
cp ../.env.example .env
```

### 3. Dependency Installation

```bash
uv sync
```

### 4. Database Migrations (CRITICAL)

This project uses Alembic for all schema changes. **Manual database modification is strictly prohibited.**

#### Important: Alembic Package Shadowing

The `backend/alembic/` directory may shadow the `alembic` package on some systems. **Always run alembic commands from the `backend/` directory.**

#### Apply All Migrations
```bash
alembic upgrade head
```

#### Create a New Migration
```bash
alembic revision --autogenerate -m "description of changes"
```

#### Other Common Commands
- **View migration history**: `alembic history`
- **Rollback last migration**: `alembic downgrade -1`
- **View current version**: `alembic current`

### 5. Seeding Data

Default roles (admin, designer, viewer) and test users are seeded automatically on first application startup via the `lifespan` event.

To manually seed roles if needed:
```bash
python -c "from rbac.seed import seed_default_roles; import asyncio; from db.session import get_session; asyncio.run(seed_default_roles(next(get_session())))"
```

### 6. Run the Server

```bash
uvicorn main:app --reload
```

Access the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

## 🧪 Testing

The backend uses `pytest` for all unit and integration tests.

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=.
```

## 🔐 Authentication & RBAC

- **JWT Secrets**: Configure `JWT_SECRET` in your `.env`.
- **Default Roles**: Defined in `rbac/seed.py`.
- **Permission Checks**: Use the `require_permission` dependency in routers.

## 📄 Related Documentation

- [Project Root README](../README.md)
- [Database Schema](../SCHEMA_DOCUMENTATION.md)
- [RBAC System Guide](rbac/README.md)


## Running

```bash
uvicorn main:app --reload
```

## Testing

```bash
pytest
```

## Linting

```bash
ruff check .
black --check .
```

## Health Check

```bash
curl http://localhost:8000/health
```
