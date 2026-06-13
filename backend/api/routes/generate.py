"""Pattern generation API endpoints."""

import base64
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import GeneratedDesign, Material, User
from api.materials.schemas import MaterialMeta
from api.storage.storages import material_storage
from shared.ai.schemas import GenerationParams
from shared.task_queue import enqueue_task, get_task_status

router = APIRouter(prefix="/api/generate", tags=["generate"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


class GenerateRequest(BaseModel):
    material_id: int
    prompt: str | None = None
    colors: list[str] | None = None
    use_img2img: bool = True
    strength: float = 0.65


class GenerateResponse(BaseModel):
    task_id: str
    generated_design_id: int
    status: str = "pending"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    result: dict | None = None
    error: str | None = None


def _condition(value: object) -> ColumnElement[bool]:
    return cast(ColumnElement[bool], value)


async def _load_material_image_b64(material: Material) -> str | None:
    if not material.file:
        return None
    if not material.stored_filename:
        raise ValueError("Material has no stored filename")

    image_bytes = await material_storage.download(material.stored_filename)
    return base64.b64encode(image_bytes).decode("utf-8")


@router.post("", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_pattern(
    request: GenerateRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(Material).where(
            _condition(Material.id == request.material_id),
            _condition(Material.uploaded_by == current_user.id),
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

    prompt = request.prompt
    if not prompt and style_analysis:
        prompt = style_analysis.style_description

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material has no style analysis and no prompt provided",
        )

    colors = request.colors
    if not colors and style_analysis:
        colors = style_analysis.color_palette

    init_image_b64 = None
    if request.use_img2img:
        try:
            init_image_b64 = await _load_material_image_b64(material)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load material image: {e}",
            ) from e

    existing_count = await session.execute(
        select(GeneratedDesign).where(
            _condition(GeneratedDesign.material_id == request.material_id)
        )
    )
    next_version = len(existing_count.scalars().all())

    generated_design = GeneratedDesign(
        material_id=request.material_id,
        status="generating",
        variant_index=next_version,
        prompt_used=prompt,
        generation_params={"strength": request.strength},
    )
    session.add(generated_design)
    await session.flush()
    if current_user.id is None or generated_design.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize generation task",
        )

    gen_params = GenerationParams(
        style=prompt,
        tiling="tile",
        width=1024,
        height=1024,
        seed=42,
        init_image_b64=init_image_b64,
        strength=request.strength,
        prompt_override=request.prompt,
    )

    task_data = {
        "material_id": request.material_id,
        "generated_design_id": generated_design.id,
        "style": style_analysis.model_dump() if style_analysis else {"style_description": prompt},
        "params": gen_params.model_dump(),
    }

    task_id = await enqueue_task(task_type="generate", user_id=current_user.id, data=task_data)

    await session.commit()

    return GenerateResponse(
        task_id=task_id, generated_design_id=generated_design.id, status="pending"
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status_endpoint(
    task_id: str,
    session: _session_dep,
    current_user: _user_dep,
):
    """Get task status and result.

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

    response = TaskStatusResponse(
        task_id=task_id,
        status=task_status.status,
        result=task_status.result,
        error=task_status.error,
    )

    return response
