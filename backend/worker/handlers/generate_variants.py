import base64
import logging
import random
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


class GenerateVariantsHandler(TaskHandler):
    handler_name = "generate_variants"

    def __init__(self) -> None:
        super().__init__()
        self.provider: ReplicateProvider | None = None

    async def _get_provider(self) -> ReplicateProvider:
        if self.provider is None:
            config = await get_provider_config("replicate")
            if config:
                self.provider = ReplicateProvider.from_config(config)
            else:
                self.provider = ReplicateProvider()
        return self.provider

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        required_fields = ["material_id", "user_id", "count", "prompt"]
        for field in required_fields:
            if field not in task_data:
                raise WorkerError(f"Missing required field: {field}")

        count = task_data.get("count", 4)
        if not isinstance(count, int) or not 1 <= count <= 8:
            raise WorkerError(f"Invalid count: {count}. Must be 1-8")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        material_id = task_data["material_id"]
        user_id = task_data["user_id"]
        count = task_data.get("count", 4)
        prompt = task_data["prompt"]
        style_analysis_data = task_data.get("style_analysis")

        style = None
        if style_analysis_data:
            try:
                style = StyleAnalysis(**style_analysis_data)
            except Exception as e:
                self.logger.warning(f"Failed to parse style analysis: {e}")

        generated_variants = []
        base_seed = random.randint(1, 100000)
        provider = await self._get_provider()

        for i in range(count):
            seed = base_seed + i * 1000
            try:
                params = GenerationParams(
                    style=prompt,
                    tiling="tile",
                    width=1024,
                    height=1024,
                    seed=seed,
                )

                self.logger.info(f"Generating variant {i+1}/{count} with seed={seed}")

                image_bytes = await provider.generate_pattern(
                    style or StyleAnalysis(style_description=prompt, pattern_type="seamless"),
                    params,
                )

                image_b64 = base64.b64encode(image_bytes).decode("utf-8")

                variant_data = {
                    "variant_index": i,
                    "image_data": image_b64,
                    "seed": seed,
                    "prompt_used": prompt,
                    "params": params.model_dump(),
                }

                generated_variants.append(variant_data)
                self.logger.info(f"Variant {i+1}/{count} generated successfully")

            except ProviderTimeoutError as e:
                self.logger.error(f"Timeout generating variant {i}: {e}")
                generated_variants.append({
                    "variant_index": i,
                    "error": "Generation timed out",
                    "seed": seed,
                })

            except ProviderRateLimitError as e:
                self.logger.error(f"Rate limit for variant {i}: {e}")
                generated_variants.append({
                    "variant_index": i,
                    "error": "Rate limit exceeded",
                    "seed": seed,
                })

            except ProviderError as e:
                self.logger.error(f"Provider error for variant {i}: {e}")
                generated_variants.append({
                    "variant_index": i,
                    "error": str(e),
                    "seed": seed,
                })

            except Exception as e:
                self.logger.exception(f"Error generating variant {i}: {e}")
                generated_variants.append({
                    "variant_index": i,
                    "error": str(e),
                    "seed": seed,
                })

        successful = [v for v in generated_variants if "image_data" in v]
        failed = [v for v in generated_variants if "error" in v]

        self.logger.info(
            f"Generation complete: {len(successful)} successful, {len(failed)} failed"
        )

        return {
            "status": "success" if successful else "failed",
            "material_id": material_id,
            "user_id": user_id,
            "variants": generated_variants,
            "total_requested": count,
            "total_successful": len(successful),
            "total_failed": len(failed),
        }


__all__ = ["GenerateVariantsHandler"]
