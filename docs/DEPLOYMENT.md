# Docker Deployment Guide

This guide covers deploying the Clothes Design platform with Docker Compose. It reflects the current Compose stack: PostgreSQL, Redis, Traefik, backend, worker, an optional frontend profile, and a one-off database maintenance service.

## Prerequisites

- Docker 20.10 or later
- Docker Compose 2.0 or later
- Git
- Minimum resources: 2 CPU cores, 4 GB RAM, 20 GB disk
- Recommended production resources: 4+ CPU cores, 8+ GB RAM, external object storage, and off-host backups

Verify installation:

```bash
docker --version
docker compose version
```

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd clothes-design
```

### 2. Configure Environment Variables

Copy the example file and edit it for your environment:

```bash
cp .env.example .env
```

Critical settings:

1. **Database password**
   ```bash
   POSTGRES_PASSWORD=your_strong_db_password_here
   ```

2. **JWT secret**
   ```bash
   openssl rand -hex 32
   JWT_SECRET=<paste_generated_hex_value_here>
   ```

3. **Storage**
   ```bash
   # Local storage is the default. For production assets, prefer a persistent
   # bind/volume or external S3-compatible storage.
   STORAGE_TYPE=local
   LOCAL_STORAGE_PATH=/tmp/clothes-design/uploads

   # External S3-compatible storage example:
   # STORAGE_TYPE=s3
   # AWS_S3_ENDPOINT_URL=
   # AWS_S3_BUCKET=your-production-bucket
   # AWS_ACCESS_KEY_ID=<access_key>
   # AWS_SECRET_ACCESS_KEY=<secret_key>
   # AWS_S3_REGION_NAME=us-east-1
   ```

   The Compose file does not run an object-storage container. If you keep `STORAGE_TYPE=local`, make sure `LOCAL_STORAGE_PATH` is backed by durable host storage before using it for production uploads.

4. **AI provider credentials**

   AI provider tokens are not deployment-time environment variables. Configure them after startup in the Admin Panel at `/admin` or through the admin-only `/api/ai-providers` API. The records are stored in the database table used by the provider loader, so database backups include provider configuration.

5. **Worker concurrency**
   ```bash
   WORKER_CONCURRENCY=4
   ```

6. **Optional frontend profile**
   ```bash
   # Backend, worker, databases, and Traefik only:
   COMPOSE_PROFILES=

   # Also run the frontend container:
   COMPOSE_PROFILES=frontend
   ```

7. **Traefik routing**
   ```bash
   TRAEFIK_HTTP_PORT=80
   TRAEFIK_HTTPS_PORT=443
   TRAEFIK_ACME_EMAIL=admin@example.com
   TRAEFIK_BACKEND_HOST=api.example.com
   TRAEFIK_FRONTEND_HOST=example.com
   ```

   Traefik uses Let's Encrypt HTTP-01 validation on port 80 and stores certificates in the `traefik_letsencrypt` Docker volume. Ensure DNS points to the server and inbound ports 80 and 443 are open.

### 3. Build Images

```bash
docker compose build
```

The default stack builds the backend and worker images. Build the frontend image only when the frontend profile is enabled:

```bash
COMPOSE_PROFILES=frontend docker compose build frontend
```

### 4. Start Services

```bash
docker compose up -d

# Or run in the foreground during first-time debugging:
docker compose up
```

Startup order:

1. PostgreSQL and Redis start and become healthy.
2. `backend-migrate` runs Alembic migrations once and exits successfully.
3. Backend starts with `BACKEND_REPLICAS` replicas, defaulting to 2.
4. Worker starts and connects to Redis and PostgreSQL.
5. Traefik starts and routes only services with explicit Traefik labels.
6. Frontend starts only when the `frontend` profile is enabled.

### 5. Verify Services

```bash
docker compose ps
```

Expected containers:

```text
NAME                        STATUS
clothes-design-postgres     healthy
clothes-design-redis        healthy
clothes-design-backend-1    healthy
clothes-design-backend-2    healthy
clothes-design-backend-migrate-1 exited (0)
clothes-design-worker       Up
clothes-design-traefik      Up
# Only with COMPOSE_PROFILES=frontend:
clothes-design-frontend     healthy
```

The worker has no HTTP health endpoint. Check the logs instead:

```bash
docker compose logs worker | grep "ready"
```

### 6. Test Endpoints

```bash
# Backend health check
curl http://localhost:8000/health

