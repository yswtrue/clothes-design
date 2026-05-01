from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import GeneratedDesign, Material, User
from api.materials.schemas import MaterialMeta
from api.storage.storages import generated_image_storage, thumbnail_storage
from shared.task_queue.celery_integration import enqueue_task, get_task_status

router = APIRouter(prefix="/api/generate", tags=["variants"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


def _get_file_path(file_obj) -> str | None:
    if file_obj is None:
        return None
    if hasattr(file_obj, "path"):
        return file_obj.path
    if isinstance(file_obj, str):
        return file_obj
    return str(file_obj) if file_obj else None


class GenerateVariantsRequest(BaseModel):
    material_id: int
    count: int = 4
    start_index: int = 0
    prompt_override: str | None = None


class GenerateVariantsResponse(BaseModel):
    task_id: str
    material_id: int
    status: str = "pending"


class VariantResponse(BaseModel):
    id: int
    material_id: int
    image_url: str | None = None
    thumbnail_url: str | None = None
    variant_index: int
    is_selected: bool
    created_at: str | None = None

    class Config:
        from_attributes = True


class VariantsListResponse(BaseModel):
    material_id: int
    variants: list[VariantResponse]
    total: int


class SelectVariantRequest(BaseModel):
    variant_id: int


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None


@router.post("/variants", response_model=GenerateVariantsResponse, status_code=status.HTTP_201_CREATED)
async def generate_variants(
    request: GenerateVariantsRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(Material).where(
            Material.id == request.material_id,
            Material.uploaded_by == current_user.id
        )
    )
    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found or access denied",
        )

    style_analysis = None
    if material.meta:
        meta = MaterialMeta(**material.meta)
        if meta.style_analysis:
            style_analysis = meta.style_analysis

    prompt = request.prompt_override
    if not prompt and style_analysis:
        prompt = style_analysis.style_description

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material has no style analysis and no prompt provided",
        )

    task_data = {
        "material_id": request.material_id,
        "user_id": current_user.id,
        "count": min(request.count, 8),
        "start_index": request.start_index,
        "prompt": prompt,
        "style_analysis": style_analysis.model_dump() if style_analysis else None,
    }

    task_id = await enqueue_task(
        task_type="generate_variants",
        user_id=current_user.id,
        data=task_data,
    )

    return GenerateVariantsResponse(
        task_id=task_id,
        material_id=request.material_id,
        status="pending",
    )


@router.get("/variants/{material_id}", response_model=VariantsListResponse)
async def get_variants(
    material_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(Material).where(
            Material.id == material_id,
            Material.uploaded_by == current_user.id
        )
    )
    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found or access denied",
        )

    variants_result = await session.execute(
        select(GeneratedDesign)
        .where(GeneratedDesign.material_id == material_id)
        .order_by(GeneratedDesign.variant_index)
    )
    variants = variants_result.scalars().all()

    variant_responses = []
    for v in variants:
        image_path = _get_file_path(v.image)
        thumb_path = _get_file_path(v.thumbnail)
        image_url = generated_image_storage.get_url(image_path) if image_path else None
        thumbnail_url = thumbnail_storage.get_url(thumb_path) if thumb_path else None
        variant_responses.append(VariantResponse(
            id=v.id,
            material_id=v.material_id,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            variant_index=v.variant_index,
            is_selected=bool(v.is_selected),
            created_at=v.created_at.isoformat() if v.created_at else None,
        ))

    return VariantsListResponse(
        material_id=material_id,
        variants=variant_responses,
        total=len(variant_responses),
    )


@router.post("/variants/{material_id}/select", response_model=VariantResponse)
async def select_variant(
    material_id: int,
    request: SelectVariantRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(Material).where(
            Material.id == material_id,
            Material.uploaded_by == current_user.id
        )
    )
    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found or access denied",
        )

    variant_result = await session.execute(
        select(GeneratedDesign).where(
            GeneratedDesign.id == request.variant_id,
            GeneratedDesign.material_id == material_id
        )
    )
    variant = variant_result.scalar_one_or_none()

    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variant not found",
        )

    await session.execute(
        select(GeneratedDesign)
        .where(GeneratedDesign.material_id == material_id)
        .execution_options(synchronize_session="fetch")
    )
    for gd in (await session.execute(
        select(GeneratedDesign).where(GeneratedDesign.material_id == material_id)
    )).scalars().all():
        gd.is_selected = 0

    variant.is_selected = 1
    await session.commit()
    await session.refresh(variant)

    image_path = _get_file_path(variant.image)
    thumb_path = _get_file_path(variant.thumbnail)
    image_url = generated_image_storage.get_url(image_path) if image_path else None
    thumbnail_url = thumbnail_storage.get_url(thumb_path) if thumb_path else None

    return VariantResponse(
        id=variant.id,
        material_id=variant.material_id,
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        variant_index=variant.variant_index,
        is_selected=bool(variant.is_selected),
        created_at=variant.created_at.isoformat() if variant.created_at else None,
    )


@router.get("/variants/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_variant_task_status(
    task_id: str,
    session: _session_dep,
    current_user: _user_dep,
):
    task_status_obj = await get_task_status(task_id)

    if not task_status_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task_status_obj.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return TaskStatusResponse(
        task_id=task_id,
        status=task_status_obj.status,
        result=task_status_obj.result,
        error=task_status_obj.error,
    )
