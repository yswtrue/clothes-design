from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_session
from db.models import User
from rbac.permissions import require_permission
from rbac.schemas import RoleCreate, RoleResponse, RoleUpdate
from rbac.service import (
    create_role,
    delete_role,
    get_role_by_id,
    get_role_by_name,
    list_roles,
    update_role,
)

router = APIRouter(prefix="/api/roles", tags=["roles"])
_session_dep = Depends(get_session)


@router.get("", response_model=list[RoleResponse])
async def get_roles(
    session: Annotated[AsyncSession, _session_dep],
) -> list[RoleResponse]:
    roles = await list_roles(session)
    return [RoleResponse.model_validate(role) for role in roles]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    session: Annotated[AsyncSession, _session_dep],
) -> RoleResponse:
    role = await get_role_by_id(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return RoleResponse.model_validate(role)


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_new_role(
    payload: RoleCreate,
    session: Annotated[AsyncSession, _session_dep],
    current_user: Annotated[User, Depends(require_permission("roles.manage"))],
) -> RoleResponse:
    existing = await get_role_by_name(session, payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists",
        )
    role = await create_role(session, payload.name, payload.permissions)
    await session.commit()
    return RoleResponse.model_validate(role)


@router.put("/{role_id}", response_model=RoleResponse)
async def update_existing_role(
    role_id: int,
    payload: RoleUpdate,
    session: Annotated[AsyncSession, _session_dep],
    current_user: Annotated[User, Depends(require_permission("roles.manage"))],
) -> RoleResponse:
    role = await get_role_by_id(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    if payload.name:
        existing = await get_role_by_name(session, payload.name)
        if existing and existing.id != role_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role with this name already exists",
            )
    updated_role = await update_role(session, role, payload.name, payload.permissions)
    await session.commit()
    return RoleResponse.model_validate(updated_role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_role(
    role_id: int,
    session: Annotated[AsyncSession, _session_dep],
    current_user: Annotated[User, Depends(require_permission("roles.manage"))],
) -> None:
    role = await get_role_by_id(session, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    await delete_role(session, role)
    await session.commit()
