"""Tests for design versions API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Design, DesignVersion, User


@pytest.mark.asyncio
async def test_list_versions_success(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test successful version listing."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version1 = DesignVersion(design_id=design.id, version=1, data={"pattern_url": "v1.png"})
    version2 = DesignVersion(design_id=design.id, version=2, data={"pattern_url": "v2.png"})
    version3 = DesignVersion(design_id=design.id, version=3, data={"pattern_url": "v3.png"})
    db_session.add_all([version1, version2, version3])
    await db_session.commit()

    response = await client.get(f"/api/designs/{design.id}/versions", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["versions"]) == 3
    assert data["versions"][0]["version"] == 3
    assert data["versions"][1]["version"] == 2
    assert data["versions"][2]["version"] == 1
    assert data["versions"][0]["data"]["pattern_url"] == "v3.png"


@pytest.mark.asyncio
async def test_list_versions_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test listing versions for non-existent design returns 404."""
    response = await client.get("/api/designs/99999/versions", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_versions_access_denied(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test listing versions for another user's design returns 404."""
    from auth.security import get_password_hash

    other_user = User(username="otheruser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(other_user)
    await db_session.flush()

    design = Design(user_id=other_user.id, name="Other Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    response = await client.get(f"/api/designs/{design.id}/versions", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_versions_empty(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test listing versions when design has no versions."""
    design = Design(user_id=auth_user.id, name="Empty Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    response = await client.get(f"/api/designs/{design.id}/versions", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["versions"]) == 0


@pytest.mark.asyncio
async def test_rollback_success(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test successful rollback to previous version."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version1 = DesignVersion(design_id=design.id, version=1, data={"pattern_url": "v1.png"})
    version2 = DesignVersion(design_id=design.id, version=2, data={"pattern_url": "v2.png"})
    version3 = DesignVersion(design_id=design.id, version=3, data={"pattern_url": "v3.png"})
    db_session.add_all([version1, version2, version3])
    await db_session.commit()

    response = await client.post(
        f"/api/designs/{design.id}/rollback",
        headers=auth_headers,
        json={"version": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 4
    assert "version 1" in data["message"].lower()

    result = await db_session.execute(
        select(DesignVersion).where(
            DesignVersion.design_id == design.id, DesignVersion.version == 4
        )
    )
    new_version = result.scalar_one()
    assert new_version.data == {"pattern_url": "v1.png"}


@pytest.mark.asyncio
async def test_rollback_version_not_found(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test rollback to non-existent version returns 404."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    response = await client.post(
        f"/api/designs/{design.id}/rollback",
        headers=auth_headers,
        json={"version": 99},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rollback_design_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test rollback for non-existent design returns 404."""
    response = await client.post(
        "/api/designs/99999/rollback",
        headers=auth_headers,
        json={"version": 1},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rollback_access_denied(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test rollback for another user's design returns 404."""
    from auth.security import get_password_hash

    other_user = User(username="otheruser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(other_user)
    await db_session.flush()

    design = Design(user_id=other_user.id, name="Other Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version = DesignVersion(design_id=design.id, version=1, data={"test": "data"})
    db_session.add(version)
    await db_session.commit()

    response = await client.post(
        f"/api/designs/{design.id}/rollback",
        headers=auth_headers,
        json={"version": 1},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rollback_creates_new_version(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test that rollback creates a new version instead of overwriting."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version1 = DesignVersion(design_id=design.id, version=1, data={"value": 1})
    version2 = DesignVersion(design_id=design.id, version=2, data={"value": 2})
    db_session.add_all([version1, version2])
    await db_session.commit()

    response = await client.post(
        f"/api/designs/{design.id}/rollback",
        headers=auth_headers,
        json={"version": 1},
    )

    assert response.status_code == 200

    result = await db_session.execute(
        select(DesignVersion).where(DesignVersion.design_id == design.id)
    )
    all_versions = result.scalars().all()
    assert len(all_versions) == 3

    result = await db_session.execute(
        select(DesignVersion).where(
            DesignVersion.design_id == design.id, DesignVersion.version == 1
        )
    )
    original_v1 = result.scalar_one()
    assert original_v1.data == {"value": 1}

    result = await db_session.execute(
        select(DesignVersion).where(
            DesignVersion.design_id == design.id, DesignVersion.version == 2
        )
    )
    original_v2 = result.scalar_one()
    assert original_v2.data == {"value": 2}
