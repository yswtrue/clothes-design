"""Model preview generation API endpoints."""

import base64
import io
import logging
import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image, ImageDraw, ImageFilter
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import User
from api.storage.storages import model_preview_storage
from shared.ai.exceptions import AIProviderError
from shared.ai.factory import get_provider_for_image_generation
from shared.ai.schemas import GenerationParams, StyleAnalysis

router = APIRouter(prefix="/api/model-previews", tags=["model-previews"])
logger = logging.getLogger(__name__)

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]

_DATA_URL_PATTERN = re.compile(r"^data:image/(?P<format>png|jpeg|jpg|webp);base64,(?P<data>.+)$", re.DOTALL)
_DEFAULT_MODEL_PREVIEW_PROMPT = (
    "Create a realistic fashion catalog try-on image using the provided garment preview as the "
    "source clothing design. Place the garment on a clean full-body studio model or mannequin, "
    "preserving the fabric print, colors, layout, and silhouette as much as possible. Use a neutral "
    "studio background, natural lighting, high quality product photography, and do not invent new "
    "patterns or change the design artwork."
)


def _soft_shadow_alpha(value: int) -> int:
    return min(90, value // 3)


class ModelPreviewRequest(BaseModel):
    image_data_url: str = Field(..., description="Filled garment preview as a PNG/JPEG/WebP data URL")
    template_id: int | None = Field(default=None, description="Optional source template id for traceability")
    prompt: str | None = Field(default=None, max_length=500, description="Optional model preview prompt")


class ModelPreviewResponse(BaseModel):
    preview_url: str
    status: Literal["completed"] = "completed"
    method: Literal["ai", "fallback"] = "fallback"


def _decode_image_data_url(data_url: str) -> bytes:
    match = _DATA_URL_PATTERN.match(data_url.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_data_url must be a PNG, JPEG, or WebP data URL",
        )

    try:
        return base64.b64decode(match.group("data"), validate=True)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_data_url contains invalid base64 data",
        ) from exc


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
        style_description="fashion model try-on preview generated from a filled garment template",
        color_palette=[],
        pattern_type="full",
        suggested_params={},
    )
    params = GenerationParams(
        style="model_preview",
        tiling="clamp",
        width=width,
        height=height,
        seed=42,
        init_image_b64=source_b64,
        strength=0.55,
        prompt_override=final_prompt,
    )

    try:
        logger.info("Generating AI model preview with provider=%s", provider_type)
        return _normalize_png(await provider.generate_pattern(style, params))
    except AIProviderError:
        logger.warning("AI model preview failed; falling back to deterministic compositor", exc_info=True)
        return None


def _compose_model_preview(garment_bytes: bytes) -> bytes:
    try:
        garment = Image.open(io.BytesIO(garment_bytes)).convert("RGBA")
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to read garment preview image",
        ) from exc

    canvas_width = 1200
    canvas_height = 1600
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (248, 250, 252, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Soft studio background.
    draw.rectangle((0, 0, canvas_width, canvas_height), fill=(248, 250, 252, 255))
    draw.ellipse((180, 210, 1020, 1540), fill=(226, 232, 240, 120))

    # Minimal mannequin silhouette behind the garment preview.
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

    # Frame and label for clarity.
    draw.rounded_rectangle((120, 80, 1080, 1520), radius=48, outline=(203, 213, 225, 210), width=4)
    draw.rounded_rectangle((412, 1450, 788, 1510), radius=30, fill=(15, 23, 42, 220))
    draw.text((470, 1468), "Model Preview", fill=(255, 255, 255, 255))

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


@router.post("", response_model=ModelPreviewResponse, status_code=status.HTTP_201_CREATED)
async def create_model_preview(
    request: ModelPreviewRequest,
    session: _session_dep,
    current_user: _user_dep,
) -> ModelPreviewResponse:
    del session
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Current user is incomplete",
        )

    garment_bytes = _decode_image_data_url(request.image_data_url)
    preview_method: Literal["ai", "fallback"] = "ai"
    preview_bytes = await _generate_ai_model_preview(garment_bytes, request.prompt)
    if preview_bytes is None:
        preview_method = "fallback"
        preview_bytes = _compose_model_preview(garment_bytes)

    template_suffix = f"template_{request.template_id}_" if request.template_id is not None else ""
    filename = f"user_{current_user.id}_{template_suffix}{uuid.uuid4().hex}.png"
    preview_url = await model_preview_storage.upload(preview_bytes, filename)
    return ModelPreviewResponse(preview_url=preview_url, method=preview_method)
