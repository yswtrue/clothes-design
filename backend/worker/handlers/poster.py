"""E-commerce poster generation handler.

Loads uploaded product photos, composites them into a reference image,
and uses AI img2img to generate styled e-commerce poster images.
"""

import base64
import io
import logging
import uuid
from typing import Any, cast

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.sql.elements import ColumnElement

from config import get_settings
from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.factory import Capability, get_provider_by_capability
from shared.ai.schemas import GenerationParams, StyleAnalysis

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)

# Style-specific prompt prefixes for img2img — bilingual (en / zh)
STYLE_PROMPTS: dict[str, dict[str, str]] = {
    "en": {
        "studio": "clean white background, studio lighting, product centered, minimal shadows, high-key commercial photography",
        "lifestyle": "lifestyle setting with natural context, realistic environment, soft daylight, candid commercial shot",
        "minimalist": "minimalist composition, ample negative space, elegant simplicity, architectural aesthetic",
        "luxury": "luxury presentation, dramatic contrast lighting, premium backdrop, gold or dark accents, high-end catalog",
        "vintage": "film grain, warm muted tones, retro film photography, analog aesthetic, 90s commercial look",
        "outdoor": "outdoor natural setting, golden hour sunlight, greenery or urban backdrop, fresh air feel",
        "editorial": "fashion editorial composition, bold high-contrast lighting, magazine cover quality, avant-garde styling",
    },
    "zh": {
        "studio": "纯白背景，影棚灯光，产品居中展示，干净无阴影，高清商业摄影",
        "lifestyle": "生活场景，自然氛围，柔和日光，真实环境，自然抓拍感",
        "minimalist": "极简构图，大量留白，优雅简洁，建筑美学感，高级质感",
        "luxury": "奢华展示，戏剧性对比光，高级背景，金色或暗色调点缀，高端画册质感",
        "vintage": "胶片颗粒感，温暖柔和色调，复古摄影风格，90年代商业片质感",
        "outdoor": "户外自然场景，黄金时段阳光，绿植或都市背景，清新自然感",
        "editorial": "时尚杂志大片构图，高对比度光影，封面级质感，前卫造型",
    },
}

PRODUCT_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "tops": "tops and shirts", "pants": "pants and trousers",
        "skirts": "skirts and dresses", "outerwear": "outerwear and jackets",
        "shoes": "shoes and footwear", "bags": "bags and handbags",
        "accessories": "fashion accessories", "other": "fashion products",
    },
    "zh": {
        "tops": "上衣和衬衫", "pants": "裤装",
        "skirts": "裙装", "outerwear": "外套和夹克",
        "shoes": "鞋类", "bags": "包袋",
        "accessories": "时尚配饰", "other": "时尚单品",
    },
}


def _condition(value: object) -> ColumnElement[bool]:
    return cast(ColumnElement[bool], value)