# Backend API documentation
open http://localhost:8000/docs

# Frontend web interface, only when COMPOSE_PROFILES=frontend
open http://localhost:3000

# Traefik routes
curl -H 'Host: api.localhost' http://localhost/health
open http://localhost

# Production HTTPS routes
curl https://api.example.com/health
open https://example.com
```

### 7. Configure AI Providers

After the backend is healthy, sign in as an admin and create active AI provider records:

- Admin Panel: `/admin`
- API: `/api/ai-providers`

Provider records store the provider type, base URL, token, model name, active flag, priority, rate limit, and provider-specific JSON config. This is the primary runtime source for AI credentials.

## Service Details

### Services Overview

| Service | Port(s) | Purpose | Image | Health Check |
| --- | --- | --- | --- | --- |
| Traefik | 80, 443 | HTTP/HTTPS reverse proxy with Let's Encrypt certificates | `traefik:v3.3` | N/A |
| Frontend | 3000 | Optional Next.js web app (`frontend` profile) | Custom (`Dockerfile.frontend`) | HTTP `/` |
| Backend | 8000 | FastAPI REST API, scaled by `BACKEND_REPLICAS` | Custom (`Dockerfile.backend`) | HTTP `/health` |
| backend-migrate | N/A | One-off Alembic migration job before backend replicas start | Custom (`Dockerfile.backend`) | N/A |
| Worker | N/A | Celery async task processor | Custom (`Dockerfile.worker`) | Check logs |
| PostgreSQL | 5432 | Primary database | `postgres:17-alpine` | `pg_isready` |
| Redis | 6379 | Cache and Celery broker | `redis:7-alpine` | `redis-cli ping` |
| db-maintenance | N/A | One-off PostgreSQL backup/restore service (`maintenance` profile) | `postgres:17-alpine` | N/A |

### Architecture Overview

```text
┌─────────────┐
│  Traefik    │  (:80/:443, host-based routing + TLS)
└──────┬──────┘
       │
       ├── Optional frontend route → Frontend :3000 (profile: frontend)
       │
       ▼ Backend route
┌─────────────┐     Task enqueue (Celery)     ┌─────────────┐
│  Backend    │──────────────────────────────▶│   Worker    │
│  FastAPI    │                               │  Celery     │
└──────┬──────┘                               └──────┬──────┘
       │                                             │
       │ DB access                                   │ DB access
       ▼                                             ▼
┌──────────────────────────────────────────────────────────┐
│ PostgreSQL :5432 (SQLAlchemy 2.0 async + asyncpg)        │
└──────────────────────────────────────────────────────────┘
       ▲                                             ▲
       │ Redis :6379 (Celery broker + cache)         │
       └─────────────────────────────────────────────┘

Backend and worker also read/write design assets through either:
- local storage at `LOCAL_STORAGE_PATH`; or
- external S3-compatible storage when `STORAGE_TYPE=s3`.
```

### Service Dependencies

```text
traefik
  └── routes to labelled services only

frontend (optional profile: frontend)
  └── depends_on: backend (healthy)

backend
  └── depends_on: backend-migrate (completed), postgres (healthy), redis (healthy)

backend-migrate
  └── depends_on: postgres (healthy)

worker
  └── depends_on: backend (healthy), redis (healthy), postgres (healthy)

db-maintenance (profile: maintenance, one-off runs)
  └── depends_on: postgres (healthy)
```

## Common Operations

### Logs

```bash
docker compose logs -f
docker compose logs -f backend
docker compose logs -f worker
docker compose logs --tail=100 backend
```

### Stop and Restart

```bash
# Stop containers but keep them
docker compose stop

