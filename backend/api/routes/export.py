"""Export API endpoints for high-resolution TIF CMYK exports."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import GeneratedDesign, Material, User
from api.storage.storages import (
    output_tif_storage,
    upscaled_storage,
)
from shared.export_settings import (
    ExportFormat,
    export_settings_match,
    get_export_settings,
    normalize_content_type,
)
from shared.task_queue import (
    EXPORT_MAX_CONCURRENT,
    acquire_export_slot,
    enqueue_task,
    get_export_slot_count,
    get_task_status,
)
from shared.task_queue.redis_client import get_redis_client

router = APIRouter(prefix="/api/export", tags=["export"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


def _require_user_id(user: User) -> int:
    user_id = user.id
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user has no ID",
        )
    return user_id


def _get_file_path(file_obj) -> str | None:
    if file_obj is None:
        return None
    if hasattr(file_obj, "path"):
        return file_obj.path
    if isinstance(file_obj, str):
        return file_obj
    return str(file_obj) if file_obj else None


def _material_export_dedup_key(
    *,
    material_id: int,
    target_resolution: int,
    color_space: str,
    content_type: str,
    sharpen: bool,
) -> str:
    return (
        f"mat_export:{material_id}:tif:{target_resolution}:"
        f"{color_space}:{normalize_content_type(content_type)}:{int(bool(sharpen))}"
    )


class ExportResponse(BaseModel):
    task_id: str | None = None
    generated_design_id: int
    format: ExportFormat
    status: str = "pending"
    download_url: str | None = None
    upscaled_url: str | None = None
    content_type: str = "pattern"
    sharpen: bool = False
    target_resolution: int = 12000


class ExportStatusResponse(BaseModel):
    task_id: str
    generated_design_id: int | None = None
    format: ExportFormat | None = None
    status: str
    progress: int = 0
    current_step: str | None = None
    download_url: str | None = None
    upscaled_url: str | None = None
    content_type: str | None = None
    sharpen: bool | None = None
    target_resolution: int | None = None
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
    export_format: ExportFormat = Query(default="tif", alias="format", description="Export format (only tif supported)"),
    target_resolution: int = Query(default=12000, ge=1024, le=16384, description="Target resolution in pixels"),
    content_type: str = Query(default="pattern", pattern="^(line-art|pattern)$", description="Content type: line-art for sharp-edged designs, pattern for textured/photographic"),
    sharpen: bool = Query(default=False, description="Apply post-upscale sharpening"),
):
    user_id = _require_user_id(current_user)

    result = await session.execute(
        select(GeneratedDesign).where(col(GeneratedDesign.id) == generated_design_id)
    )
    generated_design = result.scalar_one_or_none()

    if not generated_design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated design not found",
        )

    material_result = await session.execute(
        select(Material).where(
            col(Material.id) == generated_design.material_id,
            col(Material.uploaded_by) == user_id,
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

    existing_tif = _get_file_path(generated_design.export_tif)
    export_settings = get_export_settings(generated_design.generation_params, export_format)
    settings_match = export_settings_match(
        export_settings,
        export_format=export_format,
        target_resolution=target_resolution,
        color_space="CMYK",
        content_type=content_type,
        sharpen=sharpen,
    )
    settings_upscaled = export_settings.get("upscaled_filename") if export_settings else None

    if export_format == "tif" and existing_tif and settings_match and settings_upscaled:
        return ExportResponse(
            task_id=None,
            generated_design_id=generated_design_id,
            format=export_format,
            status="exported",
            download_url=output_tif_storage.get_url(existing_tif),
            upscaled_url=upscaled_storage.get_url(settings_upscaled),
            content_type=normalize_content_type(content_type),
            sharpen=sharpen,
            target_resolution=target_resolution,
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
        "target_resolution": target_resolution,
        "color_space": "CMYK",
        "format": export_format,
        "content_type": content_type,
        "sharpen": sharpen,
    }

    task_id = await enqueue_task(
        task_type="export_pattern",
        user_id=user_id,
        data=task_data,
    )

    return ExportResponse(
        task_id=task_id,
        generated_design_id=generated_design_id,
        format=export_format,
        status="pending",
        content_type=normalize_content_type(content_type),
        sharpen=sharpen,
        target_resolution=target_resolution,
    )


class MaterialExportResponse(BaseModel):
    task_id: str | None = None
    material_id: int
    format: ExportFormat
    status: str = "pending"
    download_url: str | None = None
    content_type: str = "pattern"
    sharpen: bool = False
    target_resolution: int = 12000


@router.post(
    "/materials/{material_id}",
    response_model=MaterialExportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def export_material(
    material_id: int,
    session: _session_dep,
    current_user: _user_dep,
    export_format: ExportFormat = Query(default="tif", alias="format", description="Export format (only tif supported)"),
    target_resolution: int = Query(default=12000, ge=1024, le=16384, description="Target resolution in pixels"),
    content_type: str = Query(default="pattern", pattern="^(line-art|pattern)$", description="Content type: line-art for sharp-edged designs, pattern for textured/photographic"),
    sharpen: bool = Query(default=False, description="Apply post-upscale sharpening"),
):
    user_id = _require_user_id(current_user)

    if export_format != "tif":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only TIF format is supported for material direct export",
        )

    result = await session.execute(
        select(Material).where(
            col(Material.id) == material_id,
            col(Material.uploaded_by) == user_id,
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

    material_export_settings = get_export_settings(material.meta, "tif")
    material_settings_match = export_settings_match(
        material_export_settings,
        export_format="tif",
        target_resolution=target_resolution,
        color_space="CMYK",
        content_type=content_type,
        sharpen=sharpen,
    )

    # Check for cached export only when options match the stored export metadata.
    existing_tif = _get_file_path(material.export_tif) if hasattr(material, "export_tif") else None
    if existing_tif and material_settings_match:
        return MaterialExportResponse(
            task_id=None,
            material_id=material_id,
            format=export_format,
            status="exported",
            download_url=output_tif_storage.get_url(existing_tif),
            content_type=normalize_content_type(content_type),
            sharpen=sharpen,
            target_resolution=target_resolution,
        )

    # Check for already-running export task (dedup)
    dedup_key = _material_export_dedup_key(
        material_id=material_id,
        target_resolution=target_resolution,
        color_space="CMYK",
        content_type=content_type,
        sharpen=sharpen,
    )
    redis_client = await get_redis_client()
    if redis_client:
        existing_task_id = await redis_client.get(dedup_key)
        if existing_task_id:
            existing_task_id = existing_task_id.decode() if isinstance(existing_task_id, bytes) else existing_task_id
            task_status = await get_task_status(existing_task_id)
            if task_status and task_status.status in ("pending", "processing"):
                return MaterialExportResponse(
                    task_id=existing_task_id,
                    material_id=material_id,
                    format=export_format,
                    status="pending",
                    content_type=normalize_content_type(content_type),
                    sharpen=sharpen,
                    target_resolution=target_resolution,
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
        "content_type": content_type,
        "sharpen": sharpen,
    }

    task_id = await enqueue_task(
        task_type="export_material",
        user_id=user_id,
        data=task_data,
    )

    # Set dedup key so re-clicks return the same task_id
    if redis_client:
        await redis_client.setex(dedup_key, 600, task_id)

    return MaterialExportResponse(
        task_id=task_id,
        material_id=material_id,
        format=export_format,
        status="pending",
        content_type=normalize_content_type(content_type),
        sharpen=sharpen,
        target_resolution=target_resolution,
    )


@router.get("/tasks/{task_id}", response_model=ExportStatusResponse)
async def get_export_status(
    task_id: str,
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
    content_type = task_status.data.get("content_type") if task_status.data else None
    sharpen = task_status.data.get("sharpen") if task_status.data else None
    target_resolution = task_status.data.get("target_resolution") if task_status.data else None
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
        if step_info == "converting":
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
        content_type=normalize_content_type(content_type),
        sharpen=bool(sharpen),
        target_resolution=target_resolution if isinstance(target_resolution, int) else None,
        error=task_status.error,
    )
