"""Celery task wrappers for worker handlers.

This module provides Celery task wrappers that execute the existing
async handler logic. Each task runs in a new event loop to handle async code.
"""

import asyncio
from typing import Any

from celery_app import celery_app


def run_async_handler(handler_class: type, task_data: dict[str, Any]) -> dict[str, Any]:
    """Execute an async handler in a new event loop.

    Args:
        handler_class: Handler class to instantiate
        task_data: Task parameters

    Returns:
        Handler result dict
    """

    async def _run():
        handler = handler_class()
        return await handler.handle(task_data)

    return asyncio.run(_run())


@celery_app.task(
    name="worker.tasks.analyze",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def analyze_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze design image using GPT-4V."""
    from worker.handlers.analyze import AnalyzeHandler

    try:
        return run_async_handler(AnalyzeHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)


@celery_app.task(
    name="worker.tasks.generate",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def generate_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    """Generate pattern using Stability AI."""
    from worker.handlers.generate import GenerateHandler

    try:
        return run_async_handler(GenerateHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)


@celery_app.task(
    name="worker.tasks.upscale",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def upscale_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    """Upscale image using Real-ESRGAN."""
    from worker.handlers.upscale import UpscaleHandler

    try:
        return run_async_handler(UpscaleHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)


@celery_app.task(
    name="worker.tasks.vectorize",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def vectorize_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    """Vectorize image using Vectorizer.ai."""
    from worker.handlers.vectorize import VectorizeHandler

    try:
        return run_async_handler(VectorizeHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)


@celery_app.task(
    name="worker.tasks.mockup",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def mockup_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    """Create mockup using Dynamic Mockups."""
    from worker.handlers.mockup import MockupHandler

    try:
        return run_async_handler(MockupHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)


@celery_app.task(
    name="worker.tasks.export_pattern",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def export_pattern_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    """Export pattern package."""
    from worker.handlers.export_pattern import ExportPatternHandler

    try:
        return run_async_handler(ExportPatternHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)


@celery_app.task(
    name="worker.tasks.generate_variants",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def generate_variants_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.generate_variants import GenerateVariantsHandler

    try:
        return run_async_handler(GenerateVariantsHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)


@celery_app.task(
    name="worker.tasks.compose_tif",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def compose_tif_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.compose_tif import ComposeTifHandler

    try:
        return run_async_handler(ComposeTifHandler, task_data)
    except Exception as exc:
        self.retry(exc=exc)


__all__ = [
    "analyze_task",
    "generate_task",
    "upscale_task",
    "vectorize_task",
    "mockup_task",
    "export_pattern_task",
    "generate_variants_task",
    "compose_tif_task",
]
