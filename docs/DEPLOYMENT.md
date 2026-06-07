# Docker Deployment Guide

This guide covers deployment of the Clothes Design platform using Docker and Docker Compose.

## Prerequisites

- **Docker**: Version 20.10 or later
- **Docker Compose**: Version 2.0 or later (v1.29+ also supported)
- **Git**: For cloning the repository
- **Minimum System Resources**:
  - CPU: 2 cores (4+ recommended for production)
  - RAM: 4GB (8GB+ recommended for production)
  - Disk: 20GB (for images, database, cache, and storage volumes)

Verify installation:
```bash
docker --version
docker-compose --version
```

## Quick Start

### 1. Clone Repository and Prepare Environment

```bash
git clone <repository-url>
cd clothes-design
```

### 2. Configure Environment Variables

Copy the example environment file and customize for production:

```bash
cp .env.example .env
```

**Critical Configuration Steps:**

1. **Database Password**: Replace default password with a strong one
   ```bash
   # In .env:
   POSTGRES_PASSWORD=your_strong_db_password_here
   # Note: DATABASE_URL will be auto-constructed in docker-compose.yml
   ```

2. **JWT Secret**: Generate a cryptographically secure random secret
   ```bash
   # Generate a 256-bit random secret:
   openssl rand -hex 32
   
   # In .env:
   JWT_SECRET=<paste_generated_hex_value_here>
   ```

3. **MinIO Credentials** (S3-compatible storage):
   ```bash
   # In .env, set strong credentials:
   MINIO_ROOT_USER=admin
   MINIO_ROOT_PASSWORD=your_strong_minio_password_here
   ```

4. **AI Provider API Keys** (required for AI features):
   ```bash
   # In .env, add your production API keys:
   OPENAI_API_KEY=sk-proj-your-key-here
   STABILITY_AI_API_KEY=sk-your-key-here
   VECTORIZER_AI_API_KEY=your-key-here
   REPLICATE_API_TOKEN=r8_your-token-here
   ```

5. **Worker Concurrency** (tune based on workload):
   ```bash
   # In .env:
   WORKER_CONCURRENCY=4  # Adjust based on CPU cores and task load
   ```

6. **Optional Frontend Deployment** (disabled by default):
   ```bash
   # Leave empty to deploy backend, worker, databases, and Traefik only:
   COMPOSE_PROFILES=

   # Set this when this Compose stack should also run the frontend container:
   COMPOSE_PROFILES=frontend
   ```

7. **Traefik Routing**:
   ```bash
   TRAEFIK_HTTP_PORT=80
   TRAEFIK_HTTPS_PORT=443
   TRAEFIK_ACME_EMAIL=admin@example.com
   TRAEFIK_BACKEND_HOST=api.example.com
   TRAEFIK_FRONTEND_HOST=example.com
   ```

   The Docker stack enables Traefik's Let's Encrypt HTTP-01 challenge on port 80 and stores issued certificates in the `traefik_letsencrypt` Docker volume. Make sure both `TRAEFIK_BACKEND_HOST` and `TRAEFIK_FRONTEND_HOST` resolve to this server, and that inbound ports 80 and 443 are open before starting Traefik.

### 3. Build Docker Images

```bash
docker-compose build
```

This builds custom images for the enabled services. By default the frontend profile is disabled, so build it explicitly when needed:
- `clothes-design-frontend` (Next.js 16.2 with React 19, only when `COMPOSE_PROFILES=frontend` or `--profile frontend` is used)
- `clothes-design-backend` (FastAPI with Python 3.13)
- `clothes-design-worker` (Celery worker with Python 3.13)

```bash
# Optional: build frontend image too
COMPOSE_PROFILES=frontend docker-compose build frontend
```

### 4. Initialize Database and Start Services

```bash
# Start services in detached mode (runs in background)
docker-compose up -d

# Or, for debugging/first-time setup, run in foreground to see logs:
docker-compose up

# Wait for services to become healthy (takes 30-60 seconds)
```

**Important**: On first startup, services initialize in dependency order:
1. PostgreSQL, Redis, MinIO start first
2. Backend starts and runs Alembic migrations automatically
3. Worker starts and connects to Celery broker (Redis)
4. Traefik starts and routes only services with explicit Traefik labels
5. Frontend starts last only when `COMPOSE_PROFILES=frontend` is set

