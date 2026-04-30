"""Worker handler for vectorization tasks."""

import logging
from typing import Any

from shared.providers.config_loader import get_provider_config
from shared.providers.vectorizer import VectorizerProvider

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class VectorizeHandler(TaskHandler):
    handler_name = "vectorize"

    def __init__(self) -> None:
        super().__init__()
        self.provider: VectorizerProvider | None = None

    async def _get_provider(self) -> VectorizerProvider:
        if self.provider is None:
            config = await get_provider_config("vectorizer")
            if config:
                self.provider = VectorizerProvider.from_config(config)
            else:
                self.provider = VectorizerProvider()
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
