# 故障排查指南

## 问题：上传后前端一直轮询，Celery 没有触发任务

### 根本原因
Celery Worker 没有运行，导致任务入队后无人处理。

### 解决方案

#### 1. 启动 Redis（如果未运行）
```bash
# 检查 Redis 是否运行
redis-cli ping

# 如果没有运行，启动 Redis
redis-server

# 或使用 Docker
docker run -d -p 6379:6379 redis
```

#### 2. 启动 Celery Worker
```bash
cd backend

# 使用 Python 模块启动（推荐）
python -m worker
```

#### 3. 启动 API 服务器
```bash
cd backend
python -m api --reload
```

#### 4. 验证任务处理

**上传文件后，检查以下日志：**

**API 日志（应该看到）：**
```
INFO - Enqueueing analyze task for material_id=1
INFO - Analyze task enqueued successfully: task_id=xxxx-xxxx-xxxx
```

**Worker 日志（应该看到）：**
```
[INFO/MainProcess] Task worker.tasks.analyze[xxxx-xxxx-xxxx] received
[INFO/ForkPoolWorker-1] Task worker.tasks.analyze[xxxx-xxxx-xxxx] succeeded in 2.5s
```

### 环境变量检查

确保 `.env` 文件包含：

```bash
# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/clothes_design

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_QUEUE_URL=redis://localhost:6379/0

# OpenAI (用于风格分析)
OPENAI_API_KEY=sk-...

# 存储
STORAGE_TYPE=local  # 或 s3
STORAGE_LOCAL_PATH=./uploads
```

### 常见错误

#### 错误 1: `Connection refused` 
**原因**: Redis 未运行  
**解决**: 启动 Redis

#### 错误 2: `Celery not available`
**原因**: Worker 模块导入失败  
**解决**: 检查依赖 `uv sync`

#### 错误 3: 任务状态一直 `PENDING`
**原因**: Worker 未监听正确的队列  
**解决**: 使用上面的启动命令，确保监听所有队列

#### 错误 4: `ProviderConfigurationError`
**原因**: OpenAI API Key 未配置  
**解决**: 在 `.env` 中设置 `OPENAI_API_KEY`

### 调试命令

```bash
# 检查 Redis 连接
redis-cli ping

# 检查 Celery 任务队列
redis-cli LLEN analyze

# 手动测试任务入队
cd backend
python << EOF
import asyncio
from shared.task_queue.celery_integration import enqueue_task

async def test():
    task_id = await enqueue_task(
        task_type="analyze",
        user_id=1,
        data={"material_id": 1, "image_data": "test"}
    )
    print(f"Task ID: {task_id}")

asyncio.run(test())
EOF

# 检查任务状态
python << EOF
from celery.result import AsyncResult
result = AsyncResult("task-id-here")
print(f"State: {result.state}")
print(f"Info: {result.info}")
EOF
```

### 完整启动流程

**终端 1 - Redis:**
```bash
redis-server
```

**终端 2 - Celery Worker:**
```bash
cd backend
python -m worker
```

**终端 3 - API Server:**
```bash
cd backend
python -m api --reload
```

**终端 4 - Frontend:**
```bash
cd frontend
bun run dev
```

现在上传文件应该会：
1. API 创建 Material 记录
2. API 触发 analyze 任务
3. Worker 接收并处理任务
4. Worker 调用 GPT-4V 分析图片
5. Worker 更新 Material.meta.style_analysis
6. 前端轮询检测到 style_analysis，停止轮询并显示结果
