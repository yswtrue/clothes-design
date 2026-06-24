"""CLO3D project integration API endpoints.

Upload .zprj files, list fabric pieces, assign materials per piece,
trigger CLO3D rendering, and poll render task status.
"""

import json
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi_pagination import Params, create_page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import Clo3dProject, Clo3dRenderTask, User
from api.storage.storages import clo3d_project_storage, clo3d_render_storage, preview_storage
from shared.task_queue import enqueue_task, get_task_status

router = APIRouter(prefix="/api/clo3d", tags=["clo3d"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


# ── Response Schemas ──────────────────────────────────────────────────────────

class Clo3dPiece(BaseModel):
    name: str
    label: str | None = None


class Clo3dProjectResponse(BaseModel):
    id: int
    name: str
    category: str
    preview_url: str | None = None
    pieces: list[Clo3dPiece] | None = None
    piece_count: int = 0
    status: str
    created_at: str | None = None

    class Config:
        from_attributes = True


class Clo3dRenderRequest(BaseModel):
    project_id: int
    material_assignments: dict[str, int] = {}
    # {"前片": 5, "后片": 12, "左袖": 8, "右袖": 8, "领口": 3}


class Clo3dRenderSubmitResponse(BaseModel):
    task_id: str
    render_task_id: int
    status: str = "pending"


class RenderTaskStatusResponse(BaseModel):
    task_id: str
    render_task_id: int
    status: str  # pending | processing | completed | failed
    front_url: str | None = None
    back_url: str | None = None
    error: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pieces_from_json(raw: object) -> list[Clo3dPiece] | None:
    if not raw:
        return None
    if isinstance(raw, list):
        return [
            Clo3dPiece(
                name=p.get("name", ""),
                label=p.get("label"),
            )
            for p in raw
            if isinstance(p, dict)
        ]
    if isinstance(raw, dict):
        items = raw.get("pieces") or raw.get("items") or []
        if isinstance(items, list):
            return [
                Clo3dPiece(
                    name=p.get("name", ""),
                    label=p.get("label"),
                )
                for p in items
                if isinstance(p, dict)
            ]
    return None


def _format_created_at(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat() + "Z" if hasattr(dt, "isoformat") else str(dt)


# ── Project CRUD ──────────────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects(
    session: _session_dep,
    current_user: _user_dep,
    params: Params = Depends(),
    category: str | None = Query(None),
    status: str | None = Query(None),
):
    query = select(Clo3dProject).where(
        col(Clo3dProject.user_id) == current_user.id
    )

    if category:
        query = query.where(col(Clo3dProject.category) == category)
    if status:
        query = query.where(col(Clo3dProject.status) == status)

    query = query.order_by(col(Clo3dProject.created_at).desc())

    page = await paginate(session, query, params)

    items = []
    for p in page.items:
        preview_url = (
            preview_storage.get_url(str(p.preview_image)) if p.preview_image else None
        )
        items.append(
            Clo3dProjectResponse(
                id=p.id,
                name=p.name,
                category=p.category,
                preview_url=preview_url,
                pieces=_pieces_from_json(p.pieces),
                piece_count=p.piece_count or 0,
                status=p.status or "uploaded",
                created_at=_format_created_at(p.created_at),
            )
        )

    return create_page(items, total=page.total, params=params)


@router.post("/projects", response_model=Clo3dProjectResponse, status_code=status.HTTP_201_CREATED)
async def upload_clo3d_project(
    session: _session_dep,
    current_user: _user_dep,
    name: str = Form(...),
    category: str = Form(...),
    prj_file: UploadFile = File(...),
    preview_file: UploadFile | None = File(None),
    pieces: str | None = Form(None),
):
    """Upload a CLO3D project (.zprj) with optional piece metadata.

    The `pieces` JSON should be a list of objects:
      [{"name": "front", "label": "前片"}, {"name": "back", "label": "后片"}, ...]
    """
    pieces_parsed = None
    if pieces:
        try:
            pieces_parsed = json.loads(pieces)
            if not isinstance(pieces_parsed, list):
                raise ValueError("pieces must be a JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pieces JSON: {exc}",
            ) from exc

    project = Clo3dProject(
        user_id=current_user.id,
        name=name,
        category=category,
        prj_file=prj_file,
        preview_image=preview_file,
        pieces=pieces_parsed,
        piece_count=len(pieces_parsed) if pieces_parsed else 0,
        status="uploaded",
    )

    session.add(project)
    await session.commit()
    await session.refresh(project)

    preview_url = (
        preview_storage.get_url(str(project.preview_image))
        if project.preview_image
        else None
    )

    return Clo3dProjectResponse(
        id=project.id,
        name=project.name,
        category=project.category,
        preview_url=preview_url,
        pieces=_pieces_from_json(project.pieces),
        piece_count=project.piece_count or 0,
        status=project.status or "uploaded",
        created_at=_format_created_at(project.created_at),
    )


@router.get("/projects/{project_id}", response_model=Clo3dProjectResponse)
async def get_project(
    project_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(Clo3dProject).where(
            col(Clo3dProject.id) == project_id,
            col(Clo3dProject.user_id) == current_user.id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    preview_url = (
        preview_storage.get_url(str(project.preview_image))
        if project.preview_image
        else None
    )

    return Clo3dProjectResponse(
        id=project.id,
        name=project.name,
        category=project.category,
        preview_url=preview_url,
        pieces=_pieces_from_json(project.pieces),
        piece_count=project.piece_count or 0,
        status=project.status or "uploaded",
        created_at=_format_created_at(project.created_at),
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(Clo3dProject).where(
            col(Clo3dProject.id) == project_id,
            col(Clo3dProject.user_id) == current_user.id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project.soft_delete()
    await session.commit()


# ── Render ────────────────────────────────────────────────────────────────────

@router.post("/render", response_model=Clo3dRenderSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_render(
    request: Clo3dRenderRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    """Submit a CLO3D render task with per-piece material assignments.

    material_assignments maps piece NAME (string) to material_id (int).
    """
    # Verify project exists and belongs to user
    result = await session.execute(
        select(Clo3dProject).where(
            col(Clo3dProject.id) == request.project_id,
            col(Clo3dProject.user_id) == current_user.id,
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not project.pieces:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no pieces defined — upload piece metadata first",
        )

    # Create render task record
    render_task = Clo3dRenderTask(
        project_id=request.project_id,
        user_id=current_user.id,
        material_assignments=request.material_assignments,
        status="pending",
    )
    session.add(render_task)
    await session.flush()

    if current_user.id is None or render_task.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize render task",
        )

    # Enqueue background task
    task_id = await enqueue_task(
        task_type="clo3d_render",
        user_id=current_user.id,
        data={
            "render_task_id": render_task.id,
            "project_id": request.project_id,
            "material_assignments": request.material_assignments,
        },
    )

    await session.commit()

    return Clo3dRenderSubmitResponse(
        task_id=task_id,
        render_task_id=render_task.id,
        status="pending",
    )


@router.get("/tasks/{task_id}", response_model=RenderTaskStatusResponse)
async def get_render_task_status(
    task_id: str,
    session: _session_dep,
    current_user: _user_dep,
):
    """Poll render task status. Returns front/back image URLs when complete."""
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

    # Look up render task for front/back URLs
    render_task_id = None
    front_url = None
    back_url = None
    error_msg = task_status.error

    if task_status.data:
        render_task_id = task_status.data.get("render_task_id")

    if render_task_id:
        result = await session.execute(
            select(Clo3dRenderTask).where(col(Clo3dRenderTask.id) == render_task_id)
        )
        render_task = result.scalar_one_or_none()
        if render_task:
            if render_task.front_image:
                front_url = clo3d_render_storage.get_url(str(render_task.front_image))
            if render_task.back_image:
                back_url = clo3d_render_storage.get_url(str(render_task.back_image))
            if not error_msg and render_task.error_message:
                error_msg = render_task.error_message

    return RenderTaskStatusResponse(
        task_id=task_id,
        render_task_id=render_task_id or 0,
        status=task_status.status,
        front_url=front_url,
        back_url=back_url,
        error=error_msg,
    )


@router.get("/projects/{project_id}/render-history")
async def get_render_history(
    project_id: int,
    session: _session_dep,
    current_user: _user_dep,
    params: Params = Depends(),
):
    """List render tasks for a project."""
    query = (
        select(Clo3dRenderTask)
        .where(
            col(Clo3dRenderTask.project_id) == project_id,
            col(Clo3dRenderTask.user_id) == current_user.id,
        )
        .order_by(col(Clo3dRenderTask.created_at).desc())
    )

    page = await paginate(session, query, params)

    items = []
    for rt in page.items:
        front_url = (
            clo3d_render_storage.get_url(str(rt.front_image))
            if rt.front_image
            else None
        )
        back_url = (
            clo3d_render_storage.get_url(str(rt.back_image))
            if rt.back_image
            else None
        )
        items.append(
            RenderTaskStatusResponse(
                task_id="",
                render_task_id=rt.id,
                status=rt.status or "unknown",
                front_url=front_url,
                back_url=back_url,
                error=rt.error_message,
            )
        )

    return create_page(items, total=page.total, params=params)
