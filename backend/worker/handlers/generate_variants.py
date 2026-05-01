import base64
import io
import logging
import random
import uuid
from typing import Any

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings
from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.schemas import GenerationParams, StyleAnalysis
from shared.providers.config_loader import get_provider_config
from shared.providers.openai_image import OpenAIImageProvider
from shared.providers.replicate import ReplicateProvider

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (400, 400)
THUMBNAIL_QUALITY = 85
DEFAULT_IMG2IMG_STRENGTH = 0.75


class GenerateVariantsHandler(TaskHandler):
    handler_name = "generate_variants"

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider | None = None

    async def _get_provider(self) -> AIProvider:
        if self.provider is None:
            openai_config = await get_provider_config("openai_image")
            if openai_config:
                self.provider = OpenAIImageProvider.from_config(openai_config)
                self.logger.info(f"Using OpenAI image provider: {openai_config.model_name}")
            else:
                replicate_config = await get_provider_config("replicate")
                if replicate_config:
                    self.provider = ReplicateProvider.from_config(replicate_config)
                    self.logger.info("Using Replicate provider from config")
                else:
                    self.provider = ReplicateProvider()
                    self.logger.info("Using default Replicate provider")
        return self.provider

    async def _load_material_image(self, session, material_id: int) -> str | None:
        from api.db.models import Material
        from api.storage.storages import material_storage

        result = await session.execute(
            select(Material).where(Material.id == material_id)  # type: ignore[arg-type]
        )
        material = result.scalar_one_or_none()
        
        if not material or not material.stored_filename:
            self.logger.warning(f"Material {material_id} not found or has no stored_filename")
            return None

        try:
            image_bytes = await material_storage.download(material.stored_filename)
            b64_str = base64.b64encode(image_bytes).decode("utf-8")
            self.logger.info(f"Loaded material image: {material.stored_filename} ({len(image_bytes)} bytes)")
            return b64_str
        except Exception as e:
            self.logger.error(f"Failed to load material image: {e}")
            return None

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

    async def _get_existing_variants(self, session, material_id: int) -> dict[int, int]:
        from api.db.models import GeneratedDesign
        
        result = await session.execute(
            select(GeneratedDesign)
            .where(GeneratedDesign.material_id == material_id)  # type: ignore[arg-type]
        )
        rows = result.scalars().all()
        return {row.variant_index: row.id for row in rows if row.id is not None}

    async def _save_variant(
        self,
        session,
        material_id: int,
        variant_index: int,
        image_bytes: bytes,
        prompt: str,
        seed: int,
        params: GenerationParams,
    ) -> int:
        from api.db.models import GeneratedDesign
        from api.storage.storages import generated_image_storage, thumbnail_storage

        unique_id = uuid.uuid4().hex[:8]
        image_filename = f"mat_{material_id}_var_{variant_index}_{unique_id}.png"
        thumb_filename = f"mat_{material_id}_var_{variant_index}_{unique_id}_thumb.jpg"

        await generated_image_storage.upload(image_bytes, image_filename)
        self.logger.info(f"Saved image: {image_filename}")

        thumb_bytes = self._generate_thumbnail(image_bytes)
        await thumbnail_storage.upload(thumb_bytes, thumb_filename)
        self.logger.info(f"Saved thumbnail: {thumb_filename}")

        record = GeneratedDesign(
            material_id=material_id,
            image=image_filename,
            thumbnail=thumb_filename,
            prompt_used=prompt,
            seed=seed,
            variant_index=variant_index,
            generation_params=params.model_dump(exclude={"init_image_b64"}),
            is_selected=0,
        )
        session.add(record)
        await session.flush()
        
        if record.id is None:
            raise WorkerError("Failed to get record ID after flush")
        return record.id

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
        start_index = task_data.get("start_index", 0)
        prompt = task_data["prompt"]
        style_analysis_data = task_data.get("style_analysis")
        img2img_strength = task_data.get("strength", DEFAULT_IMG2IMG_STRENGTH)

        style = None
        if style_analysis_data:
            try:
                style = StyleAnalysis(**style_analysis_data)
            except Exception as e:
                self.logger.warning(f"Failed to parse style analysis: {e}")

        if style is None:
            style = StyleAnalysis(style_description=prompt, pattern_type="seamless")

        settings = get_settings()
        engine = create_async_engine(settings.database.async_url, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        results = []
        base_seed = random.randint(1, 100000)
        provider = await self._get_provider()

        try:
            async with session_factory() as session:
                material_image_b64 = await self._load_material_image(session, material_id)
                if material_image_b64:
                    self.logger.info(f"Using img2img mode with strength={img2img_strength}")
                else:
                    self.logger.warning("No material image found, falling back to text-to-image")

                existing = await self._get_existing_variants(session, material_id)
                self.logger.info(f"Found {len(existing)} existing variants for material {material_id}")

                for i in range(count):
                    variant_index = start_index + i
                    seed = base_seed + i * 1000

                    if variant_index in existing:
                        self.logger.info(f"Variant {variant_index} already exists (id={existing[variant_index]}), skipping")
                        results.append({
                            "variant_index": variant_index,
                            "id": existing[variant_index],
                            "status": "exists",
                        })
                        continue

                    try:
                        params = GenerationParams(
                            style=prompt,
                            tiling="tile",
                            width=1024,
                            height=1024,
                            seed=seed,
                            init_image_b64=material_image_b64,
                            strength=img2img_strength,
                        )

                        mode = "img2img" if material_image_b64 else "txt2img"
                        self.logger.info(f"Generating variant {variant_index} (#{i+1}/{count}) via {mode} with seed={seed}")
                        image_bytes = await provider.generate_pattern(style, params)

                        record_id = await self._save_variant(
                            session=session,
                            material_id=material_id,
                            variant_index=variant_index,
                            image_bytes=image_bytes,
                            prompt=prompt,
                            seed=seed,
                            params=params,
                        )
                        await session.commit()

                        results.append({
                            "variant_index": variant_index,
                            "id": record_id,
                            "seed": seed,
                            "status": "created",
                        })
                        self.logger.info(f"Variant {variant_index} saved successfully (id={record_id})")

                    except ProviderTimeoutError as e:
                        self.logger.error(f"Timeout generating variant {variant_index}: {e}")
                        results.append({
                            "variant_index": variant_index,
                            "error": "Generation timed out",
                            "seed": seed,
                            "status": "failed",
                        })

                    except ProviderRateLimitError as e:
                        self.logger.error(f"Rate limit for variant {variant_index}: {e}")
                        results.append({
                            "variant_index": variant_index,
                            "error": "Rate limit exceeded",
                            "seed": seed,
                            "status": "failed",
                        })

                    except ProviderError as e:
                        self.logger.error(f"Provider error for variant {variant_index}: {e}")
                        results.append({
                            "variant_index": variant_index,
                            "error": str(e),
                            "seed": seed,
                            "status": "failed",
                        })

                    except Exception as e:
                        self.logger.exception(f"Error generating variant {variant_index}: {e}")
                        await session.rollback()
                        results.append({
                            "variant_index": variant_index,
                            "error": str(e),
                            "seed": seed,
                            "status": "failed",
                        })

        finally:
            await engine.dispose()

        successful = [r for r in results if r.get("status") in ("created", "exists")]
        failed = [r for r in results if r.get("status") == "failed"]

        self.logger.info(
            f"Generation complete: {len(successful)} successful, {len(failed)} failed"
        )

        return {
            "status": "success" if successful else "failed",
            "material_id": material_id,
            "user_id": user_id,
            "variants": results,
            "total_requested": count,
            "total_successful": len(successful),
            "total_failed": len(failed),
        }


__all__ = ["GenerateVariantsHandler"]
