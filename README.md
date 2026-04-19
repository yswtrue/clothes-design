# Clothes Design Platform

A high-performance clothes design platform featuring AI-powered design generation, vectorization, and mockup visualization.

## 🚀 Overview

This platform enables designers to create, iterate, and visualize clothing designs through a seamless integration of multiple AI providers. From initial concept generation to final print-ready vector export, the system manages the entire workflow asynchronously.

### Core Features

- **AI-Powered Design**: Generate unique patterns and graphics using GPT-4V and Stability AI.
- **Image Enhancement**: High-quality upscaling with Real-ESRGAN.
- **Vectorization**: Precise tracing of designs via Vectorizer.ai for print-ready outputs.
- **Mockup Visualization**: Realistic garment previews using Dynamic Mockups.
- **Granular RBAC**: Permission-based access control for Admins, Designers, and Viewers.
- **Asynchronous Workflow**: Redis-backed task queue for reliable long-running job processing.

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2.0 (Async), PostgreSQL |
| **Frontend** | Next.js 16.2 (App Router), React 19, TypeScript, Tailwind v4 |
| **Worker** | Python 3.13, Celery 5.3+, Redis |
| **Dev Environment** | devenv (Nix), Bun 1.3.10, UV |
| **AI Providers** | OpenAI, Stability AI, Vectorizer.ai, Dynamic Mockups, Replicate |

## 📦 Project Structure

```text
clothes-design/
├── backend/          # FastAPI REST API
├── frontend/         # Next.js 16.2 Frontend
├── worker/           # Task Queue Consumer
├── shared/           # Cross-workspace logic (placeholder)
└── .sisyphus/        # Project planning and knowledge base
```

## ⚡ Quick Start (Development)

### 1. Environment Setup

This project uses `devenv` for a reproducible development environment. Ensure you have Nix and `devenv` installed.

```bash
# Enter the development shell
devenv shell

# Verify the stack
check-stack
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

### 3. Initialize Services

Start the backend, frontend, and worker in separate terminals:

**Backend API:**
```bash
cd backend
python -m api --reload
```

**Worker (Celery):**
```bash
cd backend
python -m worker
```

## 🔄 Workflow

1. **Upload/Analyze**: User uploads a design or inspiration. AI analyzes the content.
2. **Generate**: New design versions are generated based on prompts/inspiration.
3. **Enhance**: Upscale low-res generations to high-quality images.
4. **Vectorize**: Convert raster designs to SVG for professional printing.
5. **Mockup**: Apply designs to garment templates for visual verification.
6. **Export**: Export final design packages for production.

## 🐳 Docker Deployment

For production-like environments using Docker, refer to the [Deployment Guide](docs/DEPLOYMENT.md).

```bash
docker-compose up -d
```

## 📄 Documentation

- **Development**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Local development setup
- **Deployment**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Docker deployment guide
- **Database Schema**: [docs/SCHEMA_DOCUMENTATION.md](docs/SCHEMA_DOCUMENTATION.md) - Database design
- **Backend**: [backend/README.md](backend/README.md) - FastAPI architecture
- **Frontend**: [frontend/README.md](frontend/README.md) - Next.js structure
- **Worker**: [backend/worker/README.md](backend/worker/README.md) - Celery tasks

## 🤝 Contributing

1. Ensure `devenv shell` is active.
2. Run tests: `pytest` (backend) or `bun run test` (frontend).
3. Follow the workspace-specific `AGENTS.md` for coding conventions.

## ⚖️ License

MIT License. See [LICENSE](LICENSE) (if available) for details.