# Stop and remove containers, preserving named volumes
docker compose down

# WARNING: removes named volumes, including database and backup volumes
docker compose down -v

# Restart all services
docker compose restart

# Rebuild and restart one service
docker compose up -d --build backend
```

### Approximate Rolling Backend Update

Ordinary Docker Compose does not provide orchestrated rolling updates, but the backend defaults to two replicas (`BACKEND_REPLICAS=2`) so Traefik can keep routing to a healthy replica while Compose recreates the service.

```bash
# Build the new backend image and run migrations once.
docker compose build backend backend-migrate
docker compose run --rm backend-migrate

# Recreate backend replicas behind Traefik.
docker compose up -d --no-deps backend

# Verify both backend replicas are healthy.
docker compose ps backend
```

Use immutable image tags in production and watch `docker compose logs -f backend` during the update. This is still a best-effort Compose workflow, not Swarm/Kubernetes-style health-gated rolling deployment with automatic rollback.

### Shell Access

```bash
docker compose exec backend bash
COMPOSE_PROFILES=frontend docker compose exec frontend bash
docker compose exec postgres psql -U postgres -d clothes_design
docker compose exec redis redis-cli
```

### Database Migrations

```bash
# backend-migrate auto-runs migrations before backend replicas start. Manual commands:
docker compose run --rm backend-migrate
docker compose run --rm backend-migrate alembic downgrade -1
docker compose exec postgres psql -U postgres -d clothes_design
```

### Database Backup and Restore

Use the `db-maintenance` service for PostgreSQL backups and restores. It stores custom-format dumps in the `db_backups` Docker volume and reuses `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` from Compose.

Important safety notes:

- `db_backups` is a local Docker named volume. It survives container removal, but `docker compose down -v` deletes it.
- A backup in `db_backups` is not an off-host backup. Copy important dumps to another machine or object storage.
- Restore is destructive clean-in-place: it uses `pg_restore --clean --if-exists` inside a single transaction. It does not drop and recreate the whole database.
- Stop `backend` and `worker` before restore so no app process writes while schema/data are being replaced.

Create and list backups:

```bash
# Create a timestamped backup, for example /backups/clothes_design-20260609T120000Z.dump
docker compose run --rm db-maintenance backup

# Create a named backup
docker compose run --rm db-maintenance backup before-release.dump

# List available backups
docker compose run --rm db-maintenance list
```

Recommended restore workflow:

```bash
# 1. Stop writers
docker compose stop backend worker

# 2. Optional: take a pre-restore backup
docker compose run --rm db-maintenance backup before-restore.dump

# 3. Restore latest or a specific dump. Confirmation is required.
docker compose run --rm -e CONFIRM_RESTORE=yes db-maintenance restore latest
docker compose run --rm -e CONFIRM_RESTORE=yes db-maintenance restore before-release.dump

# 4. Restart application services and verify
docker compose up -d backend worker
docker compose run --rm backend-migrate
curl http://localhost:8000/health
```

Copy a backup file out of the Docker volume:

```bash
docker compose run --rm --entrypoint /bin/sh \
  -v "$PWD:/host" \
  db-maintenance \
  -c 'cp /backups/before-release.dump /host/before-release.dump'
```

Host-side PostgreSQL tools can still be used for one-off exports when needed:

```bash
docker compose exec postgres pg_dump -U postgres -Fc clothes_design > backup-$(date +%Y%m%d).dump
docker compose exec -T postgres pg_restore \
  -U postgres \
  -d clothes_design \
  --clean \
  --if-exists \
  --single-transaction \
  --exit-on-error \
  < backup-20240101.dump
