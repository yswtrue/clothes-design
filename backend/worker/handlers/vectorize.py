"""Worker handler for vectorization tasks."""

import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from shared.providers.vectorizer import VectorizerProvider  # type: ignore[import-not-found]

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class VectorizeHandler(TaskHandler):
    """Handler for vectorization tasks using Vectorizer.ai."""

    handler_name = "vectorize"

    def __init__(self) -> None:
        """Initialize vectorize handler."""
        super().__init__()
        self.provider = VectorizerProvider()

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        """Validate vectorization task input.

        Args:
            task_data: Task parameters

        Raises:
            WorkerError: If required fields are missing or invalid
        """
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
        """Process vectorization task.

        Args:
            task_data: Task parameters containing:
                - image: bytes - raster image to vectorize
                - color_space: str - "CMYK" or "RGB" (default "CMYK")

        Returns:
            Result dict containing:
                - vectorized_image: bytes - TIF format output
                - color_space: str - color space used
                - format: str - output format ("tif")

        Raises:
            Exception: Any error during vectorization
        """
        await self.validate_input(task_data)

        image = task_data["image"]
        color_space = task_data.get("color_space", "CMYK")

        self.logger.info(
            f"Vectorizing image ({len(image)} bytes) with color_space={color_space}"
        )

        try:
            vectorized = await self.provider.vectorize(image, color_space)
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
