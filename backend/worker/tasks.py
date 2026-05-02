from typing import Any

from taskiq_app import broker


@broker.task(task_name="worker.tasks.analyze")
async def analyze_task(task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.analyze import AnalyzeHandler

    handler = AnalyzeHandler()
    return await handler.handle(task_data)


@broker.task(task_name="worker.tasks.generate")
async def generate_task(task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.generate import GenerateHandler

    handler = GenerateHandler()
    return await handler.handle(task_data)


@broker.task(task_name="worker.tasks.upscale")
async def upscale_task(task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.upscale import UpscaleHandler

    handler = UpscaleHandler()
    return await handler.handle(task_data)


@broker.task(task_name="worker.tasks.vectorize")
async def vectorize_task(task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.vectorize import VectorizeHandler

    handler = VectorizeHandler()
    return await handler.handle(task_data)


@broker.task(task_name="worker.tasks.mockup")
async def mockup_task(task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.mockup import MockupHandler

    handler = MockupHandler()
    return await handler.handle(task_data)


@broker.task(task_name="worker.tasks.export_pattern")
async def export_pattern_task(task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.export_pattern import ExportPatternHandler

    handler = ExportPatternHandler()
    return await handler.handle(task_data)


@broker.task(task_name="worker.tasks.generate_variants")
async def generate_variants_task(task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.generate_variants import GenerateVariantsHandler

    handler = GenerateVariantsHandler()
    return await handler.handle(task_data)


@broker.task(task_name="worker.tasks.compose_tif")
async def compose_tif_task(task_data: dict[str, Any]) -> dict[str, Any]:
    from worker.handlers.compose_tif import ComposeTifHandler

    handler = ComposeTifHandler()
    return await handler.handle(task_data)


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