class EcommercePosterHandler(TaskHandler):
    handler_name = "ecommerce_poster"

    # Composite grid settings
    _COMPOSITE_CELL = 512   # each product photo resized to 512×512 in the composite
    _COMPOSITE_MAX_COLS = 3 # max columns in the grid
    _IMG2IMG_STRENGTH = 0.6 # how much the AI can alter vs preserve (0=keep, 1=ignore)

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider | None = None
        self.provider_type: str | None = None
        self._session_factory: async_sessionmaker | None = None

    # ── infrastructure ──────────────────────────────────────────────

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

    # ── validation ──────────────────────────────────────────────────

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        required_fields = [
            "material_ids", "product_type", "style", "language",
            "image_count", "width", "height",
        ]
        for field in required_fields:
            if field not in task_data:
                raise WorkerError(f"Missing required field: {field}")
        material_ids = task_data["material_ids"]
        if not isinstance(material_ids, list) or len(material_ids) == 0:
            raise WorkerError("material_ids must be a non-empty list")
        image_count = task_data["image_count"]
        if not isinstance(image_count, int) or image_count < 1 or image_count > 10:
            raise WorkerError("image_count must be between 1 and 10")
        language = task_data["language"]
        if language not in ("en", "zh"):
            raise WorkerError("language must be 'en' or 'zh'")

    # ── material image loading ──────────────────────────────────────

    async def _load_material_images(self, material_ids: list[int]) -> list[bytes]:
        """Download all product photos from storage and return raw bytes."""
        from api.storage.storages import material_storage

        images: list[bytes] = []
        for mid in material_ids:
            session_factory = await self._get_session_factory()
            async with session_factory() as session:
                from api.db.models import Material
                result = await session.execute(
                    select(Material).where(_condition(Material.id == mid))
                )
                material = result.scalar_one_or_none()
                if not material or not material.stored_filename:
                    self.logger.warning(f"Material {mid} not found or has no file, skipping")
                    continue
                try:
                    data = await material_storage.download(material.stored_filename)
                    images.append(data)
                    self.logger.info(
                        f"Loaded material {mid}: {material.original_filename} ({len(data)} bytes)"
                    )
                except Exception as e:
                    self.logger.error(f"Failed to download material {mid}: {e}")
                    continue

        if not images:
            raise WorkerError("No valid material images could be loaded")
        return images

    # ── image compositing ───────────────────────────────────────────

    def _composite_images(self, images: list[bytes]) -> bytes:
        """Arrange multiple product photos into a single grid image for img2img.

        Returns a PNG bytes buffer of the composite grid.
        """
        pil_images = [Image.open(io.BytesIO(img)).convert("RGB") for img in images]
        n = len(pil_images)
        cols = min(n, self._COMPOSITE_MAX_COLS)
        rows = (n + cols - 1) // cols
        cell = self._COMPOSITE_CELL

        # Resize all product photos to uniform cell size
        resized = [img.resize((cell, cell), Image.Resampling.LANCZOS) for img in pil_images]

        canvas_w = cols * cell
        canvas_h = rows * cell
        canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

        for i, img in enumerate(resized):
            row = i // cols
            col = i % cols
            canvas.paste(img, (col * cell, row * cell))

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

    # ── prompt building ─────────────────────────────────────────────

    def _build_poster_prompt(
        self, product_type: str, style: str, language: str, custom_prompt: str | None
    ) -> str:
        """Build an img2img-optimized prompt in the specified language."""
        lang = language if language in STYLE_PROMPTS else "en"
        labels = PRODUCT_LABELS[lang]
        style_desc = STYLE_PROMPTS[lang].get(style, f"{style} style commercial photography")

        product_label = labels.get(product_type, product_type)

        if lang == "zh":
            parts = [
                f"专业的{product_label}电商产品海报",
                "基于提供的参考产品图片，创作精美的商业海报",
                style_desc,
                "输出应为干净、吸引人的产品展示图，适合线上店铺使用",
                "高分辨率，专业产品摄影，8K细节",
            ]
        else:
            parts = [
                f"Professional e-commerce product poster featuring {product_label}",
                "Based on the reference product images shown, create a polished commercial poster",
                style_desc,
                "The output should be a clean, attractive product showcase suitable for online store listing",
                "High resolution, professional product photography, 8K detail",
            ]
        if custom_prompt:
            parts.append(custom_prompt)
        return ". ".join(parts)

    # ── main handler ────────────────────────────────────────────────

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        poster_id = task_data.get("poster_id")
        product_type: str = task_data["product_type"]
        style: str = task_data["style"]
        language: str = task_data.get("language", "en")
        custom_prompt: str | None = task_data.get("custom_prompt")
        image_count: int = task_data["image_count"]
        width: int = task_data["width"]
        height: int = task_data["height"]
        material_ids: list[int] = task_data["material_ids"]

        try:
            # ── Step 1: load all product photos ──
            material_images = await self._load_material_images(material_ids)
            self.logger.info(f"Loaded {len(material_images)} product photos for poster generation")

            # ── Step 2: composite into single reference image ──
            composited = self._composite_images(material_images)
            init_image_b64 = base64.b64encode(composited).decode("utf-8")
            self.logger.info(
                f"Composited {len(material_images)} images → {len(composited)} bytes "
                f"(b64: {len(init_image_b64)} chars)"
            )

            # ── Step 3: build prompt ──
            full_prompt = self._build_poster_prompt(product_type, style, language, custom_prompt)
            self.logger.info(f"Poster prompt (lang={language}): {full_prompt[:150]}...")

            # ── Step 4: get AI provider ──
            provider, provider_type = await self._get_provider()

            # ── Step 5: generate images ──
            # StyleAnalysis is required by the provider interface; the actual prompt
            # is delivered via params.prompt_override to bypass fabric-specific wrapping.
            style_analysis = StyleAnalysis(
                style_description=full_prompt,
                color_palette=[],
                pattern_type="standalone",
                suggested_params={},
            )

            result_urls: list[str] = []
            for i in range(image_count):
                self.logger.info(
                    f"Generating poster image {i + 1}/{image_count} (seed={42 + i})"
                )
                params = GenerationParams(
                    style=product_type,
                    tiling="tile",
                    width=width,
                    height=height,
                    seed=42 + i,
                    init_image_b64=init_image_b64,
                    strength=self._IMG2IMG_STRENGTH,
                    prompt_override=full_prompt,
                )

                image_bytes = await provider.generate_pattern(style_analysis, params)

                if poster_id:
                    url = await self._save_poster_image(poster_id, i, image_bytes)
                    result_urls.append(url)
                    self.logger.info(f"Saved poster image {i + 1}: {url}")

            if poster_id:
                await self._update_poster_record(poster_id, result_urls)

            return {
                "status": "success",
                "result_images": result_urls,
                "image_count": image_count,
                "width": width,
                "height": height,
            }

        except ProviderTimeoutError as e:
            self.logger.error(f"Poster generation timeout: {e}")
            if poster_id:
                await self._update_poster_status(poster_id, "failed")
            return {"status": "error", "error": "Request timed out. Please retry."}

        except ProviderRateLimitError as e:
            self.logger.error(f"Rate limit exceeded: {e}")
            if poster_id:
                await self._update_poster_status(poster_id, "failed")
            return {"status": "error", "error": "Rate limit exceeded. Please retry later."}

        except ProviderError as e:
            self.logger.error(f"Provider error: {e}")
            if poster_id:
                await self._update_poster_status(poster_id, "failed")
            return {"status": "error", "error": str(e)}

        except Exception as e:
            self.logger.exception(f"Unexpected error during poster generation: {e}")
            if poster_id:
                await self._update_poster_status(poster_id, "failed")
            raise WorkerError(f"Poster generation failed: {e}")

    # ── persistence helpers ─────────────────────────────────────────

    async def _save_poster_image(self, poster_id: int, index: int, image_bytes: bytes) -> str:
        from api.storage.storages import poster_storage

        unique_id = uuid.uuid4().hex[:8]
        filename = f"poster_{poster_id}_{index}_{unique_id}.png"
        url = await poster_storage.upload(image_bytes, filename)
        return url

    async def _update_poster_record(self, poster_id: int, result_urls: list[str]) -> None:
        from api.db.models import EcommercePoster

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(EcommercePoster).where(_condition(EcommercePoster.id == poster_id))
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = "completed"
                record.result_images = result_urls
                await session.commit()
                self.logger.info(f"Updated EcommercePoster {poster_id} status to 'completed'")

    async def _update_poster_status(self, poster_id: int, status: str) -> None:
        from api.db.models import EcommercePoster

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(EcommercePoster).where(_condition(EcommercePoster.id == poster_id))
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = status
                await session.commit()
                self.logger.info(f"Updated EcommercePoster {poster_id} status to '{status}'")


__all__ = ["EcommercePosterHandler"]