### 5. Verify Services Are Running

Check service status:
```bash
docker-compose ps
```

Expected output (all services should show `healthy` status after ~60 seconds):
```
NAME                        STATUS
clothes-design-postgres     healthy
clothes-design-redis        healthy
clothes-design-minio        healthy
clothes-design-backend      healthy
clothes-design-worker       Up (no health check)
clothes-design-traefik      Up
# Only when COMPOSE_PROFILES=frontend:
clothes-design-frontend     healthy
```

**Note**: Worker service does not have a health check (Celery workers don't expose HTTP endpoints). Verify via logs:
```bash
docker-compose logs worker | grep "ready"
# Should show: celery@<hostname> ready.
```

### 6. Test Service Endpoints

```bash
# Backend health check
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Backend API documentation (Swagger UI)
open http://localhost:8000/docs

# Frontend web interface (only when COMPOSE_PROFILES=frontend)
open http://localhost:3000

# Traefik routes
curl -H 'Host: api.localhost' http://localhost/health
open http://localhost  # frontend route, only when frontend profile is enabled

# Production HTTPS routes issue Let's Encrypt certificates automatically
curl https://api.example.com/health
open https://example.com  # frontend route, only when frontend profile is enabled

# MinIO Console (object storage management)
open http://localhost:9001
# Login: minioadmin / minioadmin (or your configured credentials)
```

### 7. Verify Celery Worker

Check that the worker is processing tasks:
```bash
# View worker logs
docker-compose logs -f worker

# Expected output includes:
# - "celery@<hostname> ready."
# - Task registrations: "analyze_design_task", "generate_design_task", etc.
```

## Service Details

### Services Overview

| Service | Port(s) | Purpose | Image | Health Check |
|---------|---------|---------|-------|--------------|
| **Traefik** | 80, 443 | HTTP/HTTPS reverse proxy with Let's Encrypt certificates | traefik:v3.3 | N/A |
| **Frontend** | 3000 | Optional Next.js 16.2 web app (`COMPOSE_PROFILES=frontend`) | Custom (Dockerfile.frontend) | HTTP /3000 |
| **Backend** | 8000 | FastAPI REST API | Custom (Dockerfile.backend) | HTTP /health |
| **Worker** | N/A | Celery async task processor | Custom (Dockerfile.worker) | N/A (check logs) |
| **PostgreSQL** | 5432 | Primary database (async driver) | postgres:17-alpine | pg_isready |
| **Redis** | 6379 | Cache & Celery broker | redis:7-alpine | redis-cli ping |
| **MinIO** | 9000/9001 | S3-compatible object storage | minio/minio:latest | HTTP /health |

### Architecture Overview

```
┌─────────────┐
│  Traefik    │  (:80/:443, Host-based routing + TLS)
└──────┬──────┘
       │
       ├── Optional frontend route → Frontend :3000 (COMPOSE_PROFILES=frontend)
       │
       ▼ Backend route
┌─────────────┐     Task Enqueue (Celery)     ┌─────────────┐
│  Backend    │────────────────────────────────▶│   Worker    │
│  (FastAPI)  │                                 │  (Celery)   │
│  :8000      │                                 │             │
└──────┬──────┘                                 └──────┬──────┘
       │                                               │
       │  DB Access (async)                           │  DB Access (async)
       ▼                                               ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL :5432  (SQLAlchemy 2.0 async + asyncpg)         │
└─────────────────────────────────────────────────────────────┘
       ▲                                               ▲
       │  Redis :6379 (Celery Broker + Cache)         │
       └───────────────────────────────────────────────┘
       
       ┌─────────────┐
       │ MinIO :9000 │  (S3-compatible storage)
       └─────────────┘
```

### Service Dependencies

```
traefik
  └── routes to labelled services only

frontend (optional profile: frontend)
  └── depends_on: backend (healthy)

backend
  └── depends_on: postgres (healthy), redis (healthy), minio (healthy)

worker
  └── depends_on: backend (healthy), redis (healthy), postgres (healthy)
```

Services start in dependency order automatically. Backend runs Alembic migrations on startup.

## Common Operations

### View Service Logs

```bash
# View logs from all services
docker-compose logs -f

# View logs from specific service
docker-compose logs -f backend
docker-compose logs -f worker

# View last 100 lines from backend
docker-compose logs --tail=100 backend
```

### Stop Services

```bash
# Stop all services (containers remain)
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes (warning: deletes data!)
docker-compose down -v
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart worker

# Rebuild and restart a service
docker-compose up -d --build backend
```

### Access Service Shells

```bash
# Backend Python shell
docker-compose exec backend bash

# Frontend Node shell (only when COMPOSE_PROFILES=frontend)
COMPOSE_PROFILES=frontend docker-compose exec frontend bash

# PostgreSQL shell
docker-compose exec postgres psql -U postgres -d clothes_design_prod

# Redis CLI
docker-compose exec redis redis-cli
```

### Database Operations

```bash
# Apply database migrations (backend auto-runs on startup, but for manual trigger):
docker-compose exec backend alembic upgrade head

# Create a new migration (after model changes)
docker-compose exec backend alembic revision --autogenerate -m "description"

# Rollback one migration
docker-compose exec backend alembic downgrade -1

# Access PostgreSQL CLI
docker-compose exec postgres psql -U postgres -d clothes_design

# Create database backup
docker-compose exec postgres pg_dump -U postgres -Fc clothes_design > backup-$(date +%Y%m%d).dump

# Restore from backup
docker-compose exec -T postgres pg_restore -U postgres -d clothes_design < backup-20240101.dump
```

### MinIO Operations

```bash
# Access MinIO console web UI
open http://localhost:9001
# Login: minioadmin / minioadmin (or your configured credentials)

# Create bucket via MinIO CLI (inside container)
docker-compose exec minio sh
mc alias set local http://localhost:9000 minioadmin minioadmin
mc mb local/clothes-design
mc ls local/

# Or create bucket from host (if mc installed locally)
mc alias set prod http://localhost:9000 minioadmin minioadmin
mc mb prod/clothes-design
```

### Celery Worker Operations

```bash
# View active tasks
docker-compose exec worker celery -A celery_app inspect active

# View registered tasks
docker-compose exec worker celery -A celery_app inspect registered

# View worker stats
docker-compose exec worker celery -A celery_app inspect stats

# Purge all pending tasks (use with caution)
docker-compose exec worker celery -A celery_app purge

# Restart worker (to reload code changes)
docker-compose restart worker
```

## Troubleshooting

### Service Fails to Start

1. **Check logs** for error messages:
   ```bash
   docker-compose logs <service-name>
   ```

2. **Common issues**:
   - Port already in use: Stop other services using ports 3000, 8000, 5432, 6379, 9000
   - Missing environment variables: Verify .env file has all required variables
   - Database connection failed: Wait 30 seconds for PostgreSQL to initialize

### Health Check Failures

If a service shows "unhealthy", wait 30-60 seconds for initialization:
```bash
# Wait for service to become healthy
sleep 60 && docker-compose ps
```

### Database Connection Errors

```bash
# Test PostgreSQL connection
docker-compose exec backend bash -c "psql $DATABASE_URL -c 'SELECT 1'"

# Check PostgreSQL logs
docker-compose logs postgres
```

### Worker Not Processing Tasks

1. **Check worker logs**:
   ```bash
   docker-compose logs -f worker
   # Look for: "celery@<hostname> ready."
   ```

2. **Verify Redis connection** (Celery broker):
   ```bash
   docker-compose exec redis redis-cli ping
   # Should return: PONG
   ```

3. **Check Celery queue** (tasks waiting):
   ```bash
   docker-compose exec worker celery -A celery_app inspect active
   docker-compose exec worker celery -A celery_app inspect reserved
   ```

4. **Check Redis queue directly**:
   ```bash
   docker-compose exec redis redis-cli
   # Inside redis-cli:
   KEYS celery*
   LLEN celery  # Number of pending tasks
   ```

5. **Common issues**:
   - Worker crashed: Check logs for Python exceptions
   - Broker URL misconfigured: Verify `REDIS_QUEUE_URL` in worker env
   - Tasks not registered: Ensure `celery_tasks.py` imports are correct
   - Concurrency too low: Increase `WORKER_CONCURRENCY` in .env

### Frontend Cannot Connect to Backend

0. Confirm the optional frontend service is enabled:
   ```bash
   COMPOSE_PROFILES=frontend docker-compose ps frontend
   ```

1. Verify backend health:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check frontend environment variables:
   ```bash
   COMPOSE_PROFILES=frontend docker-compose exec frontend bash
   # Inside container, check env:
env | grep BACKEND_API_URL
   ```

3. Check backend logs for CORS issues:
   ```bash
   docker-compose logs backend | grep -i cors
   ```

## Performance Tuning

### Worker Concurrency

Edit `.env` to adjust parallel task execution:
```bash
WORKER_CONCURRENCY=8  # Increase from 4 for more parallel tasks

# Guideline:
# - CPU-bound tasks (image processing): workers = CPU cores
# - I/O-bound tasks (API calls): workers = 2-4x CPU cores
# - Mixed workload: workers = 1.5x CPU cores (starting point)
```

Restart worker after changes:
```bash
docker-compose restart worker
```

### Database Connection Pool

For production, tune pool size in `backend/api/db/base.py`:
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # Increase from default 5
    max_overflow=10,     # Extra connections during spikes
    pool_pre_ping=True,  # Verify connections before use
    echo=False           # Set True for SQL debugging
)
```

Requires backend rebuild:
```bash
docker-compose up -d --build backend
```

### Redis Persistence

For production, enable AOF (Append-Only File) for durability:
```bash
# In docker-compose.yml, redis command is already set to:
command: redis-server --appendonly yes

