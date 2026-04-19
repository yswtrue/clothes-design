from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Role, User, UserRole


async def get_role_by_id(session: AsyncSession, role_id: int) -> Role | None:
    result = await session.execute(select(Role).where(Role.id == role_id))
    return result.scalar_one_or_none()


async def get_role_by_name(session: AsyncSession, name: str) -> Role | None:
    result = await session.execute(select(Role).where(Role.name == name))
    return result.scalar_one_or_none()


async def list_roles(session: AsyncSession) -> list[Role]:
    result = await session.execute(select(Role).order_by(Role.name))
    return list(result.scalars().all())


async def create_role(session: AsyncSession, name: str, permissions: dict[str, bool]) -> Role:
    role = Role(name=name, permissions=permissions)
    session.add(role)
    await session.flush()
    await session.refresh(role)
    return role


async def update_role(
    session: AsyncSession, role: Role, name: str | None, permissions: dict[str, bool] | None
) -> Role:
    if name is not None:
        role.name = name  # type: ignore[assignment]
    if permissions is not None:
        role.permissions = permissions  # type: ignore[assignment]
    await session.flush()
    await session.refresh(role)
    return role


async def delete_role(session: AsyncSession, role: Role) -> None:
    await session.delete(role)
    await session.flush()


async def get_user_roles(session: AsyncSession, user_id: int) -> list[Role]:
    result = await session.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name)
    )
    return list(result.scalars().all())


async def assign_role_to_user(session: AsyncSession, user_id: int, role_id: int) -> UserRole:
    user_role = UserRole(user_id=user_id, role_id=role_id)
    session.add(user_role)
    await session.flush()
    await session.refresh(user_role)
    return user_role


async def remove_role_from_user(session: AsyncSession, user_id: int, role_id: int) -> None:
    await session.execute(
        delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    await session.flush()


async def has_permission(session: AsyncSession, user: User, permission: str) -> bool:
    user_id = int(user.id) if user.id else 0
    roles = await get_user_roles(session, user_id)
    for role in roles:
        if not role.permissions:
            continue
        if role.permissions.get("*") is True:
            return True
        if role.permissions.get(permission) is True:
            return True
        permission_prefix = permission.rsplit(".", 1)[0]
        wildcard_perm = f"{permission_prefix}.*"
        if role.permissions.get(wildcard_perm) is True:
            return True
    return False