```

### Storage Operations

The current Compose stack does not include an object-storage service. Choose one of these production-safe approaches:

- Use external S3-compatible storage and configure `STORAGE_TYPE=s3` plus the `AWS_*` settings.
- Use local storage only with a persistent host bind mount or Docker volume mapped to `LOCAL_STORAGE_PATH`.

If using local storage, include the upload directory in your backup plan:

```bash
# Example only: adjust host path to your actual persistent upload path
rsync -a /srv/clothes-design/uploads/ backup/uploads/
```

### Celery Worker Operations

```bash
docker compose exec worker celery -A celery_app inspect active
docker compose exec worker celery -A celery_app inspect registered
docker compose exec worker celery -A celery_app inspect stats
docker compose exec worker celery -A celery_app purge
docker compose restart worker
```

## Troubleshooting

### Service Fails to Start

```bash
docker compose logs <service-name>
```

Common causes:

- Port already in use: check ports 80, 443, 3000, 8000, 5432, and 6379.
- Missing required environment variables: verify database, Redis, JWT, Traefik, and storage settings in `.env`.
- Database still initializing: wait 30-60 seconds and check `docker compose ps`.
- AI providers missing: add active provider records in `/admin` or `/api/ai-providers`; do not add provider tokens as deployment-time env vars.

### Health Check Failures

```bash
sleep 60 && docker compose ps
docker compose logs backend postgres redis
```

### Database Connection Errors

```bash
docker compose exec backend bash -c "psql $DATABASE_URL -c 'SELECT 1'"
docker compose logs postgres
```

### Worker Not Processing Tasks

1. Check worker logs:
   ```bash
   docker compose logs -f worker
   ```

2. Verify Redis:
   ```bash
   docker compose exec redis redis-cli ping
   ```

3. Inspect Celery queues:
   ```bash
   docker compose exec worker celery -A celery_app inspect active
   docker compose exec worker celery -A celery_app inspect reserved
   ```

Common causes include worker crashes, `REDIS_QUEUE_URL` misconfiguration, missing task imports, or too-low `WORKER_CONCURRENCY`.

### Frontend Cannot Connect to Backend

```bash
COMPOSE_PROFILES=frontend docker compose ps frontend
curl http://localhost:8000/health
COMPOSE_PROFILES=frontend docker compose exec frontend env | grep BACKEND_API_URL
docker compose logs backend | grep -i cors
```

## Performance Tuning

### Worker Concurrency

```bash
WORKER_CONCURRENCY=8
docker compose restart worker
```

Guidelines:

- CPU-bound image processing: start near CPU core count.
- I/O-bound provider calls: start at 2-4x CPU core count.
- Mixed workload: start around 1.5x CPU core count and measure.

### Database Connection Pool

Tune the async SQLAlchemy engine in `backend/api/db/base.py` for production traffic:

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)
```

Rebuild after code changes:

```bash
docker compose up -d --build backend
```

### Redis Persistence

The Redis service enables append-only persistence. Verify it when needed:

```bash
docker compose exec redis redis-cli CONFIG GET appendonly
```

### Memory Management

```bash
docker stats --no-stream
```

Expected idle baseline:

- Backend: about 200 MB
- Worker: about 150 MB
- Frontend: about 100 MB, when enabled
- PostgreSQL: about 50 MB
- Redis: about 10 MB

## Backup and Recovery

### Full Backup Strategy

```bash
BACKUP_ROOT=backup-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_ROOT"

# 1. Database backup through the maintenance service
docker compose run --rm db-maintenance backup full-backup.dump
docker compose run --rm --entrypoint /bin/sh \
  -v "$PWD/$BACKUP_ROOT:/host" \
  db-maintenance \
  -c 'cp /backups/full-backup.dump /host/database.dump'

# 2. Local uploads, only if using durable local storage
# rsync -a /srv/clothes-design/uploads/ "$BACKUP_ROOT/uploads/"

# 3. Redis data, optional because queues/cache are usually transient
docker cp clothes-design-redis:/data "$BACKUP_ROOT/redis_data"

# 4. Environment configuration
cp .env "$BACKUP_ROOT/env.backup"

tar -czf "$BACKUP_ROOT.tar.gz" "$BACKUP_ROOT"
rm -rf "$BACKUP_ROOT"
```

If you use external S3-compatible storage, rely on that provider's lifecycle and backup features for uploaded assets.

