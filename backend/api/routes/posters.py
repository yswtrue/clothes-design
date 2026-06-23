"""E-commerce poster generation API endpoints."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import EcommercePoster, Material, User
from shared.task_queue import enqueue_task, get_task_status

router = APIRouter(prefix="/api/posters", tags=["posters"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


class PosterGenerateRequest(BaseModel):
    material_ids: list[int]
    product_type: str
    style: str
    language: str = "en"  # en, zh
    custom_prompt: str | None = None
    image_count: int = 1
    width: int = 1024
    height: int = 768


class PosterGenerateResponse(BaseModel):
    task_id: str
    poster_id: int
    status: str = "pending"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    result: dict | None = None
    error: str | None = None


class PosterHistoryItem(BaseModel):
    id: int
    product_type: str
    style: str
    language: str
    status: str
    image_count: int
    width: int
    height: int
    custom_prompt: str | None = None
    result_images: list | None = None
    created_at: str | None = None


class PosterHistoryResponse(BaseModel):
    items: list[PosterHistoryItem]
    total: int
    page: int
    size: int


def _condition(value: object) -> ColumnElement[bool]:
    return cast(ColumnElement[bool], value)


@router.post("/generate", response_model=PosterGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_poster(
    request: PosterGenerateRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    """Generate e-commerce poster images.

    Uploads multiple material photos and uses AI to generate styled
    e-commerce poster images based on product type, style, and prompt.
    """
    if request.image_count < 1 or request.image_count > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_count must be between 1 and 10",
        )

    if request.width < 64 or request.width > 4096:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="width must be between 64 and 4096",
        )

    if request.height < 64 or request.height > 4096:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="height must be between 64 and 4096",
        )

    # Validate all materials belong to user
    for mid in request.material_ids:
        result = await session.execute(
            select(Material).where(
                _condition(Material.id == mid),
                _condition(Material.uploaded_by == current_user.id),
            )
        )
        material = result.scalar_one_or_none()
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material {mid} not found or access denied",
            )

    if request.language not in ("en", "zh"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="language must be 'en' or 'zh'",
        )

    poster = EcommercePoster(
        user_id=current_user.id,
        product_type=request.product_type,
        style=request.style,
        language=request.language,
        custom_prompt=request.custom_prompt,
        material_ids=request.material_ids,
        image_count=request.image_count,
        width=request.width,
        height=request.height,
        status="generating",
    )
    session.add(poster)
    await session.flush()

    if poster.id is None or current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize poster generation task",
        )

    task_data = {
        "poster_id": poster.id,
        "user_id": current_user.id,
        "material_ids": request.material_ids,
        "product_type": request.product_type,
        "style": request.style,
        "language": request.language,
        "custom_prompt": request.custom_prompt,
        "image_count": request.image_count,
        "width": request.width,
        "height": request.height,
    }

    task_id = await enqueue_task(task_type="ecommerce_poster", user_id=current_user.id, data=task_data)
    await session.commit()

    return PosterGenerateResponse(
        task_id=task_id, poster_id=poster.id, status="pending"
    )


@router.get("", response_model=PosterHistoryResponse)
async def list_posters(
    session: _session_dep,
    current_user: _user_dep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """List user's poster generation history."""
    offset = (page - 1) * size

    # Total count
    count_result = await session.execute(
        select(func.count()).select_from(EcommercePoster).where(
            _condition(EcommercePoster.user_id == current_user.id)
        )
    )
    total = count_result.scalar() or 0

    # Fetch items
    result = await session.execute(
        select(EcommercePoster)
        .where(_condition(EcommercePoster.user_id == current_user.id))
        .order_by(desc(EcommercePoster.created_at))
        .offset(offset)
        .limit(size)
    )
    posters = result.scalars().all()

    items = [
        PosterHistoryItem(
            id=p.id,
            product_type=p.product_type,
            style=p.style,
            language=p.language,
            status=p.status,
            image_count=p.image_count,
            width=p.width,
            height=p.height,
            custom_prompt=p.custom_prompt,
            result_images=p.result_images,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in posters
    ]

    return PosterHistoryResponse(items=items, total=total, page=page, size=size)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status_endpoint(
    task_id: str,
    session: _session_dep,
    current_user: _user_dep,
):
    """Get poster generation task status and result.

    Args:
        task_id: Task ID to query
        session: Database session
        current_user: Authenticated user

    Returns:
        Task status and result if completed

    Raises:
        HTTPException: If task not found
    """
    task_status = await get_task_status(task_id)

    if not task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Verify task belongs to user
    if task_status.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return TaskStatusResponse(
        task_id=task_id,
        status=task_status.status,
        result=task_status.result,
        error=task_status.error,
    )
