# Docker Deployment Guide

This guide covers deployment of the Clothes Design platform using Docker and Docker Compose.

## Prerequisites

- **Docker**: Version 20.10 or later
- **Docker Compose**: Version 1.29 or later
- **Git**: For cloning the repository
- **Minimum System Resources**:
  - CPU: 2 cores
  - RAM: 4GB
  - Disk: 10GB (for images, database, and cache volumes)

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

Copy the production environment template and configure it:

```bash
cp .env.production .env
```

**Critical Configuration Steps:**

1. **Database Password**: Replace `CHANGE_THIS_PASSWORD` with a strong password
   ```bash
   # In .env:
   POSTGRES_PASSWORD=your_strong_db_password
   DATABASE_URL=postgresql://postgres:your_strong_db_password@postgres:5432/clothes_design_prod
   ```

2. **JWT Secret**: Generate a strong random secret
   ```bash
   # Generate a random secret:
   openssl rand -hex 32
   
   # In .env:
   JWT_SECRET=<generated_random_value>
   ```

3. **MinIO Credentials** (for S3-compatible storage):
   ```bash
   # In .env, customize if needed:
   AWS_ACCESS_KEY_ID=minioadmin
   AWS_SECRET_ACCESS_KEY=your_strong_minio_password
   ```

4. **API Keys** (optional for AI features):
   ```bash
   # In .env, add your production API keys:
   OPENAI_API_KEY=sk_prod_your_key_here
   STABILITY_AI_API_KEY=sk-your_key_here
   ```

### 3. Build Docker Images

```bash
docker-compose build
```

This builds three custom images:
- `clothes-design-frontend` (Next.js 16)
- `clothes-design-backend` (FastAPI)
- `clothes-design-worker` (Redis task consumer)

### 4. Start All Services

```bash
# Start services in detached mode (runs in background)
docker-compose up -d

# Or, for debugging, run in foreground (Ctrl+C to stop):
docker-compose up
```

### 5. Verify Services Are Running

Check service status:
```bash
docker-compose ps
```

Expected output (all services should show `healthy` status):
```
NAME                        STATUS
clothes-design-postgres     healthy
clothes-design-redis        healthy
clothes-design-minio        healthy
clothes-design-backend      healthy
clothes-design-worker       healthy
clothes-design-frontend     healthy
```

### 6. Test Health Endpoints

```bash
# Backend health check
curl http://localhost:8000/health

# Expected response:
# {"status":"ok"}

# Frontend accessibility
curl http://localhost:3000

# MinIO Console (for file management)
# Open browser: http://localhost:9001
# Login with: minioadmin / minioadmin
```

## Service Details

### Services Overview

| Service | Port | Purpose | Image |
|---------|------|---------|-------|
| **Frontend** | 3000 | Next.js web application | Custom (Dockerfile.frontend) |
| **Backend** | 8000 | FastAPI REST API | Custom (Dockerfile.backend) |
| **Worker** | N/A | Redis task consumer | Custom (Dockerfile.worker) |
| **PostgreSQL** | 5432 | Primary database | postgres:17-alpine |
| **Redis** | 6379 | Cache & task queue | redis:7-alpine |
| **MinIO** | 9000/9001 | S3-compatible storage | minio/minio:latest |

### Service Dependencies

```
frontend
  └── depends_on: backend

backend
  └── depends_on: postgres, redis, minio

worker
  └── depends_on: backend, redis, postgres
```

Services start in dependency order automatically with `docker-compose up`.

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

# Frontend Node shell
docker-compose exec frontend bash

# PostgreSQL shell
docker-compose exec postgres psql -U postgres -d clothes_design_prod

# Redis CLI
docker-compose exec redis redis-cli
```

### Database Operations

```bash
# Apply database migrations (if needed)
docker-compose exec backend bash
# Inside container:
alembic upgrade head

# Create database backup
docker-compose exec postgres pg_dump -U postgres clothes_design_prod > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U postgres clothes_design_prod < backup.sql
```

### MinIO Operations

```bash
# Access MinIO console
# Browser: http://localhost:9001
# Login: minioadmin / minioadmin (from .env)

