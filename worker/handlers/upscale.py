"""Upscale task handler for image super-resolution."""

import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from providers.esrgan import ESRGANProvider  # type: ignore[import-not-found]

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class UpscaleHandler(TaskHandler):
    """Handler for upscale tasks using Real-ESRGAN."""

    handler_name = "upscale"

    def __init__(self) -> None:
        """Initialize upscale handler."""
        super().__init__()
        self.provider = ESRGANProvider()

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        """Validate upscale task input.

        Args:
            task_data: Must contain 'image' (bytes) and 'target_size' (int)

        Raises:
            WorkerError: If validation fails
        """
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
        """Process upscale task.

        Args:
            task_data: Task parameters with 'image' and 'target_size'

        Returns:
            Result dict with 'upscaled_image' (bytes)

        Raises:
            WorkerError: If processing fails
        """
        await self.validate_input(task_data)

        image = task_data["image"]
        target_size = task_data["target_size"]

        self.logger.info(f"Starting upscale to target_size={target_size}")

        try:
            upscaled = await self.provider.upscale_image(image, target_size)

            self.logger.info(
                f"Upscale completed: input={len(image)} bytes, output={len(upscaled)} bytes"
            )

            return {"upscaled_image": upscaled}

        except ValueError as e:
            raise WorkerError(f"Invalid input: {e}") from e

        except Exception as e:
            self.logger.error(f"Upscale failed: {e}", exc_info=True)
            raise WorkerError(f"Upscale processing failed: {e}") from e
