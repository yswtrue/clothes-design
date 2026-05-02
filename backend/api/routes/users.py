from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.auth.dependencies import get_current_user
from api.auth.schemas import UserResponse
from api.db.base import get_session
from api.db.models import User, UserRole
from api.rbac.permissions import require_permission
from api.rbac.schemas import UserRoleAssignment
from api.rbac.service import assign_role_to_user, get_role_by_id

router = APIRouter(prefix="/api/users", tags=["users"])
_session_dep = Depends(get_session)


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    session: Annotated[AsyncSession, _session_dep],
    user: User = Depends(get_current_user),
) -> UserResponse:
    result = await session.execute(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    user_with_roles = result.scalar_one()
    
    roles = [ur.role.name for ur in user_with_roles.user_roles if ur.role]
    
    return UserResponse(
        id=user_with_roles.id,
        username=user_with_roles.username,
        created_at=user_with_roles.created_at,
        roles=roles,
    )


@router.post("/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_user_role(
    user_id: int,
    payload: UserRoleAssignment,
    session: Annotated[AsyncSession, _session_dep],
    current_user: Annotated[User, Depends(require_permission("users.manage"))],
) -> dict[str, str]:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    role = await get_role_by_id(session, payload.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    try:
        await assign_role_to_user(session, user_id, payload.role_id)
        await session.commit()
    except Exception as e:
        await session.rollback()
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has this role",
            ) from e
        raise
    return {"message": "Role assigned successfully"}