# Create bucket via MinIO CLI
docker-compose exec minio mc alias set minio http://localhost:9000 minioadmin minioadmin
docker-compose exec minio mc mb minio/clothes-design-prod
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

1. Check worker logs:
   ```bash
   docker-compose logs worker
   ```

2. Verify Redis connection:
   ```bash
   docker-compose exec redis redis-cli ping
   # Should return: PONG
   ```

3. Check task queue:
   ```bash
   docker-compose exec redis redis-cli
   # Inside redis-cli:
   KEYS *
   LLEN clothes-design-queue
   ```

### Frontend Cannot Connect to Backend

1. Verify backend health:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check frontend environment variables:
   ```bash
   docker-compose exec frontend bash
   # Inside container, check env:
   env | grep NEXT_PUBLIC_API_URL
   ```

3. Check backend logs for CORS issues:
   ```bash
   docker-compose logs backend | grep -i cors
   ```

## Performance Tuning

### Increase Resource Limits

Edit `.env`:
```bash
WORKER_CONCURRENCY=8  # Increase from 4 for more parallel task processing
CACHE_TTL=7200        # Increase cache TTL for better performance
```

### Database Connection Pool

Edit `backend/db/base.py` for production:
```python
# Increase pool size for higher concurrency
create_engine(..., pool_size=20, max_overflow=10)
```

### Memory Management

Monitor container resource usage:
```bash
docker stats --no-stream
```

If memory is constrained, increase system resources or limit specific services:
```bash
# In docker-compose.yml, add to service:
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

## Backup and Recovery

### Backup Data

```bash
# Backup PostgreSQL database
docker-compose exec postgres pg_dump -U postgres clothes_design_prod | gzip > backup-$(date +%Y%m%d).sql.gz

# Backup MinIO data
docker cp clothes-design-minio:/minio_data ./minio_backup

# Backup Redis data
docker cp clothes-design-redis:/data ./redis_backup
```

### Restore Data

```bash
# Restore PostgreSQL database
gunzip < backup-20240101.sql.gz | docker-compose exec -T postgres psql -U postgres clothes_design_prod

# Restore MinIO data
docker cp ./minio_backup clothes-design-minio:/minio_data

# Restore Redis data
docker cp ./redis_backup clothes-design-redis:/data
```

## Production Considerations

### Security

1. **Change default credentials** in `.env`:
   - POSTGRES_PASSWORD
   - AWS_SECRET_ACCESS_KEY (MinIO)
   - JWT_SECRET

2. **Use environment variables securely**:
   - Never commit `.env` to version control
   - Use secrets management for sensitive data

3. **Enable firewall rules**:
   - Restrict access to ports 8000, 9001 to authorized users only
   - Do not expose MinIO console (9001) publicly

4. **SSL/TLS**:
   - Add reverse proxy (nginx) for HTTPS
   - Configure certificate management

### Monitoring

Set up monitoring for:
- Container resource usage (CPU, memory)
- Service health checks
- Error logs and application metrics
- Database connection pool status

Example using Prometheus + Grafana:
```bash
# Add to docker-compose.yml
prometheus:
  image: prom/prometheus:latest
  ...

grafana:
  image: grafana/grafana:latest
  ...
```

### Scaling

For production scale:

1. **Multiple backend/worker instances**:
   ```bash
   docker-compose up -d --scale backend=2 --scale worker=4
   ```

2. **External database** (managed PostgreSQL service)

3. **External cache** (managed Redis service)

4. **Object storage** (AWS S3 instead of MinIO)

5. **Load balancer** (nginx or cloud provider)

## Updates and Maintenance

### Update Services

```bash
# Pull latest images
docker-compose pull

# Rebuild and restart services
docker-compose up -d --build

# Verify services are healthy
docker-compose ps
```

### Clean Up

```bash
# Remove unused images and containers
docker image prune
docker container prune

# Remove all unused volumes (warning: deletes data!)
docker volume prune
```

## Support and Documentation

- **Backend API**: http://localhost:8000/docs (Swagger UI)
- **Frontend**: http://localhost:3000
- **MinIO Console**: http://localhost:9001
- **Project Issues**: See repository for issue tracking

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
