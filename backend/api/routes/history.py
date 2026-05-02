from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import GeneratedDesign, Material, User
from api.storage.storages import (
    generated_image_storage,
    material_storage,
    thumbnail_storage,
    upscaled_storage,
    vector_storage,
)

router = APIRouter(prefix="/api/history", tags=["history"])

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


class GeneratedDesignResponse(BaseModel):
    id: int
    material_id: int
    status: str
    image_url: str | None = None
    thumbnail_url: str | None = None
    upscaled_url: str | None = None
    vector_url: str | None = None
    variant_index: int
    prompt_used: str | None = None
    seed: int | None = None
    is_selected: bool
    created_at: str | None = None
    exported_at: str | None = None


class MaterialWithDesignsResponse(BaseModel):
    id: int
    original_filename: str | None = None
    thumbnail_url: str | None = None
    created_at: str | None = None
    designs_count: int
    designs: list[GeneratedDesignResponse]


class PaginatedHistoryResponse(BaseModel):
    items: list[MaterialWithDesignsResponse]
    total: int
    page: int
    size: int
    pages: int


@router.get("", response_model=PaginatedHistoryResponse)
async def get_history(
    page: int = 1,
    size: int = 10,
    session: _session_dep = None,
    current_user: _user_dep = None,
):
    offset = (page - 1) * size

    count_result = await session.execute(
        select(func.count(Material.id)).where(Material.uploaded_by == current_user.id)
    )
    total = count_result.scalar() or 0

    materials_result = await session.execute(
        select(Material)
        .where(Material.uploaded_by == current_user.id)
        .order_by(Material.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    materials = materials_result.scalars().all()

    items = []
    for material in materials:
        designs_result = await session.execute(
            select(GeneratedDesign)
            .where(GeneratedDesign.material_id == material.id)
            .order_by(GeneratedDesign.created_at.desc())
        )
        designs = designs_result.scalars().all()

        material_thumb = None
        if material.stored_filename:
            material_thumb = material_storage.get_url(material.stored_filename)

        design_responses = []
        for d in designs:
            image_path = _get_file_path(d.image)
            thumb_path = _get_file_path(d.thumbnail)
            upscaled_path = _get_file_path(d.upscaled_image)
            vector_path = _get_file_path(d.vector_svg)

            design_responses.append(GeneratedDesignResponse(
                id=d.id,
                material_id=d.material_id,
                status=d.status,
                image_url=generated_image_storage.get_url(image_path) if image_path else None,
                thumbnail_url=thumbnail_storage.get_url(thumb_path) if thumb_path else None,
                upscaled_url=upscaled_storage.get_url(upscaled_path) if upscaled_path else None,
                vector_url=vector_storage.get_url(vector_path) if vector_path else None,
                variant_index=d.variant_index,
                prompt_used=d.prompt_used,
                seed=d.seed,
                is_selected=bool(d.is_selected),
                created_at=d.created_at.isoformat() if d.created_at else None,
                exported_at=d.exported_at.isoformat() if d.exported_at else None,
            ))

        items.append(MaterialWithDesignsResponse(
            id=material.id,
            original_filename=material.original_filename,
            thumbnail_url=material_thumb,
            created_at=material.created_at.isoformat() if material.created_at else None,
            designs_count=len(design_responses),
            designs=design_responses,
        ))

    pages = (total + size - 1) // size if size > 0 else 0

    return PaginatedHistoryResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{generated_design_id}", response_model=GeneratedDesignResponse)
async def get_generated_design(
    generated_design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(GeneratedDesign).where(GeneratedDesign.id == generated_design_id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated design not found",
        )

    material_result = await session.execute(
        select(Material).where(
            Material.id == design.material_id,
            Material.uploaded_by == current_user.id,
        )
    )
    if not material_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    image_path = _get_file_path(design.image)
    thumb_path = _get_file_path(design.thumbnail)
    upscaled_path = _get_file_path(design.upscaled_image)
    vector_path = _get_file_path(design.vector_svg)

    return GeneratedDesignResponse(
        id=design.id,
        material_id=design.material_id,
        status=design.status,
        image_url=generated_image_storage.get_url(image_path) if image_path else None,
        thumbnail_url=thumbnail_storage.get_url(thumb_path) if thumb_path else None,
        upscaled_url=upscaled_storage.get_url(upscaled_path) if upscaled_path else None,
        vector_url=vector_storage.get_url(vector_path) if vector_path else None,
        variant_index=design.variant_index,
        prompt_used=design.prompt_used,
        seed=design.seed,
        is_selected=bool(design.is_selected),
        created_at=design.created_at.isoformat() if design.created_at else None,
        exported_at=design.exported_at.isoformat() if design.exported_at else None,
    )


@router.delete("/{generated_design_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generated_design(
    generated_design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(GeneratedDesign).where(GeneratedDesign.id == generated_design_id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated design not found",
        )

    material_result = await session.execute(
        select(Material).where(
            Material.id == design.material_id,
            Material.uploaded_by == current_user.id,
        )
    )
    if not material_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    design.soft_delete()
    await session.commit()