# Verify AOF is enabled:
docker-compose exec redis redis-cli CONFIG GET appendonly
# Should return: appendonly yes
```

### Memory Management

Monitor container resource usage:
```bash
docker stats --no-stream
```

**Expected baseline (idle):**
- Backend: ~200MB
- Worker: ~150MB
- Frontend: ~100MB
- PostgreSQL: ~50MB
- Redis: ~10MB
- MinIO: ~100MB

**Under load:**
- Worker memory grows with active tasks (AI processing is memory-intensive)
- Backend scales with concurrent API requests

To limit container resources, edit `docker-compose.yml`:
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 512M
```

Restart after changes:
```bash
docker-compose up -d
```

## Backup and Recovery

### Full Backup Strategy

```bash
# Create timestamped backup directory
BACKUP_DIR=backup-$(date +%Y%m%d-%H%M%S)
mkdir -p $BACKUP_DIR

# 1. Backup PostgreSQL database (compressed binary format)
docker-compose exec postgres pg_dump -U postgres -Fc clothes_design > $BACKUP_DIR/database.dump

# 2. Backup MinIO data (all uploaded files)
docker cp clothes-design-minio:/data $BACKUP_DIR/minio_data

# 3. Backup Redis data (task queue state, cache)
docker cp clothes-design-redis:/data $BACKUP_DIR/redis_data

# 4. Backup environment configuration
cp .env $BACKUP_DIR/env.backup

# Compress entire backup
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

echo "Backup saved: $BACKUP_DIR.tar.gz"
```

