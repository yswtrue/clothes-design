import io
import json
import uuid
from typing import Annotated, Protocol, runtime_checkable

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi_pagination import Params, create_page
from fastapi_pagination.ext.sqlalchemy import paginate
from PIL import Image, ImageDraw
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import GeneratedDesign, Material, PrjTemplate, User
from api.rbac import require_permission
from api.storage.storages import (
    generated_image_storage,
    preview_storage,
    prj_storage,
    template_preview_storage,
    upscaled_storage,
)

router = APIRouter(prefix="/api/prj-templates", tags=["prj-templates"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]
_admin_dep = Annotated[User, Depends(require_permission("admin:manage"))]


class PrjTemplateResponse(BaseModel):
    id: int
    name: str
    category: str
    preview_url: str | None = None
    is_builtin: bool

    class Config:
        from_attributes = True


class PrjTemplateDetailResponse(PrjTemplateResponse):
    prj_path: str | None = None
    regions: dict | None = None


class PrjTemplatePreviewRequest(BaseModel):
    generated_design_id: int


class PrjTemplatePreviewResponse(BaseModel):
    template_id: int
    generated_design_id: int
    preview_url: str


Point = tuple[int, int]
Rectangle = tuple[int, int, int, int]
Region = dict[str, object]


@runtime_checkable
class _PathLikeFile(Protocol):
    path: str


def _get_file_path(file_obj: object) -> str | None:
    if file_obj is None:
        return None
    if isinstance(file_obj, _PathLikeFile):
        return str(file_obj.path) if file_obj.path else None
    if isinstance(file_obj, str):
        return file_obj
    return str(file_obj) if file_obj else None


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _regions_from_payload(payload: object) -> list[Region]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("regions", "areas", "pieces"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return [payload]


def _rectangle_from_region(region: Region, canvas_size: tuple[int, int]) -> Rectangle | None:
    x = _as_int(region.get("x"))
    y = _as_int(region.get("y"))
    width = _as_int(region.get("width", region.get("w")))
    height = _as_int(region.get("height", region.get("h")))

    if x is None or y is None or width is None or height is None:
        return None
    if width <= 0 or height <= 0:
        return None

    canvas_width, canvas_height = canvas_size
    left = max(0, min(x, canvas_width))
    top = max(0, min(y, canvas_height))
    right = max(left, min(x + width, canvas_width))
    bottom = max(top, min(y + height, canvas_height))
    if right <= left or bottom <= top:
        return None
    return (left, top, right, bottom)


def _point_from_payload(payload: object) -> Point | None:
    if isinstance(payload, dict):
        x = _as_int(payload.get("x"))
        y = _as_int(payload.get("y"))
        if x is not None and y is not None:
            return (x, y)
    if isinstance(payload, list | tuple) and len(payload) >= 2:
        x = _as_int(payload[0])
        y = _as_int(payload[1])
        if x is not None and y is not None:
            return (x, y)
    return None


def _polygon_from_region(region: Region, canvas_size: tuple[int, int]) -> list[Point]:
    raw_points = region.get("points", region.get("polygon"))
    if not isinstance(raw_points, list):
        return []

    canvas_width, canvas_height = canvas_size
    points: list[Point] = []
    for raw_point in raw_points:
        point = _point_from_payload(raw_point)
        if point is None:
            continue
        x, y = point
        points.append((max(0, min(x, canvas_width)), max(0, min(y, canvas_height))))
    return points if len(points) >= 3 else []


def _tile_pattern(pattern: Image.Image, canvas_size: tuple[int, int]) -> Image.Image:
    canvas_width, canvas_height = canvas_size
    tiled = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    if pattern.width <= 0 or pattern.height <= 0:
        return tiled

    for y in range(0, canvas_height, pattern.height):
        for x in range(0, canvas_width, pattern.width):
            tiled.alpha_composite(pattern, (x, y))
    return tiled


def _compose_template_preview(
    template_bytes: bytes,
    pattern_bytes: bytes,
    regions_payload: object,
) -> bytes:
    with Image.open(io.BytesIO(template_bytes)) as template_image:
        base = template_image.convert("RGBA")

    with Image.open(io.BytesIO(pattern_bytes)) as pattern_image:
        pattern = pattern_image.convert("RGBA")

    if pattern.width > base.width or pattern.height > base.height:
        pattern.thumbnail(base.size, Image.Resampling.LANCZOS)

    regions = _regions_from_payload(regions_payload)
    if not regions:
        regions = [Region({"x": 0, "y": 0, "width": base.width, "height": base.height})]

    filled = base.copy()
    tiled_pattern = _tile_pattern(pattern, base.size)

    for region in regions:
        mask = Image.new("L", base.size, 0)
        draw = ImageDraw.Draw(mask)
        polygon = _polygon_from_region(region, base.size)
        if polygon:
            draw.polygon(polygon, fill=255)
        else:
            rectangle = _rectangle_from_region(region, base.size)
            if rectangle is None:
                continue
            draw.rectangle(rectangle, fill=255)
        filled.paste(tiled_pattern, (0, 0), mask)

    output = io.BytesIO()
    filled.save(output, format="PNG")
    return output.getvalue()


@router.get("")
async def list_prj_templates(
    session: _session_dep,
    current_user: _user_dep,
    params: Params = Depends(),
    category: str | None = Query(None),
):
    query = select(PrjTemplate)

    if category:
        query = query.where(PrjTemplate.category == category)  # type: ignore[arg-type]

    query = query.order_by(PrjTemplate.name)

    page = await paginate(session, query, params)

    items_with_urls = []
    for item in page.items:
        preview_url = preview_storage.get_url(str(item.preview_image)) if item.preview_image else None
        items_with_urls.append(PrjTemplateResponse(
            id=item.id,
            name=item.name,
            category=item.category,
            preview_url=preview_url,
            is_builtin=bool(item.is_builtin),
        ))

    return create_page(items_with_urls, total=page.total, params=params)


@router.get("/categories")
async def list_categories(
    session: _session_dep,
    current_user: _user_dep,
) -> list[str]:
    result = await session.execute(
        select(PrjTemplate.category).distinct().order_by(PrjTemplate.category)  # type: ignore[arg-type]
    )
    return [row[0] for row in result.all()]


@router.get("/{template_id}", response_model=PrjTemplateDetailResponse)
async def get_prj_template(
    template_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(PrjTemplate).where(PrjTemplate.id == template_id)  # type: ignore[arg-type]
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    preview_url = preview_storage.get_url(str(template.preview_image)) if template.preview_image else None
    prj_path = prj_storage.get_url(str(template.prj_file)) if template.prj_file else None

    return PrjTemplateDetailResponse(
        id=template.id,  # type: ignore[arg-type]
        name=template.name,
        category=template.category,
        prj_path=prj_path,
        preview_url=preview_url,
        regions=template.regions,
        is_builtin=bool(template.is_builtin),
    )


@router.post("", response_model=PrjTemplateDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_prj_template(
    session: _session_dep,
    admin_user: _admin_dep,
    name: str = Form(...),
    category: str = Form(...),
    prj_file: UploadFile = File(...),
    preview_file: UploadFile | None = File(None),
    regions: str | None = Form(None),
):
    regions_dict = None
    if regions:
        try:
            regions_dict = json.loads(regions)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in regions field",
            ) from exc

    template = PrjTemplate(
        name=name,
        category=category,
        prj_file=prj_file,
        preview_image=preview_file,
        regions=regions_dict,
        is_builtin=1,
    )

    session.add(template)
    await session.commit()
    await session.refresh(template)

    preview_url = preview_storage.get_url(str(template.preview_image)) if template.preview_image else None
    prj_path = prj_storage.get_url(str(template.prj_file)) if template.prj_file else None

    return PrjTemplateDetailResponse(
        id=template.id,  # type: ignore[arg-type]
        name=template.name,
        category=template.category,
        prj_path=prj_path,
        preview_url=preview_url,
        regions=template.regions,
        is_builtin=bool(template.is_builtin),
    )


@router.post("/{template_id}/preview", response_model=PrjTemplatePreviewResponse)
async def create_template_preview(
    template_id: int,
    request: PrjTemplatePreviewRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    template_result = await session.execute(
        select(PrjTemplate).where(col(PrjTemplate.id) == template_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    design_result = await session.execute(
        select(GeneratedDesign).where(col(GeneratedDesign.id) == request.generated_design_id)
    )
    design = design_result.scalar_one_or_none()
    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated design not found",
        )

    material_result = await session.execute(
        select(Material).where(
            col(Material.id) == design.material_id,
            col(Material.uploaded_by) == current_user.id,
        )
    )
    if not material_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    template_image_path = _get_file_path(template.preview_image)
    if not template_image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template preview image is required",
        )

    pattern_image_path = _get_file_path(design.upscaled_image) or _get_file_path(design.image)
    if not pattern_image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generated design image is required",
        )

    template_bytes = await preview_storage.download(template_image_path)
    pattern_storage = upscaled_storage if _get_file_path(design.upscaled_image) else generated_image_storage
    pattern_bytes = await pattern_storage.download(pattern_image_path)

    try:
        preview_bytes = _compose_template_preview(
            template_bytes=template_bytes,
            pattern_bytes=pattern_bytes,
            regions_payload=template.regions,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to compose template preview",
        ) from exc

    filename = f"template_{template.id}_design_{design.id}_{uuid.uuid4().hex}.png"
    preview_url = await template_preview_storage.upload(preview_bytes, filename)

    if template.id is None or design.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Preview source record is incomplete",
        )

    return PrjTemplatePreviewResponse(
        template_id=template.id,
        generated_design_id=design.id,
        preview_url=preview_url,
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prj_template(
    template_id: int,
    session: _session_dep,
    admin_user: _admin_dep,
):
    result = await session.execute(
        select(PrjTemplate).where(PrjTemplate.id == template_id)  # type: ignore[arg-type]
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    template.soft_delete()
    await session.commit()
