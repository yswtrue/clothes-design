"""Export API endpoints for high-resolution TIF CMYK exports."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import GeneratedDesign, Material, User
from api.storage.storages import upscaled_storage, vector_storage
from shared.task_queue import (
    enqueue_task,
    get_task_status,
    acquire_export_slot,
    get_export_slot_count,
    EXPORT_MAX_CONCURRENT,
)

router = APIRouter(prefix="/api/export", tags=["export"])

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


class ExportResponse(BaseModel):
    task_id: str | None = None
    generated_design_id: int
    status: str = "pending"
    download_url: str | None = None
    upscaled_url: str | None = None


class ExportStatusResponse(BaseModel):
    task_id: str
    generated_design_id: int | None = None
    status: str
    progress: int = 0
    current_step: str | None = None
    download_url: str | None = None
    upscaled_url: str | None = None
    error: str | None = None


@router.post(
    "/generated-designs/{generated_design_id}",
    response_model=ExportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_export(
    generated_design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(GeneratedDesign).where(GeneratedDesign.id == generated_design_id)
    )
    generated_design = result.scalar_one_or_none()

    if not generated_design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated design not found",
        )

    material_result = await session.execute(
        select(Material).where(
            Material.id == generated_design.material_id,
            Material.uploaded_by == current_user.id,
        )
    )
    material = material_result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if not generated_design.image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generated design has no image to export",
        )

    if generated_design.status not in ("completed", "exported"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot export design with status: {generated_design.status}",
        )

    existing_vector = _get_file_path(generated_design.vector_svg)
    existing_upscaled = _get_file_path(generated_design.upscaled_image)
    if existing_vector and existing_upscaled:
        return ExportResponse(
            task_id=None,
            generated_design_id=generated_design_id,
            status="exported",
            download_url=vector_storage.get_url(existing_vector),
            upscaled_url=upscaled_storage.get_url(existing_upscaled),
        )

    acquired = await acquire_export_slot()
    if not acquired:
        current_count = await get_export_slot_count()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Export queue full ({current_count}/{EXPORT_MAX_CONCURRENT}). Please try again later.",
        )

    task_data = {
        "generated_design_id": generated_design_id,
        "target_resolution": 12000,
        "color_space": "CMYK",
        "format": "tif",
    }

    task_id = await enqueue_task(
        task_type="export_pattern",
        user_id=current_user.id,
        data=task_data,
    )

    return ExportResponse(
        task_id=task_id,
        generated_design_id=generated_design_id,
        status="pending",
    )


@router.get("/tasks/{task_id}", response_model=ExportStatusResponse)
async def get_export_status(
    task_id: str,
    session: _session_dep,
    current_user: _user_dep,
):
    task_status = await get_task_status(task_id)

    if not task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task_status.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    generated_design_id = task_status.data.get("generated_design_id") if task_status.data else None
    current_step = None
    progress = 0
    download_url = None
    upscaled_url = None

    status_mapping = {
        "pending": "pending",
        "processing": "processing",
        "completed": "exported",
        "failed": "failed",
    }
    export_status = status_mapping.get(task_status.status, task_status.status)

    if task_status.status == "processing":
        step_info = task_status.data.get("current_step") if task_status.data else None
        if step_info == "vectorizing":
            current_step = "vectorizing"
            progress = 60
        else:
            current_step = "upscaling"
            progress = 25

    elif task_status.status == "completed":
        current_step = "complete"
        progress = 100
        if task_status.result:
            download_url = task_status.result.get("download_url")
            upscaled_url = task_status.result.get("upscaled_url")

    return ExportStatusResponse(
        task_id=task_id,
        generated_design_id=generated_design_id,
        status=export_status,
        progress=progress,
        current_step=current_step,
        download_url=download_url,
        upscaled_url=upscaled_url,
        error=task_status.error,
    )
