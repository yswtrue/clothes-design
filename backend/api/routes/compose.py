from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import Design, GeneratedDesign, PrjTemplate, User
from api.storage.factory import get_storage_service
from shared.task_queue.celery_integration import enqueue_task, get_task_status

router = APIRouter(prefix="/api/designs", tags=["compose"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


def get_file_path(file_obj) -> str | None:
    if file_obj is None:
        return None
    if hasattr(file_obj, "path"):
        return file_obj.path
    if isinstance(file_obj, str):
        return file_obj
    return None


class ComposeRequest(BaseModel):
    generated_design_id: int
    prj_template_id: int
    name: str | None = None


class ComposeResponse(BaseModel):
    task_id: str
    design_id: int
    status: str = "pending"


class ComposeStatusResponse(BaseModel):
    task_id: str
    design_id: int | None = None
    status: str
    progress: int = 0
    current_step: str | None = None
    download_url: str | None = None
    error: str | None = None


class DesignDetailResponse(BaseModel):
    id: int
    name: str
    status: str
    generated_design_id: int | None = None
    prj_template_id: int | None = None
    output_tif_url: str | None = None
    created_at: str | None = None


@router.post("/compose", response_model=ComposeResponse, status_code=status.HTTP_201_CREATED)
async def compose_design(
    request: ComposeRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    gd_result = await session.execute(
        select(GeneratedDesign).where(GeneratedDesign.id == request.generated_design_id)
    )
    generated_design = gd_result.scalar_one_or_none()

    if not generated_design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated design not found",
        )

    from api.db.models import Material
    material_result = await session.execute(
        select(Material).where(Material.id == generated_design.material_id)
    )
    material = material_result.scalar_one_or_none()

    if not material or material.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this design",
        )

    template_result = await session.execute(
        select(PrjTemplate).where(PrjTemplate.id == request.prj_template_id)
    )
    prj_template = template_result.scalar_one_or_none()

    if not prj_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PRJ template not found",
        )

    design_name = request.name or f"Design-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    design = Design(
        user_id=current_user.id,
        generated_design_id=request.generated_design_id,
        prj_template_id=request.prj_template_id,
        name=design_name,
        status="composing",
    )
    session.add(design)
    await session.flush()

    task_data = {
        "design_id": design.id,
        "generated_design_id": request.generated_design_id,
        "prj_template_id": request.prj_template_id,
        "fabric_image_path": get_file_path(generated_design.image),
        "prj_path": get_file_path(prj_template.prj_file),
        "regions": prj_template.regions,
    }

    task_id = await enqueue_task(
        task_type="compose_tif",
        user_id=current_user.id,
        data=task_data,
    )

    await session.commit()

    return ComposeResponse(
        task_id=task_id,
        design_id=design.id,
        status="pending",
    )


@router.get("/compose/tasks/{task_id}", response_model=ComposeStatusResponse)
async def get_compose_status(
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

    design_id = task_status_obj.data.get("design_id") if task_status_obj.data else None
    current_step = None
    progress = 0
    download_url = None

    status_mapping = {
        "pending": "pending",
        "processing": "processing",
        "completed": "complete",
        "failed": "failed",
    }
    compose_status = status_mapping.get(task_status_obj.status, task_status_obj.status)

    if task_status_obj.status == "processing":
        step_info = task_status_obj.data.get("current_step") if task_status_obj.data else None
        if step_info == "rendering":
            current_step = "rendering"
            progress = 60
        else:
            current_step = "parsing"
            progress = 30

    elif task_status_obj.status == "completed":
        current_step = "complete"
        progress = 100
        if task_status_obj.result:
            download_url = task_status_obj.result.get("download_url")

    return ComposeStatusResponse(
        task_id=task_id,
        design_id=design_id,
        status=compose_status,
        progress=progress,
        current_step=current_step,
        download_url=download_url,
        error=task_status_obj.error,
    )


@router.get("/{design_id}", response_model=DesignDetailResponse)
async def get_design(
    design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(Design).where(
            Design.id == design_id,
            Design.user_id == current_user.id
        )
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or access denied",
        )

    output_tif_url = None
    output_tif_path = get_file_path(design.output_tif)
    if output_tif_path:
        storage = get_storage_service()
        output_tif_url = await storage.get_url(output_tif_path)

    return DesignDetailResponse(
        id=design.id,
        name=design.name,
        status=design.status,
        generated_design_id=design.generated_design_id,
        prj_template_id=design.prj_template_id,
        output_tif_url=output_tif_url,
        created_at=design.created_at.isoformat() if design.created_at else None,
    )
