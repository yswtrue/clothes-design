import logging
from typing import Any

from shared.ai.base import AIProvider
from shared.ai.factory import Capability, get_provider_by_capability

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class UpscaleHandler(TaskHandler):
    handler_name = "upscale"

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider | None = None

    async def _get_provider(self) -> AIProvider:
        if self.provider is None:
            result = await get_provider_by_capability(Capability.UPSCALE)
            if result is None:
                raise WorkerError("No active upscale provider configured")
            self.provider, provider_type = result
            self.logger.info(f"Using provider: {provider_type}")
        return self.provider

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        if "image" not in task_data:
            raise WorkerError("Missing required field: image")

        if "target_size" not in task_data:
            raise WorkerError("Missing required field: target_size")

        if not isinstance(task_data["image"], bytes):
            raise WorkerError("Field 'image' must be bytes")

        if not isinstance(task_data["target_size"], int):
            raise WorkerError("Field 'target_size' must be int")

        target_size = task_data["target_size"]
        if not 1024 <= target_size <= 16384:
            raise WorkerError(f"target_size must be 1024-16384, got {target_size}")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        image = task_data["image"]
        target_size = task_data["target_size"]

        self.logger.info(f"Starting upscale to target_size={target_size}")

        try:
            provider = await self._get_provider()
            upscaled = await provider.upscale_image(image, target_size)

            self.logger.info(
                f"Upscale completed: input={len(image)} bytes, output={len(upscaled)} bytes"
            )

            return {"upscaled_image": upscaled}

        except ValueError as e:
            raise WorkerError(f"Invalid input: {e}") from e

        except Exception as e:
            self.logger.error(f"Upscale failed: {e}", exc_info=True)
            raise WorkerError(f"Upscale processing failed: {e}") from e
