# BACKEND SHARED MODULES

**Generated:** 2026-04-19

## OVERVIEW
Cross-workspace utilities providing AI provider abstractions, task queue integration, and common schemas. Imported by API routes and worker handlers.

## STRUCTURE
```
shared/
├── ai/
│   ├── base.py           # AIProvider ABC
│   ├── factory.py        # Provider factory
│   ├── schemas.py        # GenerationParams, StyleAnalysis, Position
│   └── exceptions.py     # ProviderError subclasses
├── providers/
│   ├── gpt4v.py          # GPT-4V style analysis
│   ├── stability.py      # Stability AI pattern generation
│   ├── mockups.py        # Mockup compositing
│   ├── esrgan.py         # Real-ESRGAN upscaling
└── task_queue/
    ├── celery_integration.py  # enqueue_task bridge to Celery
    ├── tasks.py               # Task helpers
    ├── redis_client.py        # Redis abstraction
    └── schemas.py             # Task payload/status schemas
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add Provider | `shared/providers/` | Implement AIProvider ABC |
| Enqueue Job | `shared/task_queue/celery_integration.py` | `enqueue_task(type, data)` |
| Common Schemas | `shared/ai/schemas.py` | GenerationParams, etc. |
| Provider Errors | `shared/ai/exceptions.py` | Timeout, RateLimit, etc. |

## CONVENTIONS
- **Import Pattern**: Use `from shared.xxx import ...` (never relative imports from outside shared/).
- **Provider Interface**: All providers implement `AIProvider` ABC with async methods.
- **Factory Usage**: Prefer `get_provider(type)` from factory over direct imports.
- **Task Queue**: API routes call `enqueue_task(task_type, payload)`. Worker handlers are mapped in celery_integration TASK_MAP.
- **Schemas**: Use Pydantic models from `shared/ai/schemas.py` for typed data interchange.
- **Error Handling**: Raise `ProviderError` subclasses (ProviderTimeout, ProviderRateLimit, ProviderInvalidInput) with clear messages.

## ANTI-PATTERNS
- **NO Direct Provider Instantiation**: Use factory unless implementing provider-specific configuration.
- **NO Task Type Hardcoding**: Task types must be registered in celery_integration TASK_MAP.
- **NO Sync Provider Calls**: All provider methods are async. Always `await provider.method()`.
- **NO Generic Exceptions**: Raise specific ProviderError subclasses, not bare Exception.

## USAGE EXAMPLES
**Enqueue Task:**
```python
from shared.task_queue.celery_integration import enqueue_task

task_id = await enqueue_task("generate", {
    "design_id": 123,
    "prompt": "floral pattern",
    "style": "watercolor"
})
```

**Use Provider:**
```python
from shared.ai.factory import get_provider
from shared.ai.schemas import GenerationParams

provider = get_provider("stability")
result = await provider.generate_pattern(
    GenerationParams(prompt="floral", style="watercolor")
)
```

## NOTES
- **Provider Capabilities**:
  - GPT4V: Style analysis, design description
  - Stability: Pattern generation, style transfer
  - ESRGAN: Image upscaling (2x, 4x)
  - Mockups: Composite design onto garment template
- **Task Queue**: Celery + Redis. API enqueues, worker consumes. Metadata stored in Redis for status polling.
- **Used By**: Backend API routes (generate, upload, export, designs) and all worker handlers.
