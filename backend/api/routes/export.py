"""Export API endpoints for high-resolution SVG and TIF CMYK exports."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import GeneratedDesign, Material, User
from api.storage.storages import (
    output_tif_storage,
    upscaled_storage,
    vector_storage,
)
from shared.task_queue import (
    enqueue_task,
    get_task_status,
    acquire_export_slot,
    get_export_slot_count,
    EXPORT_MAX_CONCURRENT,
)

router = APIRouter(prefix="/api/export", tags=["export"])

ExportFormat = Literal["svg", "tif"]

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
    format: ExportFormat
    status: str = "pending"
    download_url: str | None = None
    upscaled_url: str | None = None


class ExportStatusResponse(BaseModel):
    task_id: str
    generated_design_id: int | None = None
    format: ExportFormat | None = None
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
    format: ExportFormat = Query(default="svg", description="Export format: svg or tif"),
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
    existing_tif = _get_file_path(generated_design.export_tif)

    if format == "svg" and existing_vector and existing_upscaled:
        return ExportResponse(
            task_id=None,
            generated_design_id=generated_design_id,
            format=format,
            status="exported",
            download_url=vector_storage.get_url(existing_vector),
            upscaled_url=upscaled_storage.get_url(existing_upscaled),
        )

    if format == "tif" and existing_tif and existing_upscaled:
        return ExportResponse(
            task_id=None,
            generated_design_id=generated_design_id,
            format=format,
            status="exported",
            download_url=output_tif_storage.get_url(existing_tif),
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
        "format": format,
    }

    task_id = await enqueue_task(
        task_type="export_pattern",
        user_id=current_user.id,
        data=task_data,
    )

    return ExportResponse(
        task_id=task_id,
        generated_design_id=generated_design_id,
        format=format,
        status="pending",
    )


class MaterialExportResponse(BaseModel):
    task_id: str | None = None
    material_id: int
    format: ExportFormat
    status: str = "pending"
    download_url: str | None = None


@router.post(
    "/materials/{material_id}",
    response_model=MaterialExportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def export_material(
    material_id: int,
    session: _session_dep,
    current_user: _user_dep,
    format: ExportFormat = Query(default="tif", description="Export format (only tif supported)"),
    target_resolution: int = Query(default=12000, ge=1024, le=16384, description="Target resolution in pixels"),
):
    if format != "tif":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only TIF format is supported for material direct export",
        )

    result = await session.execute(
        select(Material).where(
            Material.id == material_id,
            Material.uploaded_by == current_user.id,
        )
    )
    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )

    if not material.file or not material.stored_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material has no file to export",
        )

    # Check for cached export — if already exported via this endpoint, return immediately
    existing_tif = _get_file_path(material.export_tif) if hasattr(material, "export_tif") else None
    if existing_tif:
        return MaterialExportResponse(
            task_id=None,
            material_id=material_id,
            format=format,
            status="exported",
            download_url=output_tif_storage.get_url(existing_tif),
        )

    acquired = await acquire_export_slot()
    if not acquired:
        current_count = await get_export_slot_count()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Export queue full ({current_count}/{EXPORT_MAX_CONCURRENT}). Please try again later.",
        )

    task_data = {
        "material_id": material_id,
        "stored_filename": material.stored_filename,
        "target_resolution": target_resolution,
        "color_space": "CMYK",
        "dpi": 300,
    }

    task_id = await enqueue_task(
        task_type="export_material",
        user_id=current_user.id,
        data=task_data,
    )

    return MaterialExportResponse(
        task_id=task_id,
        material_id=material_id,
        format=format,
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
    mat_id = task_status.data.get("material_id") if task_status.data else None
    design_id = generated_design_id or mat_id
    export_format = task_status.data.get("format", "tif") if task_status.data else "tif"
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
        elif step_info == "converting":
            current_step = "converting"
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
        generated_design_id=design_id,
        format=export_format,
        status=export_status,
        progress=progress,
        current_step=current_step,
        download_url=download_url,
        upscaled_url=upscaled_url,
        error=task_status.error,
    )
