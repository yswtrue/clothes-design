# 🚀 Clothes Design Platform - 开发指南

完整的本地开发环境设置指南。

## 📋 前置要求

### 必需工具

- **Python 3.11+** 或使用项目的 devenv
- **Node.js 18+** 和 **Bun 1.0+**
- **PostgreSQL 15+**
- **Redis 7+**
- **Git**

### 可选工具

- **MinIO** (本地 S3 存储测试)
- **Docker & Docker Compose** (容器化开发)

---

## 🏗️ 项目结构

```
clothes-design/
├── backend/              # Python 后端（统一管理）
│   ├── api/             # FastAPI REST API
│   │   ├── __main__.py  # API 入口: python -m api
│   │   ├── routes/      # API 路由
│   │   ├── auth/        # 认证模块
│   │   ├── db/          # 数据库模型
│   │   └── rbac/        # 权限控制
│   ├── worker/          # Celery Worker
│   │   ├── __main__.py  # Worker 入口: python -m worker
│   │   ├── handlers/    # 任务处理器
│   │   └── celery_tasks.py
│   ├── shared/          # 共享模块
│   │   ├── ai/          # AI 工具
│   │   ├── providers/   # AI Provider 封装
│   │   └── task_queue/  # 任务队列集成
│   └── celery_app.py    # Celery 配置
├── frontend/            # Next.js 16.2 + React 19
└── .env                 # 环境变量
```

---

## ⚙️ 方式一：使用 Devenv (推荐)

### 1. 安装 Nix 和 Devenv

```bash
# 安装 Nix (如果尚未安装)
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install

# 安装 devenv
curl -fsSL https://get.jetify.com/devenv | bash
```

### 2. 进入开发环境

```bash
cd clothes-design

# 进入 devenv shell (自动安装所有依赖)
devenv shell

# 或使用 direnv 自动激活
direnv allow
```

### 3. 初始化数据库

```bash
# 在 devenv shell 中
cd backend

# 运行数据库迁移
alembic upgrade head
```

### 4. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入你的配置
# - 数据库连接
# - Redis 连接
# - AI API Keys (OpenAI, Stability AI 等)
```

### 5. 启动服务

**终端 1 - API:**
```bash
cd backend
python -m api --reload
```

**终端 2 - Worker:**
```bash
cd backend
python -m worker
```

**终端 3 - Frontend:**
```bash
cd frontend
bun install
bun run dev
```

### 6. 访问应用

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## ⚙️ 方式二：手动设置

### 1. 克隆项目

```bash
git clone https://github.com/your-org/clothes-design.git
cd clothes-design
```

### 2. 设置 PostgreSQL

```bash
# 创建数据库
createdb clothes_design

# 或使用 psql
psql -U postgres
CREATE DATABASE clothes_design;
```

### 3. 设置 Redis

```bash
# 使用系统包管理器安装
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

### 4. 后端设置

```bash
cd backend

# 安装 uv (Python 包管理器)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖
uv sync

# 配置环境变量
cp ../.env.example ../.env
# 编辑 .env

# 运行数据库迁移
alembic upgrade head

# 启动 API
python -m api --reload

# 启动 Worker (新终端)
python -m worker
```

### 5. 前端设置

```bash
cd frontend

# 安装 Bun (如果尚未安装)
curl -fsSL https://bun.sh/install | bash

# 安装依赖
bun install

# 启动开发服务器
bun run dev
```

---

## 🧪 运行测试

### 后端测试

```bash
cd backend

# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_auth.py

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

### 前端测试

```bash
cd frontend

# 运行测试
bun run test

# 运行 E2E 测试
bun run test:e2e
```

---

## 🔧 常用开发命令

### 数据库迁移

```bash
cd backend

# 创建新迁移
alembic revision --autogenerate -m "描述变更"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1

# 查看迁移历史
alembic history
```

### 代码格式化和检查

```bash
cd backend

# 格式化代码
ruff format .

# 检查代码风格
ruff check .

# 类型检查
pyright
```

### Celery 监控

```bash
cd backend

# 启动 Flower (Celery 监控工具)
celery -A celery_app flower

# 访问 http://localhost:5555
```

### 清理缓存

```bash
# 清理 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# 清理 Ruff 缓存
rm -rf .ruff_cache
```

---

## 🐛 常见问题

### 1. 导入错误 `ModuleNotFoundError`

**问题**: Python 无法找到模块

**解决**:
```bash
# 确保在正确的目录
cd backend

# 使用模块方式启动
python -m api     # 而不是 python api/main.py
python -m worker  # 而不是 python worker/main.py
```

### 2. 数据库连接失败

**问题**: `FATAL: database "clothes_design" does not exist`

**解决**:
```bash
# 创建数据库
createdb clothes_design

# 或在 psql 中
CREATE DATABASE clothes_design;
```

### 3. Redis 连接失败

**问题**: `Error 111 connecting to localhost:6379`

**解决**:
```bash
# 检查 Redis 是否运行
redis-cli ping  # 应返回 PONG

# 启动 Redis
redis-server    # 或 brew services start redis
```

### 4. Celery 任务不执行

**问题**: 任务在队列中但不执行

**解决**:
```bash
# 检查 Worker 是否运行
cd backend
python -m worker

# 检查任务注册
celery -A celery_app inspect registered
```

### 5. 前端无法连接后端

**问题**: API 请求失败

**解决**:
```bash
# 检查 .env 配置
BACKEND_API_URL=http://localhost:8000

# Docker Compose 默认不启动前端容器；如需容器化前端：
COMPOSE_PROFILES=frontend

# 检查后端是否运行
curl http://localhost:8000/health
```

---

## 📚 相关文档

- [部署指南](DEPLOYMENT.md)
- [API 文档](backend/api/README.md)
- [Worker 文档](backend/worker/README.md)
- [数据库架构](SCHEMA_DOCUMENTATION.md)
- [架构说明](.sisyphus/unified-module-structure.md)

---

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

---

## 📞 获取帮助

- 查看 [常见问题](#-常见问题)
- 阅读 [文档](#-相关文档)
- 提交 [Issue](https://github.com/your-org/clothes-design/issues)

---

**Happy Coding! 🎉**
