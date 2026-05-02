import base64
import io
import logging
import uuid
from typing import Any

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import UploadFile

from config import get_settings
from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.factory import Capability, get_provider_by_capability
from shared.ai.schemas import GenerationParams, StyleAnalysis
from shared.providers.prompt_template_service import get_or_default_prompt

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (400, 400)
THUMBNAIL_QUALITY = 85


def make_upload_file(data: bytes, filename: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename)


class GenerateHandler(TaskHandler):
    handler_name = "generate"

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider | None = None
        self.provider_type: str | None = None
        self._session_factory: async_sessionmaker | None = None

    async def _get_session_factory(self) -> async_sessionmaker:
        if self._session_factory is None:
            settings = get_settings()
            engine = create_async_engine(settings.database.async_url, echo=False)
            self._session_factory = async_sessionmaker(engine, expire_on_commit=False)
        return self._session_factory

    async def _get_provider(self) -> tuple[AIProvider, str]:
        if self.provider is not None and self.provider_type is not None:
            return self.provider, self.provider_type

        result = await get_provider_by_capability(Capability.IMAGE_GENERATION)
        if result is None:
            raise WorkerError("No active image generation provider configured")

        self.provider, self.provider_type = result
        self.logger.info(f"Using provider: {self.provider_type}")
        return self.provider, self.provider_type

    async def _update_generated_design(
        self, generated_design_id: int, status: str
    ) -> None:
        from api.db.models import GeneratedDesign

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(GeneratedDesign).where(GeneratedDesign.id == generated_design_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = status
                await session.commit()
                self.logger.info(f"Updated GeneratedDesign {generated_design_id} status to '{status}'")

    def _generate_thumbnail(self, image_bytes: bytes) -> bytes:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
        return output.getvalue()

    async def validate_input(self, task_data: dict[str, Any]) -> None:
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
        await self.validate_input(task_data)

        style = StyleAnalysis(**task_data["style"])
        params = GenerationParams(**task_data["params"])
        generated_design_id = task_data.get("generated_design_id")

        try:
            is_img2img = bool(params.init_image_b64)
            task_type = "img2img" if is_img2img else "text2img"
            provider, provider_type = await self._get_provider()

            if params.prompt_override:
                prompt = params.prompt_override
                self.logger.info(f"Using custom prompt ({task_type}/{provider_type}): {prompt[:100]}...")
            else:
                prompt = await get_or_default_prompt(
                    task_type=task_type,
                    style=style,
                    params=params,
                    provider_type=provider_type,
                )
                params = params.model_copy(update={"prompt_override": prompt})
                self.logger.info(f"Using default prompt ({task_type}/{provider_type}): {prompt[:100]}...")

            image_bytes = await provider.generate_pattern(style, params)
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            self.logger.info(
                f"Pattern generated successfully: {params.width}x{params.height}, "
                f"tiling={params.tiling}, seed={params.seed}"
            )

            pattern_url = None
            if generated_design_id:
                pattern_url = await self._save_generated_design(
                    generated_design_id, image_bytes, params
                )

            return {
                "status": "success",
                "image_data": image_b64,
                "pattern_url": pattern_url,
                "width": params.width,
                "height": params.height,
                "tiling": params.tiling,
                "seed": params.seed,
            }

        except ProviderTimeoutError as e:
            self.logger.error(f"Generation timeout: {e}")
            if generated_design_id:
                await self._update_generated_design(generated_design_id, "failed")
            return {"status": "error", "error": "Request timed out. Please retry."}

        except ProviderRateLimitError as e:
            self.logger.error(f"Rate limit exceeded: {e}")
            if generated_design_id:
                await self._update_generated_design(generated_design_id, "failed")
            return {"status": "error", "error": "Rate limit exceeded. Please retry later."}

        except ProviderError as e:
            self.logger.error(f"Provider error: {e}")
            if generated_design_id:
                await self._update_generated_design(generated_design_id, "failed")
            return {"status": "error", "error": str(e)}

        except Exception as e:
            self.logger.exception(f"Unexpected error during generation: {e}")
            if generated_design_id:
                await self._update_generated_design(generated_design_id, "failed")
            raise WorkerError(f"Pattern generation failed: {e}")

    async def _save_generated_design(
        self, generated_design_id: int, image_bytes: bytes, params: GenerationParams
    ) -> str:
        from api.db.models import GeneratedDesign
        from api.storage.storages import generated_image_storage

        unique_id = uuid.uuid4().hex[:8]
        image_filename = f"gen_{generated_design_id}_{unique_id}.png"
        thumb_filename = f"gen_{generated_design_id}_{unique_id}_thumb.jpg"

        thumb_bytes = self._generate_thumbnail(image_bytes)

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(GeneratedDesign).where(GeneratedDesign.id == generated_design_id)
            )
            record = result.scalar_one_or_none()

            if record:
                record.status = "completed"
                record.image = make_upload_file(image_bytes, image_filename)
                record.thumbnail = make_upload_file(thumb_bytes, thumb_filename)
                record.seed = params.seed
                await session.commit()
                self.logger.info(f"Updated GeneratedDesign {generated_design_id} status to 'completed'")

        pattern_url = generated_image_storage.get_url(image_filename)
        return pattern_url


__all__ = ["GenerateHandler"]
