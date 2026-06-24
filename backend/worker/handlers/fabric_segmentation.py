"""Fabric patch segmentation task handler.

Runs the segmentation algorithm asynchronously in the worker.
"""

import base64
import uuid
from typing import Any

from api.services.fabric_segmentation import segment_fabric_patches
from api.storage.storages import fabric_patch_storage

from .base import TaskHandler, WorkerError


class FabricSegmentHandler(TaskHandler):
    """Handles fabric patch segmentation tasks."""

    handler_name = "fabric_segment"

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        if "image_data" not in task_data:
            raise WorkerError("Missing required field: image_data")

        image_data = task_data["image_data"]
        if not isinstance(image_data, str) or not image_data:
            raise WorkerError("image_data must be a non-empty base64 string")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        image_data_b64: str = task_data["image_data"]

        try:
            image_bytes = base64.b64decode(image_data_b64)
        except Exception as exc:
            raise WorkerError(f"Invalid base64 image_data: {exc}") from exc

        patches = segment_fabric_patches(image_bytes)

        if len(patches) < 2:
            raise WorkerError("No fabric patches detected in the image")

        result_patches: list[dict] = []
        for idx, patch in enumerate(patches):
            filename = f"{uuid.uuid4()}.png"
            url = await fabric_patch_storage.upload(patch["image_bytes"], filename)
            result_patches.append(
                {
                    "index": idx,
                    "url": url,
                    "width": patch["width"],
                    "height": patch["height"],
                }
            )

        self.logger.info(f"Segmented {len(result_patches)} patches")
        return {
            "total_patches": len(result_patches),
            "patches": result_patches,
        }