### Restore from Backup

```bash
# Extract backup
tar -xzf backup-20240101-120000.tar.gz
cd backup-20240101-120000

# 1. Stop services
docker-compose down

# 2. Restore PostgreSQL database
docker-compose up -d postgres
sleep 10  # Wait for PostgreSQL to start
docker-compose exec -T postgres pg_restore -U postgres -d clothes_design --clean < database.dump

# 3. Restore MinIO data
docker cp minio_data clothes-design-minio:/data

# 4. Restore Redis data (optional - mostly transient cache)
docker cp redis_data clothes-design-redis:/data

# 5. Restart all services
docker-compose up -d

# 6. Verify
docker-compose ps
curl http://localhost:8000/health
```

### Automated Backup Script

Create `backup.sh` for scheduled backups:
```bash
#!/bin/bash
set -e

BACKUP_DIR=/backups/$(date +%Y%m%d-%H%M%S)
mkdir -p $BACKUP_DIR

# Database only (most critical)
docker-compose exec postgres pg_dump -U postgres -Fc clothes_design > $BACKUP_DIR/database.dump

# MinIO (if using local MinIO for storage)
docker cp clothes-design-minio:/data $BACKUP_DIR/minio_data

# Compress
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

# Keep last 7 days only
find /backups -name "*.tar.gz" -mtime +7 -delete

echo "Backup complete: $BACKUP_DIR.tar.gz"
```

Add to crontab for daily backups:
```bash
0 2 * * * /path/to/backup.sh >> /var/log/clothes-design-backup.log 2>&1
```

## Production Considerations

### Security Hardening

