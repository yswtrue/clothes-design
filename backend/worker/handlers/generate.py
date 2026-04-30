"""Generate pattern handler for worker queue."""

import logging
from typing import Any

from shared.ai.exceptions import (
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.schemas import GenerationParams, StyleAnalysis
from shared.providers.config_loader import get_provider_config
from shared.providers.replicate import ReplicateProvider

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class GenerateHandler(TaskHandler):
    """Handler for pattern generation tasks."""

    handler_name = "generate"

    def __init__(self) -> None:
        """Initialize generate handler."""
        super().__init__()
        self.provider: ReplicateProvider | None = None

    async def _get_provider(self) -> ReplicateProvider:
        """Get or initialize the provider with DB config."""
        if self.provider is None:
            config = await get_provider_config("replicate")
            if config:
                self.provider = ReplicateProvider.from_config(config)
            else:
                self.provider = ReplicateProvider()
        return self.provider

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        """Validate task input data."""
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
        """Process pattern generation task."""
        await self.validate_input(task_data)

        style = StyleAnalysis(**task_data["style"])
        params = GenerationParams(**task_data["params"])

        try:
            provider = await self._get_provider()
            image_bytes = await provider.generate_pattern(style, params)

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

        except ProviderError as e:
            self.logger.error(f"Provider error: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

        except Exception as e:
            self.logger.exception(f"Unexpected error during generation: {e}")
            raise WorkerError(f"Pattern generation failed: {e}")


__all__ = ["GenerateHandler"]
