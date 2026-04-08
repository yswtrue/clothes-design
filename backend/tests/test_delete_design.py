"""Tests for design deletion API endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Design, DesignVersion, User


@pytest.mark.asyncio
async def test_delete_design_success(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test successful design deletion."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version1 = DesignVersion(design_id=design.id, version=1, data={"test": "data"})
    version2 = DesignVersion(design_id=design.id, version=2, data={"test": "data2"})
    db_session.add_all([version1, version2])
    await db_session.commit()

    response = await client.delete(f"/api/designs/{design.id}", headers=auth_headers)

    assert response.status_code == 204
    assert response.content == b""

    result = await db_session.execute(select(Design).where(Design.id == design.id))
    deleted_design = result.scalar_one_or_none()
    assert deleted_design is None


@pytest.mark.asyncio
async def test_delete_design_cascade_versions(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test that deleting design cascades to versions."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version1 = DesignVersion(design_id=design.id, version=1, data={"test": "data"})
    version2 = DesignVersion(design_id=design.id, version=2, data={"test": "data2"})
    version3 = DesignVersion(design_id=design.id, version=3, data={"test": "data3"})
    db_session.add_all([version1, version2, version3])
    await db_session.commit()

    response = await client.delete(f"/api/designs/{design.id}", headers=auth_headers)

    assert response.status_code == 204

    result = await db_session.execute(
        select(DesignVersion).where(DesignVersion.design_id == design.id)
    )
    remaining_versions = result.scalars().all()
    assert len(remaining_versions) == 0


@pytest.mark.asyncio
async def test_delete_design_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test deleting non-existent design returns 404."""
    response = await client.delete("/api/designs/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_design_access_denied(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test deleting another user's design returns 404."""
    from auth.security import get_password_hash

    other_user = User(username="otheruser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(other_user)
    await db_session.flush()

    design = Design(user_id=other_user.id, name="Other Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    response = await client.delete(f"/api/designs/{design.id}", headers=auth_headers)
    assert response.status_code == 404

    result = await db_session.execute(select(Design).where(Design.id == design.id))
    still_exists = result.scalar_one_or_none()
    assert still_exists is not None


@pytest.mark.asyncio
async def test_delete_design_unauthenticated(
    client: AsyncClient,
    auth_user: User,
    db_session: AsyncSession,
):
    """Test deleting design without authentication returns 401."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    response = await client.delete(f"/api/designs/{design.id}")
    assert response.status_code == 401
