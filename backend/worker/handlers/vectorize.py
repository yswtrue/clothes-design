import logging
from typing import Any

from shared.ai.base import AIProvider
from shared.ai.factory import Capability, get_provider_by_capability

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class VectorizeHandler(TaskHandler):
    handler_name = "vectorize"

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider | None = None

    async def _get_provider(self) -> AIProvider:
        if self.provider is None:
            result = await get_provider_by_capability(Capability.VECTORIZE)
            if result is None:
                raise WorkerError("No active vectorizer provider configured")
            self.provider, provider_type = result
            self.logger.info(f"Using provider: {provider_type}")
        return self.provider

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        if "image" not in task_data:
            raise WorkerError("Missing required field: image")

        if not isinstance(task_data["image"], bytes):
            raise WorkerError("Field 'image' must be bytes")

        color_space = task_data.get("color_space", "CMYK")
        if color_space not in ("CMYK", "RGB"):
            raise WorkerError(
                f"Invalid color_space: {color_space}. Must be 'CMYK' or 'RGB'"
            )

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        image = task_data["image"]
        color_space = task_data.get("color_space", "CMYK")

        self.logger.info(
            f"Vectorizing image ({len(image)} bytes) with color_space={color_space}"
        )

        try:
            provider = await self._get_provider()
            vectorized = await provider.vectorize(image, color_space)
            self.logger.info(f"Vectorization complete: {len(vectorized)} bytes")

            return {
                "vectorized_image": vectorized,
                "color_space": color_space,
                "format": "tif",
            }
        except ValueError as e:
            self.logger.error(f"Validation error during vectorization: {e}")
            raise WorkerError(f"Invalid input: {e}") from e

        except Exception as e:
            self.logger.error(f"Vectorization failed: {e}")
            raise
