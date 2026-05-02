"""Pattern generation API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.ai.schemas import GenerationParams, StyleAnalysis
from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import Design, DesignVersion, Material, User
from api.materials.schemas import MaterialMeta
from shared.task_queue import enqueue_task, get_task_status

router = APIRouter(prefix="/api/generate", tags=["generate"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


class GenerateRequest(BaseModel):
    """Request to generate a pattern."""

    material_id: int
    pattern_type: str  # seamless, standalone, full
    prompt: str | None = None
    colors: list[str] | None = None
    use_img2img: bool = True
    strength: float = 0.65
    generate_vector: bool = False


class GenerateResponse(BaseModel):
    """Response from pattern generation request."""

    task_id: str
    design_id: int
    status: str = "pending"


class TaskStatusResponse(BaseModel):
    """Response for task status query."""

    task_id: str
    status: str  # pending, processing, completed, failed
    result: dict | None = None
    error: str | None = None


@router.post("", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_pattern(
    request: GenerateRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    """Generate a pattern from a material.

    Args:
        request: Generation parameters
        session: Database session
        current_user: Authenticated user

    Returns:
        Task ID and design ID for polling

    Raises:
        HTTPException: If material not found or doesn't belong to user
    """
    # Verify material exists and belongs to user
    result = await session.execute(
        select(Material).where(
            Material.id == request.material_id, Material.uploaded_by == current_user.id
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

    # Build prompt from request or style analysis
    prompt = request.prompt
    if not prompt and style_analysis:
        prompt = style_analysis.style_description

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material has no style analysis and no prompt provided",
        )

    # Use colors from request or style analysis
    colors = request.colors
    if not colors and style_analysis:
        colors = style_analysis.color_palette

    init_image_b64 = None
    if request.use_img2img and material.file:
        import base64

        try:
            with material.file.open() as f:
                image_bytes = f.read()
            init_image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load material image: {e}",
            )

    # Create Design record
    from datetime import datetime

    design_name = f"Design-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    design = Design(user_id=current_user.id, name=design_name, status="generating")
    session.add(design)
    await session.flush()

    initial_version = DesignVersion(
        design_id=design.id,
        version=1,
        data={"material_id": request.material_id, "pattern_type": request.pattern_type},
    )
    session.add(initial_version)

    gen_params = GenerationParams(
        style=prompt,
        tiling="tile" if request.pattern_type == "seamless" else "clamp",
        width=1024,
        height=1024,
        seed=42,
        init_image_b64=init_image_b64,
        strength=request.strength,
        prompt_override=request.prompt,
    )

    # Enqueue task
    task_data = {
        "material_id": request.material_id,
        "design_id": design.id,
        "pattern_type": request.pattern_type,
        "style": style_analysis.model_dump() if style_analysis else {"style_description": prompt},
        "params": gen_params.model_dump(),
        "generate_vector": request.generate_vector,
    }

    task_id = await enqueue_task(task_type="generate", user_id=current_user.id, data=task_data)

    await session.commit()

    return GenerateResponse(task_id=task_id, design_id=design.id, status="pending")


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