1. **Change ALL default credentials** in `.env`:
   ```bash
   POSTGRES_PASSWORD=<strong_random_password>
   MINIO_ROOT_PASSWORD=<strong_random_password>
   JWT_SECRET=<256_bit_random_hex>
   ```

2. **Secure secrets management**:
   - **NEVER** commit `.env` to version control (already in `.gitignore`)
   - Use Docker secrets or external secret managers (Vault, AWS Secrets Manager)
   - Rotate secrets periodically (especially JWT_SECRET, API keys)

3. **Network security**:
   ```bash
   # Restrict PostgreSQL to internal network only (remove ports exposure)
   # In docker-compose.yml, comment out:
   # ports:
   #   - "5432:5432"
   
   # Restrict Redis to internal network only
   # ports:
   #   - "6379:6379"
   
   # Restrict MinIO console to localhost or VPN
   # Use firewall rules or reverse proxy
   ```

4. **Reverse proxy with SSL/TLS** (production requirement):
   - The bundled Traefik service listens on ports 80 and 443 and requests Let's Encrypt certificates automatically through the HTTP-01 challenge.
   - Set `TRAEFIK_ACME_EMAIL`, `TRAEFIK_BACKEND_HOST`, and `TRAEFIK_FRONTEND_HOST` to real public DNS names before production startup.
   - Keep port 80 reachable from the public internet because Let's Encrypt uses it to validate domain ownership.
   - Issued certificates are persisted in the `traefik_letsencrypt` Docker volume so container recreation does not trigger unnecessary re-issuance.

5. **CORS configuration**:
   ```bash
   # In .env, restrict to production domains only:
   CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

6. **Database security**:
   - Enable SSL for PostgreSQL connections
   - Use read-only database users for analytics/reporting
   - Regular security updates via `docker-compose pull`

### Monitoring and Logging

**Minimal Monitoring Setup:**

```bash
# View aggregated logs from all services
docker-compose logs -f

# Filter by service and severity
docker-compose logs -f backend | grep ERROR
docker-compose logs -f worker | grep -E "ERROR|WARN"

# Monitor container resource usage
docker stats

# Check service health
watch -n 5 'docker-compose ps'
```

**Production Monitoring Recommendations:**

1. **Application Performance Monitoring (APM)**:
   - Integrate Sentry for error tracking
   - Add New Relic or DataDog for APM
   - Enable FastAPI middleware for request tracing

2. **Infrastructure Monitoring**:
   - Prometheus + Grafana for metrics
   - Loki for log aggregation
   - AlertManager for critical alerts

3. **Health Checks**:
   ```bash
   # External health monitoring (e.g., UptimeRobot, Pingdom)
   curl https://api.yourdomain.com/health
   curl https://yourdomain.com
   ```

4. **Celery Monitoring**:
   - Use Flower for real-time task monitoring:
   ```yaml
   # Add to docker-compose.yml
   flower:
     image: mher/flower:latest
     command: celery --broker=redis://redis:6379/1 flower
     ports:
       - "5555:5555"
     depends_on:
       - redis
     networks:
       - clothes-design-net
   ```
   Access Flower UI: http://localhost:5555

5. **Log Retention**:
   ```bash
   # Configure Docker logging driver in docker-compose.yml
   services:
     backend:
       logging:
         driver: "json-file"
         options:
           max-size: "10m"
           max-file: "3"
   ```

### Scaling Strategies

**Horizontal Scaling (Multiple Instances):**

1. **Scale workers** (recommended for high task load):
   ```bash
   docker-compose up -d --scale worker=4
   ```
   
   All workers share the same Redis broker. Celery handles task distribution automatically.

2. **Scale backend** (for high API traffic):
   ```bash
   docker-compose up -d --scale backend=3
   ```
   
   Requires a load balancer in front (nginx, HAProxy, or cloud LB):
   ```nginx
   upstream backend {
       server localhost:8000;
       server localhost:8001;
       server localhost:8002;
   }
   ```

**Vertical Scaling (Resource Limits):**

Edit `docker-compose.yml`:
```yaml
services:
  worker:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 2G
