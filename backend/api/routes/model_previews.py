"""Model preview generation API endpoints."""

import base64
import io
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

router = APIRouter(prefix="/api/model-previews", tags=["model-previews"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]

_DATA_URL_PATTERN = re.compile(r"^data:image/(?P<format>png|jpeg|jpg|webp);base64,(?P<data>.+)$", re.DOTALL)


def _soft_shadow_alpha(value: int) -> int:
    return min(90, value // 3)


class ModelPreviewRequest(BaseModel):
    image_data_url: str = Field(..., description="Filled garment preview as a PNG/JPEG/WebP data URL")
    template_id: int | None = Field(default=None, description="Optional source template id for traceability")
    prompt: str | None = Field(default=None, max_length=500, description="Optional model preview prompt")


class ModelPreviewResponse(BaseModel):
    preview_url: str
    status: Literal["completed"] = "completed"


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
    preview_bytes = _compose_model_preview(garment_bytes)
    template_suffix = f"template_{request.template_id}_" if request.template_id is not None else ""
    filename = f"user_{current_user.id}_{template_suffix}{uuid.uuid4().hex}.png"
    preview_url = await model_preview_storage.upload(preview_bytes, filename)
    return ModelPreviewResponse(preview_url=preview_url)