### Restore from Backup

```bash
tar -xzf backup-20240101-120000.tar.gz

# Restore env first if needed
cp backup-20240101-120000/env.backup .env

# Start dependencies
docker compose up -d postgres redis

# Copy database dump into db_backups and restore with app writers stopped
docker compose run --rm --entrypoint /bin/sh \
  -v "$PWD/backup-20240101-120000:/host" \
  db-maintenance \
  -c 'cp /host/database.dump /backups/database.dump'

docker compose stop backend worker
docker compose run --rm -e CONFIRM_RESTORE=yes db-maintenance restore database.dump

# Restore local uploads only if you use local persistent storage
# rsync -a backup-20240101-120000/uploads/ /srv/clothes-design/uploads/

docker compose up -d
docker compose exec backend alembic upgrade head
curl http://localhost:8000/health
```

### Automated Backup Script

Example scheduled database backup:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR=/backups/$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_DIR"

docker compose run --rm db-maintenance backup scheduled.dump
docker compose run --rm --entrypoint /bin/sh \
  -v "$BACKUP_DIR:/host" \
  db-maintenance \
  -c 'cp /backups/scheduled.dump /host/database.dump'

tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"
find /backups -name "*.tar.gz" -mtime +7 -delete
```

Add to crontab:

```bash
0 2 * * * /path/to/backup.sh >> /var/log/clothes-design-backup.log 2>&1
```

## Production Considerations

### Security Hardening

1. Change default secrets:
   ```bash
   POSTGRES_PASSWORD=<strong_random_password>
   JWT_SECRET=<256_bit_random_hex>
   ```

2. Manage secrets safely:
   - Never commit `.env`.
   - Use Docker secrets or an external secret manager for production.
   - Rotate database credentials and JWT secrets regularly.
   - Rotate AI provider tokens in `/admin` or `/api/ai-providers`; they are stored in the database, not configured as required environment variables.

3. Restrict internal service ports:
   ```bash
   # In production, avoid exposing PostgreSQL and Redis publicly.
   # Keep only Traefik ports 80/443 exposed to the internet.
   ```

4. Use TLS at the edge:
   - Set real DNS names in `TRAEFIK_BACKEND_HOST` and `TRAEFIK_FRONTEND_HOST`.
   - Keep port 80 reachable for Let's Encrypt HTTP-01 validation.
   - Persist the `traefik_letsencrypt` volume.

5. Restrict CORS:
   ```bash
   CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

6. Database security:
   - Use SSL for managed PostgreSQL connections when supported.
   - Use least-privilege users for reporting or analytics.
   - Apply image updates regularly with `docker compose pull`.

### Monitoring and Logging

```bash
docker compose logs -f
docker compose logs -f backend | grep ERROR
docker compose logs -f worker | grep -E "ERROR|WARN"
docker stats
watch -n 5 'docker compose ps'
```

Recommended production additions:

- Sentry or another error tracking service
- APM such as Datadog or New Relic
- Prometheus, Grafana, Loki, and Alertmanager
- External uptime monitoring for `/health`

### Scaling Strategies

Scale workers for task throughput:

```bash
docker compose up -d --scale worker=4
```

Scale backend only behind a load balancer that understands multiple backend instances:

```bash
docker compose up -d --scale backend=3
```

Cloud-managed services recommended for production:

1. PostgreSQL: AWS RDS, Azure Database for PostgreSQL, or equivalent.
2. Redis: AWS ElastiCache, Azure Cache for Redis, or equivalent.
3. Object storage: AWS S3, Azure Blob Storage with S3-compatible gateway if required, or another compatible provider.
4. Container orchestration: Kubernetes, ECS, Azure Container Apps, or another platform with rolling deploys and health-based restarts.

Object storage environment example:

```bash
STORAGE_TYPE=s3
AWS_S3_ENDPOINT_URL=
AWS_S3_BUCKET=your-production-bucket
AWS_ACCESS_KEY_ID=<access_key>
AWS_SECRET_ACCESS_KEY=<secret_key>
AWS_S3_REGION_NAME=us-east-1
```