```

**Cloud-Managed Services (Recommended for Production):**

1. **Database**: AWS RDS PostgreSQL or Azure Database for PostgreSQL
   - Automated backups, point-in-time recovery
   - Read replicas for analytics workloads
   - Update `DATABASE_URL` in `.env`

2. **Cache/Broker**: AWS ElastiCache Redis or Azure Cache for Redis
   - High availability with automatic failover
   - Update `REDIS_URL` and `REDIS_QUEUE_URL` in `.env`

3. **Object Storage**: AWS S3 or Azure Blob Storage
   - Unlimited scalability, CDN integration
   - Update storage settings:
   ```bash
   STORAGE_TYPE=s3
   AWS_S3_ENDPOINT=<leave_empty_for_aws_s3>
   AWS_S3_BUCKET=your-production-bucket
   AWS_ACCESS_KEY_ID=<aws_access_key>
   AWS_SECRET_ACCESS_KEY=<aws_secret_key>
   AWS_REGION=us-east-1
   ```

4. **Container Orchestration**: Kubernetes, AWS ECS, or Azure Container Instances
   - Auto-scaling based on CPU/memory metrics
   - Rolling updates with zero downtime
   - Self-healing (automatic container restarts)

**Load Testing:**

Before scaling, measure baseline performance:
```bash
# Install Apache Bench or use wrk
ab -n 1000 -c 10 http://localhost:8000/health

# Or use a more sophisticated tool
wrk -t4 -c100 -d30s http://localhost:8000/api/designs
```

## Updates and Maintenance

### Updating Application Code

```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild images (only changed services rebuild)
docker-compose build

# 3. Restart with new images (zero-downtime requires orchestrator)
docker-compose up -d

# 4. Check for errors in logs
docker-compose logs -f backend worker

# 5. Run database migrations if needed (backend auto-runs on startup)
docker-compose exec backend alembic upgrade head

# 6. Verify health
curl http://localhost:8000/health
```

### Updating Dependencies

**Backend (Python):**
```bash
# Update dependencies in backend/pyproject.toml
docker-compose build backend worker
docker-compose up -d backend worker
```

**Frontend (Node.js):**
```bash
# Update dependencies in frontend/package.json
COMPOSE_PROFILES=frontend docker-compose build frontend
COMPOSE_PROFILES=frontend docker-compose up -d frontend
```

### Updating Base Images

```bash
# Pull latest base images (PostgreSQL, Redis, MinIO)
docker-compose pull

# Restart services with new images
docker-compose up -d

# Verify no breaking changes
docker-compose logs postgres redis minio
```

### Rolling Updates (Zero Downtime)

For production, use orchestrators that support rolling updates:
- **Kubernetes**: `kubectl rollout restart deployment/backend`
- **Docker Swarm**: `docker service update --image <new_image> backend`
- **AWS ECS**: Blue/green deployment via CodeDeploy

**Manual rolling update** (requires multiple instances):
```bash
# Scale to 2 instances
docker-compose up -d --scale backend=2

# Update image
docker-compose build backend

# Restart instances one by one
docker-compose up -d --scale backend=1 --no-deps backend
sleep 30  # Wait for health check
docker-compose up -d --scale backend=2 --no-deps backend
```

### Clean Up and Maintenance

```bash
# Remove stopped containers
docker-compose down

# Remove unused images (frees disk space)
docker image prune -a

# Remove unused volumes (WARNING: deletes data!)
docker volume prune

# Remove unused networks
docker network prune

# Full cleanup (dangerous - removes all containers, images, volumes)
docker system prune -a --volumes

# View disk usage by Docker
docker system df

# Clean up old logs
find /var/lib/docker/containers -name "*.log" -mtime +7 -delete
```

### Database Maintenance

```bash
# Analyze database statistics (improves query performance)
docker-compose exec postgres psql -U postgres -d clothes_design -c "ANALYZE;"

# Vacuum database (reclaim storage)
docker-compose exec postgres psql -U postgres -d clothes_design -c "VACUUM FULL;"

# Check database size
docker-compose exec postgres psql -U postgres -d clothes_design -c "SELECT pg_size_pretty(pg_database_size('clothes_design'));"

# Check table sizes
docker-compose exec postgres psql -U postgres -d clothes_design -c "
  SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

## Support and Documentation

### Service Endpoints

- **Frontend Web App**: http://localhost:3000
- **Backend API Docs (Swagger)**: http://localhost:8000/docs
- **Backend API Docs (ReDoc)**: http://localhost:8000/redoc
- **Backend Health Check**: http://localhost:8000/health
- **MinIO Console**: http://localhost:9001 (default: minioadmin / minioadmin)
- **Flower (if enabled)**: http://localhost:5555

