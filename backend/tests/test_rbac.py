import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import create_access_token
from db.models import Role, User
from rbac.seed import seed_default_roles
from rbac.service import assign_role_to_user, create_role, has_permission


@pytest.mark.asyncio
async def test_seed_default_roles(db_session: AsyncSession):
    await seed_default_roles(db_session)
    await db_session.commit()

    from sqlalchemy import select

    result = await db_session.execute(select(Role))
    roles = list(result.scalars().all())

    assert len(roles) == 3
    role_names = {role.name for role in roles}
    assert role_names == {"admin", "designer", "viewer"}

    admin_role = next(r for r in roles if r.name == "admin")
    assert admin_role.permissions.get("*") is True

    designer_role = next(r for r in roles if r.name == "designer")
    assert designer_role.permissions.get("designs.create") is True
    assert designer_role.permissions.get("materials.create") is True

    viewer_role = next(r for r in roles if r.name == "viewer")
    assert viewer_role.permissions.get("designs.read") is True
    assert viewer_role.permissions.get("designs.create") is None


@pytest.mark.asyncio
async def test_create_role(db_session: AsyncSession):
    role = await create_role(db_session, "custom", {"test.permission": True})
    await db_session.commit()

    assert role.name == "custom"
    assert role.permissions == {"test.permission": True}
    assert role.id is not None


@pytest.mark.asyncio
async def test_assign_role_to_user(db_session: AsyncSession):
    from auth.security import get_password_hash

    user = User(username="testuser", password_hash=get_password_hash("password123"))
    db_session.add(user)
    await db_session.flush()

    role = await create_role(db_session, "tester", {"test.read": True})
    await db_session.flush()

    user_role = await assign_role_to_user(db_session, user.id, role.id)
    await db_session.commit()

    assert user_role.user_id == user.id
    assert user_role.role_id == role.id


@pytest.mark.asyncio
async def test_has_permission_with_wildcard(db_session: AsyncSession):
    from auth.security import get_password_hash

    user = User(username="adminuser", password_hash=get_password_hash("password123"))
    db_session.add(user)
    await db_session.flush()

    admin_role = await create_role(db_session, "admin", {"*": True})
    await db_session.flush()

    await assign_role_to_user(db_session, user.id, admin_role.id)
    await db_session.commit()

    assert await has_permission(db_session, user, "designs.create") is True
    assert await has_permission(db_session, user, "materials.delete") is True
    assert await has_permission(db_session, user, "anything.random") is True


@pytest.mark.asyncio
async def test_has_permission_with_specific_permissions(db_session: AsyncSession):
    from auth.security import get_password_hash

    user = User(username="designeruser", password_hash=get_password_hash("password123"))
    db_session.add(user)
    await db_session.flush()

    designer_role = await create_role(
        db_session,
        "designer",
        {
            "designs.create": True,
            "designs.read": True,
            "materials.read": True,
        },
    )
    await db_session.flush()

    await assign_role_to_user(db_session, user.id, designer_role.id)
    await db_session.commit()

    assert await has_permission(db_session, user, "designs.create") is True
    assert await has_permission(db_session, user, "designs.read") is True
    assert await has_permission(db_session, user, "materials.read") is True
    assert await has_permission(db_session, user, "materials.delete") is False


@pytest.mark.asyncio
async def test_has_permission_with_namespace_wildcard(db_session: AsyncSession):
    from auth.security import get_password_hash

    user = User(username="poweruser", password_hash=get_password_hash("password123"))
    db_session.add(user)
    await db_session.flush()

    role = await create_role(db_session, "poweruser", {"designs.*": True})
    await db_session.flush()

    await assign_role_to_user(db_session, user.id, role.id)
    await db_session.commit()

    assert await has_permission(db_session, user, "designs.create") is True
    assert await has_permission(db_session, user, "designs.read") is True
    assert await has_permission(db_session, user, "designs.delete") is True
    assert await has_permission(db_session, user, "materials.create") is False


@pytest.mark.asyncio
async def test_list_roles_endpoint(client: AsyncClient, db_session: AsyncSession, test_env):
    await seed_default_roles(db_session)
    await db_session.commit()

    response = await client.get("/api/roles")
    assert response.status_code == 200

    roles = response.json()
    assert len(roles) >= 3
    role_names = {role["name"] for role in roles}
    assert "admin" in role_names
    assert "designer" in role_names
    assert "viewer" in role_names


@pytest.mark.asyncio
async def test_create_role_endpoint_requires_permission(
    client: AsyncClient, db_session: AsyncSession, test_env
):
    from auth.security import get_password_hash

    user = User(username="nonadmin", password_hash=get_password_hash("Test123!@#"))
    db_session.add(user)
    await db_session.flush()

    viewer_role = await create_role(db_session, "viewer", {"designs.read": True})
    await assign_role_to_user(db_session, user.id, viewer_role.id)
    await db_session.commit()

    token = create_access_token(user.id)

    response = await client.post(
        "/api/roles",
        json={"name": "custom", "permissions": {"test.permission": True}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Permission denied" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_role_endpoint_with_permission(
    client: AsyncClient, db_session: AsyncSession, test_env
):
    from auth.security import get_password_hash

    user = User(username="adminuser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(user)
    await db_session.flush()

    admin_role = await create_role(db_session, "admin", {"*": True})
    await assign_role_to_user(db_session, user.id, admin_role.id)
    await db_session.commit()

    token = create_access_token(user.id)

    response = await client.post(
        "/api/roles",
        json={"name": "custom", "permissions": {"test.permission": True}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    role = response.json()
    assert role["name"] == "custom"
    assert role["permissions"]["test.permission"] is True


@pytest.mark.asyncio
async def test_update_role_endpoint(client: AsyncClient, db_session: AsyncSession, test_env):
    from auth.security import get_password_hash

    user = User(username="adminuser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(user)
    await db_session.flush()

    admin_role = await create_role(db_session, "admin", {"*": True})
    await assign_role_to_user(db_session, user.id, admin_role.id)

    test_role = await create_role(db_session, "test", {"old.permission": True})
    await db_session.commit()

    token = create_access_token(user.id)

    response = await client.put(
        f"/api/roles/{test_role.id}",
        json={"permissions": {"new.permission": True}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    role = response.json()
    assert role["permissions"]["new.permission"] is True


@pytest.mark.asyncio
async def test_delete_role_endpoint(client: AsyncClient, db_session: AsyncSession, test_env):
    from auth.security import get_password_hash

    user = User(username="adminuser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(user)
    await db_session.flush()

    admin_role = await create_role(db_session, "admin", {"*": True})
    await assign_role_to_user(db_session, user.id, admin_role.id)

    test_role = await create_role(db_session, "deleteme", {"test.permission": True})
    await db_session.commit()

    token = create_access_token(user.id)

    response = await client.delete(
        f"/api/roles/{test_role.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_assign_role_to_user_endpoint(
    client: AsyncClient, db_session: AsyncSession, test_env
):
    from auth.security import get_password_hash

    admin_user = User(username="adminuser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(admin_user)
    await db_session.flush()

    target_user = User(username="targetuser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(target_user)
    await db_session.flush()

    admin_role = await create_role(db_session, "admin", {"*": True})
    viewer_role = await create_role(db_session, "viewer", {"designs.read": True})
    await assign_role_to_user(db_session, admin_user.id, admin_role.id)
    await db_session.commit()

    token = create_access_token(admin_user.id)

    response = await client.post(
        f"/api/users/{target_user.id}/roles",
        json={"role_id": viewer_role.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["message"] == "Role assigned successfully"
