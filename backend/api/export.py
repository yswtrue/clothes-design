"""Export API endpoints for high-resolution TIF CMYK exports."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.base import get_session
from db.models import Design, DesignVersion, User
from task_queue.tasks import enqueue_task, get_task_status

router = APIRouter(prefix="/api/export", tags=["export"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


class ExportResponse(BaseModel):
    """Response from export trigger."""

    task_id: str
    design_id: int
    status: str = "pending"


class ExportStatusResponse(BaseModel):
    """Response for export task status query."""

    task_id: str
    design_id: int | None = None
    status: str  # pending, processing, complete, failed
    progress: int = 0  # 0-100
    current_step: str | None = None  # upscaling, vectorizing
    download_url: str | None = None
    error: str | None = None


@router.post(
    "/designs/{design_id}", response_model=ExportResponse, status_code=status.HTTP_201_CREATED
)
async def trigger_export(
    design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    """Trigger export workflow for a design (upscale → vectorize → TIF CMYK).

    Args:
        design_id: Design ID to export
        session: Database session
        current_user: Authenticated user

    Returns:
        Task ID for polling export progress

    Raises:
        HTTPException: If design not found, access denied, or no pattern to export
    """
    # Verify design exists and belongs to user
    result = await session.execute(
        select(Design).where(Design.id == design_id, Design.user_id == current_user.id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or access denied",
        )

    # Get latest version with pattern URL
    version_result = await session.execute(
        select(DesignVersion)
        .where(DesignVersion.design_id == design_id)
        .order_by(DesignVersion.version.desc())
        .limit(1)
    )
    latest_version = version_result.scalar_one_or_none()

    if not latest_version or not latest_version.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Design has no data to export",
        )

    pattern_url = latest_version.data.get("pattern_url")
    if not pattern_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Design has no pattern to export",
        )

    # Enqueue export_pattern task (will be handled by worker with task chaining)
    task_data = {
        "design_id": design_id,
        "pattern_url": pattern_url,
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
        design_id=design_id,
        status="pending",
    )


@router.get("/tasks/{task_id}", response_model=ExportStatusResponse)
async def get_export_status(
    task_id: str,
    session: _session_dep,
    current_user: _user_dep,
):
    """Get export task status and progress.

    Args:
        task_id: Task ID to query
        session: Database session
        current_user: Authenticated user

    Returns:
        Export status with progress tracking and download URL when complete

    Raises:
        HTTPException: If task not found or access denied
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

    # Extract progress and status from task metadata
    design_id = task_status.data.get("design_id") if task_status.data else None
    current_step = None
    progress = 0
    download_url = None

    # Map worker status to export status
    status_mapping = {
        "pending": "pending",
        "processing": "processing",
        "completed": "complete",
        "failed": "failed",
    }
    export_status = status_mapping.get(task_status.status, task_status.status)

    # Determine current step and progress from task metadata
    if task_status.status == "processing":
        # Check if we're in upscaling or vectorizing phase
        step_info = task_status.data.get("current_step") if task_status.data else None
        if step_info == "vectorizing":
            current_step = "vectorizing"
            progress = 60  # Upscaling done (0-50), vectorizing in progress (50-100)
        else:
            current_step = "upscaling"
            progress = 25  # In progress

    elif task_status.status == "completed":
        current_step = "complete"
        progress = 100
        # Extract download URL from result
        if task_status.result:
            download_url = task_status.result.get("download_url")

    response = ExportStatusResponse(
        task_id=task_id,
        design_id=design_id,
        status=export_status,
        progress=progress,
        current_step=current_step,
        download_url=download_url,
        error=task_status.error,
    )

    return response
