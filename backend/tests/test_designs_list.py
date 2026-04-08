"""Tests for designs list API endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Design, DesignVersion, User


@pytest.mark.asyncio
async def test_list_designs_success(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test successful design listing."""
    design1 = Design(user_id=auth_user.id, name="Design 1", status="draft")
    design2 = Design(user_id=auth_user.id, name="Design 2", status="published")
    design3 = Design(user_id=auth_user.id, name="Design 3", status="draft")
    db_session.add_all([design1, design2, design3])
    await db_session.flush()

    version1 = DesignVersion(design_id=design1.id, version=1, data={"test": "data1"})
    version2_1 = DesignVersion(design_id=design2.id, version=1, data={"test": "data2"})
    version2_2 = DesignVersion(design_id=design2.id, version=2, data={"test": "data2_v2"})
    db_session.add_all([version1, version2_1, version2_2])
    await db_session.commit()

    response = await client.get("/api/designs", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["pages"] == 1
    assert len(data["designs"]) == 3

    design_names = {d["name"] for d in data["designs"]}
    assert design_names == {"Design 1", "Design 2", "Design 3"}

    design2_data = next(d for d in data["designs"] if d["name"] == "Design 2")
    assert design2_data["versions_count"] == 2

    design1_data = next(d for d in data["designs"] if d["name"] == "Design 1")
    assert design1_data["versions_count"] == 1

    design3_data = next(d for d in data["designs"] if d["name"] == "Design 3")
    assert design3_data["versions_count"] == 0


@pytest.mark.asyncio
async def test_list_designs_pagination(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test pagination works correctly."""
    designs = [Design(user_id=auth_user.id, name=f"Design {i}", status="draft") for i in range(25)]
    db_session.add_all(designs)
    await db_session.commit()

    response_page1 = await client.get("/api/designs?page=1&limit=10", headers=auth_headers)
    assert response_page1.status_code == 200
    data_page1 = response_page1.json()
    assert data_page1["total"] == 25
    assert data_page1["page"] == 1
    assert data_page1["pages"] == 3
    assert len(data_page1["designs"]) == 10

    response_page2 = await client.get("/api/designs?page=2&limit=10", headers=auth_headers)
    assert response_page2.status_code == 200
    data_page2 = response_page2.json()
    assert data_page2["total"] == 25
    assert data_page2["page"] == 2
    assert data_page2["pages"] == 3
    assert len(data_page2["designs"]) == 10

    response_page3 = await client.get("/api/designs?page=3&limit=10", headers=auth_headers)
    assert response_page3.status_code == 200
    data_page3 = response_page3.json()
    assert data_page3["page"] == 3
    assert len(data_page3["designs"]) == 5

    page1_names = {d["name"] for d in data_page1["designs"]}
    page2_names = {d["name"] for d in data_page2["designs"]}
    assert len(page1_names & page2_names) == 0


@pytest.mark.asyncio
async def test_list_designs_empty(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test listing when user has no designs."""
    response = await client.get("/api/designs", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 0
    assert len(data["designs"]) == 0


@pytest.mark.asyncio
async def test_list_designs_only_own_designs(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test that users only see their own designs."""
    from auth.security import get_password_hash

    other_user = User(username="otheruser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(other_user)
    await db_session.flush()

    own_design = Design(user_id=auth_user.id, name="My Design", status="draft")
    other_design = Design(user_id=other_user.id, name="Other Design", status="draft")
    db_session.add_all([own_design, other_design])
    await db_session.commit()

    response = await client.get("/api/designs", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["designs"]) == 1
    assert data["designs"][0]["name"] == "My Design"


@pytest.mark.asyncio
async def test_list_designs_unauthenticated(
    client: AsyncClient,
):
    """Test listing designs without authentication returns 401."""
    response = await client.get("/api/designs")
    assert response.status_code == 401
