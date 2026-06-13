"""Model preview generation API endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import User
from shared.task_queue import enqueue_task, get_task_status

router = APIRouter(prefix="/api/model-previews", tags=["model-previews"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


class ModelPreviewRequest(BaseModel):
    image_data_url: str = Field(..., description="Filled garment preview as a PNG/JPEG/WebP data URL")
    template_id: int | None = Field(default=None, description="Optional source template id for traceability")
    prompt: str | None = Field(default=None, max_length=1200, description="Optional model preview prompt")


class ModelPreviewSubmitResponse(BaseModel):
    task_id: str
    status: Literal["pending"] = "pending"


class ModelPreviewTaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    result: dict | None = None
    error: str | None = None


@router.post("", response_model=ModelPreviewSubmitResponse, status_code=status.HTTP_201_CREATED)
async def create_model_preview(
    request: ModelPreviewRequest,
    session: _session_dep,
    current_user: _user_dep,
) -> ModelPreviewSubmitResponse:
    del session
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Current user is incomplete",
        )

    task_id = await enqueue_task(
        task_type="model_preview",
        user_id=current_user.id,
        data={
            "image_data_url": request.image_data_url,
            "template_id": request.template_id,
            "prompt": request.prompt,
            "user_id": current_user.id,
        },
    )
    return ModelPreviewSubmitResponse(task_id=task_id)


@router.get("/tasks/{task_id}", response_model=ModelPreviewTaskStatusResponse)
async def get_model_preview_task_status(
    task_id: str,
    session: _session_dep,
    current_user: _user_dep,
) -> ModelPreviewTaskStatusResponse:
    del session
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

    return ModelPreviewTaskStatusResponse(
        task_id=task_id,
        status=task_status.status,
        result=task_status.result,
        error=task_status.error,
    )
