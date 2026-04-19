# Backend Structure

重构后的后端结构，将所有 Python 模块统一到 `backend/` 目录下。

## 📁 新结构

```
backend/
├── api/              # FastAPI REST API (原 backend/)
│   ├── api/         # API 路由
│   ├── auth/        # 认证模块
│   ├── db/          # 数据库模型
│   ├── rbac/        # 权限控制
│   ├── storage/     # 存储抽象
│   ├── alembic/     # 数据库迁移
│   └── main.py      # FastAPI 应用入口
├── shared/          # 共享模块
│   ├── ai/          # AI 相关工具
│   ├── providers/   # 第三方 AI Provider
│   └── task_queue/  # Celery 任务队列集成
├── worker/          # Celery Worker
│   ├── handlers/    # 异步任务处理器
│   └── celery_tasks.py  # Celery 任务定义
├── celery_app.py    # Celery 应用配置
└── pyproject.toml   # 项目依赖
```

## 🚀 启动服务

### API 服务

**方式 1：使用 Python 模块（推荐）**
```bash
cd backend
python -m api               # 生产模式
python -m api --reload      # 开发模式（自动重载）
python -m api --host 0.0.0.0 --port 8080  # 自定义配置
```

**方式 2：使用 Uvicorn 直接启动**
```bash
cd backend
uvicorn api.main:app --reload
```

### Celery Worker

**方式 1：使用 Python 模块（推荐）**
```bash
cd backend
python -m worker
```

**方式 2：使用 Celery 直接启动**
```bash
cd backend
celery -A celery_app worker --loglevel=info

# 指定队列
celery -A celery_app worker --loglevel=info --queues=generate,upscale
```

## 🔧 依赖管理

所有 Python 依赖统一在 `backend/pyproject.toml` 中管理：

```bash
cd backend
uv sync
```

## 📝 关键变化

1. **模块化**: API、Worker、Shared 模块解耦
2. **无循环依赖**: Worker 不再依赖 API，通过 `shared/` 共享代码
3. **统一包管理**: 所有依赖在一个 `pyproject.toml` 中
4. **简化导入**: 
   - `from shared.ai import ...`
   - `from shared.providers import ...`
   - `from shared.task_queue import ...`

## 📚 相关文档

- [开发指南](../docs/DEVELOPMENT.md) - 本地开发设置
- [部署指南](../docs/DEPLOYMENT.md) - Docker 部署
- [数据库文档](../docs/SCHEMA_DOCUMENTATION.md) - 数据库设计
