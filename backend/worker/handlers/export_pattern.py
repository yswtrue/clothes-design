"""Export pattern handler for high-resolution CMYK TIF workflow."""

import logging
from typing import Any

from shared.providers.esrgan import ESRGANProvider
from shared.providers.vectorizer import VectorizerProvider
from api.storage.storages import generated_image_storage, output_tif_storage

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class ExportPatternHandler(TaskHandler):
    """Handler for export_pattern tasks (upscale → vectorize → TIF CMYK)."""

    handler_name = "export_pattern"

    def __init__(self) -> None:
        super().__init__()
        self.esrgan = ESRGANProvider()
        self.vectorizer = VectorizerProvider()

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        if "pattern_url" not in task_data:
            raise WorkerError("Missing required field: pattern_url")

        if "design_id" not in task_data:
            raise WorkerError("Missing required field: design_id")

        target_resolution = task_data.get("target_resolution", 12000)
        if (
            not isinstance(target_resolution, int)
            or not 1024 <= target_resolution <= 16384
        ):
            raise WorkerError(f"Invalid target_resolution: {target_resolution}")

        color_space = task_data.get("color_space", "CMYK")
        if color_space not in ("CMYK", "RGB"):
            raise WorkerError(f"Invalid color_space: {color_space}")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        pattern_url = task_data["pattern_url"]
        design_id = task_data["design_id"]
        target_resolution = task_data.get("target_resolution", 12000)
        color_space = task_data.get("color_space", "CMYK")

        try:
            self.logger.info(f"Downloading pattern from {pattern_url}")
            pattern_bytes = await generated_image_storage.download(pattern_url)

            self.logger.info(f"Upscaling pattern to {target_resolution}px")
            upscaled_bytes = await self.esrgan.upscale_image(
                pattern_bytes, target_resolution
            )

            self.logger.info(
                f"Upscaled: {len(pattern_bytes)} → {len(upscaled_bytes)} bytes"
            )

            self.logger.info(f"Vectorizing to TIF {color_space}")
            tif_bytes = await self.vectorizer.vectorize(upscaled_bytes, color_space)

            self.logger.info(f"Vectorized: {len(tif_bytes)} bytes")

            export_filename = f"design-{design_id}-12K-{color_space}.tif"
            download_url = await output_tif_storage.upload(tif_bytes, export_filename)

            self.logger.info(f"Export complete: {download_url}")

            return {
                "download_url": download_url,
                "design_id": design_id,
                "resolution": target_resolution,
                "color_space": color_space,
                "format": "tif",
                "file_size": len(tif_bytes),
            }

        except Exception as e:
            self.logger.error(f"Export failed: {e}", exc_info=True)
            raise WorkerError(f"Export processing failed: {e}") from e