### Project Documentation

- **Development Guide**: [DEVELOPMENT.md](DEVELOPMENT.md) - Local setup without Docker
- **Backend README**: [backend/README.md](backend/README.md) - FastAPI architecture
- **Frontend README**: [frontend/README.md](frontend/README.md) - Next.js 16 structure
- **Worker README**: [backend/worker/README.md](backend/worker/README.md) - Celery tasks
- **Database Schema**: [SCHEMA_DOCUMENTATION.md](SCHEMA_DOCUMENTATION.md) - DB design
- **Main README**: [README.md](README.md) - Project overview

### Architecture Documentation

- `.sisyphus/unified-module-structure.md` - Module organization rationale
- `.sisyphus/refactoring-summary.md` - Celery migration summary
- `.sisyphus/worker-refactoring-rationale.md` - Worker design decisions

### Troubleshooting Checklist

Before reporting issues, verify:
- [ ] All services show `healthy` status: `docker-compose ps`
- [ ] Environment variables are set correctly: `cat .env`
- [ ] Ports 3000, 8000, 5432, 6379, 9000, 9001 are not in use
- [ ] Docker has sufficient resources (4GB+ RAM)
- [ ] Database migrations applied: `docker-compose exec backend alembic current`
- [ ] Worker registered tasks: `docker-compose logs worker | grep "registered"`
- [ ] No errors in logs: `docker-compose logs | grep -E "ERROR|FATAL"`

### Getting Help

1. **Check Logs First**:
   ```bash
   docker-compose logs -f <service_name>
   ```

2. **Review Common Issues** in this guide's Troubleshooting section

3. **Search Project Issues**: Check the repository issue tracker

4. **Create New Issue**: Include:
   - Docker versions (`docker --version`, `docker-compose --version`)
   - Service logs (`docker-compose logs backend worker`)
   - Steps to reproduce
   - Expected vs actual behavior

## Additional Resources

### Official Documentation

- **Docker**: https://docs.docker.com/
- **Docker Compose**: https://docs.docker.com/compose/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Celery**: https://docs.celeryq.dev/
- **Next.js 16**: https://nextjs.org/docs
- **PostgreSQL**: https://www.postgresql.org/docs/
- **Redis**: https://redis.io/docs/
- **MinIO**: https://min.io/docs/minio/linux/index.html
- **SQLAlchemy 2.0**: https://docs.sqlalchemy.org/en/20/

### AI Provider Documentation

- **OpenAI API**: https://platform.openai.com/docs/
- **Stability AI**: https://platform.stability.ai/docs/
- **Vectorizer.ai**: https://vectorizer.ai/api/
- **Replicate**: https://replicate.com/docs/

### DevOps Best Practices

- **Docker Security**: https://docs.docker.com/engine/security/
- **PostgreSQL Tuning**: https://pgtune.leopard.in.ua/
- **Redis Persistence**: https://redis.io/docs/management/persistence/
- **Celery Production**: https://docs.celeryq.dev/en/stable/userguide/deployment.html
- **FastAPI Deployment**: https://fastapi.tiangolo.com/deployment/

### Community and Support

- **Project Repository**: [Add your repo URL]
- **Issue Tracker**: [Add issues URL]
- **Discussions**: [Add discussions URL]
- **Changelog**: [Add CHANGELOG.md link]

---

## Quick Reference

### Essential Commands

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f [service_name]

# Check status
docker-compose ps

# Rebuild and restart
docker-compose up -d --build

# Execute command in container
docker-compose exec <service> <command>

# Access service shell
docker-compose exec <service> bash

# View resource usage
docker stats
```

### Health Check URLs

```bash
curl http://localhost:8000/health  # Backend
curl http://localhost:3000         # Frontend
curl http://localhost:9000/minio/health/live  # MinIO
docker-compose exec redis redis-cli ping  # Redis
docker-compose exec postgres pg_isready  # PostgreSQL
```

### Emergency Recovery

```bash
# Stop everything
docker-compose down

# Clean state (removes volumes - data loss!)
docker-compose down -v

# Fresh start
docker-compose up -d

# Restore from backup
# See "Backup and Recovery" section above
```

---

**Last Updated**: 2026-04-19  
**Deployment Guide Version**: 2.0 (Celery-based architecture)
