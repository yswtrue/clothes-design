"""Material management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_pagination import Page
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import User
from api.materials.schemas import (
    MaterialDetailResponse,
    MaterialListResponse,
    MaterialUpdateRequest,
)
from api.materials.service import MaterialService

router = APIRouter(prefix="/api/materials", tags=["materials"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=Page[MaterialListResponse])
async def list_materials(
    session: _session_dep,
    current_user: _user_dep,
    uploaded_by: int | None = Query(None),
    mime_type: str | None = Query(None),
    sort_by: str = Query("created_at", pattern="^(created_at|file_size)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> Page[MaterialListResponse]:
    """List all materials with pagination.

    Args:
        session: Database session
        current_user: Authenticated user
        uploaded_by: Filter by uploader user ID
        mime_type: Filter by MIME type
        sort_by: Sort field (created_at or file_size)
        sort_order: Sort direction (asc or desc)

    Returns:
        Paginated list of materials with thumbnail URLs

    Query params (auto-injected by fastapi-pagination):
        page: Page number (default: 1)
        size: Items per page (default: 50, max: 100)
    """
    service = MaterialService(session)
    return await service.list_materials(
        uploaded_by=uploaded_by,
        mime_type=mime_type,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{material_id}", response_model=MaterialDetailResponse)
async def get_material(
    material_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    service = MaterialService(session)
    material = await service.get_material_by_id(material_id)

    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )

    return MaterialDetailResponse.model_validate(material)


@router.patch("/{material_id}", response_model=MaterialDetailResponse)
async def update_material(
    material_id: int,
    update_data: MaterialUpdateRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    service = MaterialService(session)

    try:
        material = await service.update_material(
            material_id=material_id,
            user_id=int(current_user.id),
            update_data=update_data,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this material",
        ) from exc

    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )

    return MaterialDetailResponse.model_validate(material)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    service = MaterialService(session)

    try:
        material = await service.delete_material(
            material_id=material_id,
            user_id=int(current_user.id),
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this material",
        ) from exc

    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found",
        )


@router.get("/search/", response_model=Page[MaterialListResponse])
async def search_materials(
    session: _session_dep,
    current_user: _user_dep,
    q: str = Query(..., min_length=1),
) -> Page[MaterialListResponse]:
    """Search materials by query string.

    Args:
        session: Database session
        current_user: Authenticated user
        q: Search query string

    Returns:
        Paginated search results

    Query params (auto-injected by fastapi-pagination):
        page: Page number (default: 1)
        size: Items per page (default: 50, max: 100)
    """
    service = MaterialService(session)
    return await service.search_materials(query=q)
