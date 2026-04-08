"""Generate pattern handler for worker queue."""

import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from ai.schemas import GenerationParams, StyleAnalysis  # type: ignore[import-not-found]
from providers.stability import (  # type: ignore[import-not-found]
    ProviderContentPolicyError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StabilityProvider,
)

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class GenerateHandler(TaskHandler):
    """Handler for pattern generation tasks."""

    handler_name = "generate"

    def __init__(self) -> None:
        """Initialize generate handler."""
        super().__init__()
        self.provider = StabilityProvider()

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        """Validate task input data.

        Args:
            task_data: Task parameters

        Raises:
            WorkerError: If validation fails
        """
        required_fields = ["style", "params"]
        for field in required_fields:
            if field not in task_data:
                raise WorkerError(f"Missing required field: {field}")

        try:
            StyleAnalysis(**task_data["style"])
        except Exception as e:
            raise WorkerError(f"Invalid style data: {e}")

        try:
            GenerationParams(**task_data["params"])
        except Exception as e:
            raise WorkerError(f"Invalid generation params: {e}")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Process pattern generation task.

        Args:
            task_data: Task parameters containing:
                - style: StyleAnalysis dict
                - params: GenerationParams dict

        Returns:
            Result dict with:
                - status: "success" or "error"
                - image_data: Base64-encoded image (on success)
                - error: Error message (on failure)

        Raises:
            WorkerError: If task processing fails
        """
        await self.validate_input(task_data)

        style = StyleAnalysis(**task_data["style"])
        params = GenerationParams(**task_data["params"])

        try:
            image_bytes = await self.provider.generate_pattern(style, params)

            import base64

            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            self.logger.info(
                f"Pattern generated successfully: {params.width}x{params.height}, "
                f"tiling={params.tiling}, seed={params.seed}"
            )

            return {
                "status": "success",
                "image_data": image_b64,
                "width": params.width,
                "height": params.height,
                "tiling": params.tiling,
                "seed": params.seed,
            }

        except ProviderTimeoutError as e:
            self.logger.error(f"Generation timeout: {e}")
            return {"status": "error", "error": "Request timed out. Please retry."}

        except ProviderRateLimitError as e:
            self.logger.error(f"Rate limit exceeded: {e}")
            return {
                "status": "error",
                "error": "Rate limit exceeded. Please retry later.",
            }

        except ProviderContentPolicyError as e:
            self.logger.error(f"Content policy violation: {e}")
            return {
                "status": "error",
                "error": "Content policy violation. Please modify your prompt.",
            }

        except Exception as e:
            self.logger.exception(f"Unexpected error during generation: {e}")
            raise WorkerError(f"Pattern generation failed: {e}")


__all__ = ["GenerateHandler"]
