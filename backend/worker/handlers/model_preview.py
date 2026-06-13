import base64
import io
import logging
import re
import uuid
from typing import Any, Literal

from PIL import Image, ImageDraw, ImageFilter

from api.storage.storages import model_preview_storage
from shared.ai.exceptions import AIProviderError
from shared.ai.factory import get_provider_for_image_generation
from shared.ai.schemas import GenerationParams, StyleAnalysis

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)

_DATA_URL_PATTERN = re.compile(r"^data:image/(?P<format>png|jpeg|jpg|webp);base64,(?P<data>.+)$", re.DOTALL)
_DEFAULT_MODEL_PREVIEW_PROMPT = (
    "Create a realistic front-facing fashion model try-on image using the provided filled garment "
    "preview as the exact clothing source. Use a clean straight-on studio catalog pose, front view "
    "only, with the model standing naturally and facing the camera. Preserve the garment silhouette, "
    "fabric print identity, artwork colors, logo placement, and textile pattern. The cloth and printed "
    "pattern must wrap around the body and deform naturally with the model's torso, shoulders, arms, "
    "folds, wrinkles, drape, and slight fabric tension; do not keep the artwork flat or pasted on. Do "
    "not invent new patterns, change the design artwork, use side view, back view, or three-quarter view."
)


def _soft_shadow_alpha(value: int) -> int:
    return min(90, value // 3)


def _decode_image_data_url(data_url: str) -> bytes:
    match = _DATA_URL_PATTERN.match(data_url.strip())
    if not match:
        raise WorkerError("image_data_url must be a PNG, JPEG, or WebP data URL")

    try:
        return base64.b64decode(match.group("data"), validate=True)
    except ValueError as exc:
        raise WorkerError("image_data_url contains invalid base64 data") from exc


def _fit_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return fitted


def _preview_dimensions(image_bytes: bytes) -> tuple[int, int]:
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except OSError:
        return 1024, 1024

    width, height = image.size
    if width <= 0 or height <= 0:
        return 1024, 1024

    scale = min(1024 / width, 1024 / height, 1)
    return max(64, int(width * scale)), max(64, int(height * scale))


def _normalize_png(image_bytes: bytes) -> bytes:
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except OSError as exc:
        raise AIProviderError("AI provider returned an unreadable image") from exc

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


async def _generate_ai_model_preview(garment_bytes: bytes, prompt: str | None) -> bytes | None:
    provider_result = await get_provider_for_image_generation()
    if provider_result is None:
        logger.info("No active image-generation provider configured for model preview")
        return None

    provider, provider_type = provider_result
    width, height = _preview_dimensions(garment_bytes)
    source_b64 = base64.b64encode(garment_bytes).decode("ascii")
    final_prompt = prompt.strip() if prompt and prompt.strip() else _DEFAULT_MODEL_PREVIEW_PROMPT

    style = StyleAnalysis(
        style_description="front-facing fashion model try-on preview generated from a filled garment template",
        color_palette=[],
        pattern_type="full",
        suggested_params={},
    )
    params = GenerationParams(
        style="model_preview_front_view",
        tiling="clamp",
        width=width,
        height=height,
        seed=42,
        init_image_b64=source_b64,
        strength=0.68,
        prompt_override=final_prompt,
    )

    try:
        logger.info("Generating async AI model preview with provider=%s", provider_type)
        return _normalize_png(await provider.generate_pattern(style, params))
    except AIProviderError:
        logger.warning("AI model preview failed; falling back to deterministic compositor", exc_info=True)
        return None


def _compose_model_preview(garment_bytes: bytes) -> bytes:
    try:
        garment = Image.open(io.BytesIO(garment_bytes)).convert("RGBA")
    except OSError as exc:
        raise WorkerError("Unable to read garment preview image") from exc

    canvas_width = 1200
    canvas_height = 1600
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (248, 250, 252, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")

    draw.rectangle((0, 0, canvas_width, canvas_height), fill=(248, 250, 252, 255))
    draw.ellipse((180, 210, 1020, 1540), fill=(226, 232, 240, 120))

    draw.ellipse((500, 120, 700, 320), fill=(214, 219, 227, 255))
    draw.rounded_rectangle((410, 300, 790, 1220), radius=180, fill=(218, 223, 231, 255))
    draw.rounded_rectangle((300, 430, 455, 1120), radius=90, fill=(222, 226, 233, 255))
    draw.rounded_rectangle((745, 430, 900, 1120), radius=90, fill=(222, 226, 233, 255))
    draw.rounded_rectangle((435, 1120, 570, 1480), radius=70, fill=(220, 225, 232, 255))
    draw.rounded_rectangle((630, 1120, 765, 1480), radius=70, fill=(220, 225, 232, 255))

    fitted = _fit_image(garment, 760, 930)
    x = (canvas_width - fitted.width) // 2
    y = 360

    shadow = Image.new("RGBA", fitted.size, (0, 0, 0, 0))
    shadow_alpha = fitted.getchannel("A").filter(ImageFilter.GaussianBlur(18))
    shadow.putalpha(Image.eval(shadow_alpha, _soft_shadow_alpha))
    canvas.alpha_composite(shadow, (x + 24, y + 28))
    canvas.alpha_composite(fitted, (x, y))

    draw.rounded_rectangle((120, 80, 1080, 1520), radius=48, outline=(203, 213, 225, 210), width=4)
    draw.rounded_rectangle((412, 1450, 788, 1510), radius=30, fill=(15, 23, 42, 220))
    draw.text((470, 1468), "Model Preview", fill=(255, 255, 255, 255))

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


class ModelPreviewHandler(TaskHandler):
    handler_name = "model_preview"

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        image_data_url = task_data.get("image_data_url")
        if not isinstance(image_data_url, str) or not image_data_url.strip():
            raise WorkerError("Missing required field: image_data_url")

        template_id = task_data.get("template_id")
        if template_id is not None and not isinstance(template_id, int):
            raise WorkerError("template_id must be an integer when provided")

        prompt = task_data.get("prompt")
        if prompt is not None and not isinstance(prompt, str):
            raise WorkerError("prompt must be a string when provided")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        image_data_url = task_data["image_data_url"]
        template_id = task_data.get("template_id")
        prompt = task_data.get("prompt")
        user_id = task_data.get("user_id")

        garment_bytes = _decode_image_data_url(image_data_url)
        preview_method: Literal["ai", "fallback"] = "ai"
        preview_bytes = await _generate_ai_model_preview(garment_bytes, prompt)
        if preview_bytes is None:
            preview_method = "fallback"
            preview_bytes = _compose_model_preview(garment_bytes)

        user_prefix = f"user_{user_id}_" if isinstance(user_id, int) else ""
        template_suffix = f"template_{template_id}_" if isinstance(template_id, int) else ""
        filename = f"{user_prefix}{template_suffix}{uuid.uuid4().hex}.png"
        preview_url = await model_preview_storage.upload(preview_bytes, filename)
        return {"status": "success", "preview_url": preview_url, "method": preview_method}


__all__ = ["ModelPreviewHandler"]