## Updates and Maintenance

### Updating Application Code

```bash
git pull origin main
docker compose build
docker compose up -d
docker compose logs -f backend worker
docker compose exec backend alembic upgrade head
curl http://localhost:8000/health
```

### Updating Dependencies

```bash
# Backend and worker
docker compose build backend worker
docker compose up -d backend worker

# Frontend, when enabled
COMPOSE_PROFILES=frontend docker compose build frontend
COMPOSE_PROFILES=frontend docker compose up -d frontend
```

### Updating Base Images

```bash
docker compose pull
docker compose up -d
docker compose logs postgres redis backend worker
```

### Cleanup

```bash
docker compose down
docker image prune -a
docker volume prune        # WARNING: can delete data volumes
docker network prune
docker system df
```

### Database Maintenance

```bash
docker compose exec postgres psql -U postgres -d clothes_design -c "ANALYZE;"
docker compose exec postgres psql -U postgres -d clothes_design -c "VACUUM FULL;"
docker compose exec postgres psql -U postgres -d clothes_design -c "SELECT pg_size_pretty(pg_database_size('clothes_design'));"
```

## Support and Documentation

### Service Endpoints

- Frontend web app: http://localhost:3000, only when the frontend profile is enabled
- Backend API docs: http://localhost:8000/docs
- Backend ReDoc: http://localhost:8000/redoc
- Backend health check: http://localhost:8000/health
- Flower, if added separately: http://localhost:5555

### Project Documentation

- [DEVELOPMENT.md](DEVELOPMENT.md) - Local setup without Docker
- [backend/README.md](backend/README.md) - FastAPI architecture
- [frontend/README.md](frontend/README.md) - Next.js structure
- [backend/worker/README.md](backend/worker/README.md) - Celery tasks
- [SCHEMA_DOCUMENTATION.md](SCHEMA_DOCUMENTATION.md) - Database design
- [README.md](README.md) - Project overview

### Troubleshooting Checklist

- [ ] `docker compose ps` shows expected services healthy or running.
- [ ] `.env` contains database, JWT, Redis, Traefik, and storage settings.
- [ ] Ports 80, 443, 3000, 8000, 5432, and 6379 are not already in use.
- [ ] Docker has sufficient resources.
- [ ] Database migrations are current: `docker compose run --rm backend-migrate alembic current`.
- [ ] Worker registered tasks: `docker compose logs worker | grep "registered"`.
- [ ] AI provider records are active in `/admin` or `/api/ai-providers`.
- [ ] Logs have no errors: `docker compose logs | grep -E "ERROR|FATAL"`.

### Official Documentation

- Docker: https://docs.docker.com/
- Docker Compose: https://docs.docker.com/compose/
- FastAPI: https://fastapi.tiangolo.com/
- Celery: https://docs.celeryq.dev/
- Next.js: https://nextjs.org/docs
- PostgreSQL: https://www.postgresql.org/docs/
- Redis: https://redis.io/docs/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/

### AI Provider Documentation

- OpenAI API: https://platform.openai.com/docs/
- Stability AI: https://platform.stability.ai/docs/
- Replicate: https://replicate.com/docs/

## Quick Reference

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# View logs
docker compose logs -f [service_name]

# Check status
docker compose ps

# Rebuild and restart
docker compose up -d --build

# Execute command in a container
docker compose exec <service> <command>

# View resource usage
docker stats
```

### Health Checks

```bash
curl http://localhost:8000/health       # Backend
curl http://localhost:3000              # Frontend, when enabled
docker compose exec redis redis-cli ping
docker compose exec postgres pg_isready
```

### Emergency Recovery

```bash
docker compose down

# WARNING: removes database, backup, Redis, and certificate volumes
docker compose down -v

docker compose up -d

# Restore from backup using the Backup and Recovery workflow above.
```

---

**Last Updated**: 2026-06-09
**Deployment Guide Version**: 2.1
