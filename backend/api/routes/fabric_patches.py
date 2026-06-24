"""Fabric patch segmentation API endpoints (async via task queue)."""

import base64

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import User
from shared.task_queue import QueueError, enqueue_task, get_task_status

router = APIRouter(prefix="/api/fabric-patches", tags=["fabric-patches"])

_file_dep = File(...)
_session_dep = Depends(get_session)
_user_dep = Depends(get_current_user)

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


class SegmentTaskResponse(BaseModel):
    """Response returned immediately after enqueuing a segmentation task."""

    task_id: str


@router.post("/segment", response_model=SegmentTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def segment_fabric_patches_endpoint(
    file: UploadFile = _file_dep,
    session: AsyncSession = _session_dep,
    user: User = _user_dep,
) -> SegmentTaskResponse:
    """Upload an image and enqueue a segmentation task.

    Returns a task_id immediately. Poll GET /status/{task_id} for results.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: {file.content_type}. Allowed: {', '.join(_ALLOWED_CONTENT_TYPES)}",
        )

    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {exc!s}",
        ) from exc

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    image_base64 = base64.b64encode(content).decode("utf-8")

    try:
        task_id = await enqueue_task(
            task_type="fabric_segment",
            user_id=user.id,  # type: ignore[assignment]
            data={
                "image_data": image_base64,
                "original_filename": file.filename,
            },
        )
    except QueueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue task: {exc!s}",
        ) from exc

    return SegmentTaskResponse(task_id=task_id)


@router.get("/status/{task_id}")
async def get_segment_status(
    task_id: str,
    user: User = _user_dep,
) -> dict:
    """Poll the status of a segmentation task.

    Returns status ("pending"|"processing"|"completed"|"failed"), result
    (patches list when completed), and error message on failure.
    """
    task_status = await get_task_status(task_id)
    if task_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return {
        "task_id": task_status.task_id,
        "status": task_status.status,
        "result": task_status.result,
        "error": task_status.error,
    }
