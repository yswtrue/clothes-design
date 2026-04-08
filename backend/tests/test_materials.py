"""Tests for material management API."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Material


@pytest.fixture
async def test_material(db_session: AsyncSession, auth_headers: dict):
    material = Material(
        uploaded_by=1,
        original_filename="test.jpg",
        stored_filename="test-uuid.jpg",
        file_size=1024,
        mime_type="image/jpeg",
        storage_path="/materials/test-uuid.jpg",
        meta={"name": "Test Material", "tags": ["test", "sample"]},
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)
    return material


@pytest.fixture
async def other_user_material(db_session: AsyncSession):
    material = Material(
        uploaded_by=999,
        original_filename="other.jpg",
        stored_filename="other-uuid.jpg",
        file_size=2048,
        mime_type="image/png",
        storage_path="/materials/other-uuid.jpg",
        meta={"name": "Other Material"},
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)
    return material


@pytest.mark.asyncio
async def test_list_materials_success(
    client: AsyncClient, auth_headers: dict, test_material: Material
):
    response = await client.get("/api/materials", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_materials_with_filters(
    client: AsyncClient, auth_headers: dict, test_material: Material
):
    response = await client.get(
        "/api/materials",
        headers=auth_headers,
        params={
            "uploaded_by": test_material.uploaded_by,
            "mime_type": "image/jpeg",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_materials_with_sorting(
    client: AsyncClient, auth_headers: dict, test_material: Material
):
    response = await client.get(
        "/api/materials",
        headers=auth_headers,
        params={"sort_by": "file_size", "sort_order": "asc"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_materials_pagination(
    client: AsyncClient, auth_headers: dict, test_material: Material
):
    response = await client.get(
        "/api/materials",
        headers=auth_headers,
        params={"page": 1, "page_size": 10},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.asyncio
async def test_list_materials_unauthorized(client: AsyncClient):
    response = await client.get("/api/materials")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_material_success(
    client: AsyncClient, auth_headers: dict, test_material: Material
):
    response = await client.get(f"/api/materials/{test_material.id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_material.id
    assert data["original_filename"] == test_material.original_filename


@pytest.mark.asyncio
async def test_get_material_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/materials/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_material_success(
    client: AsyncClient, auth_headers: dict, test_material: Material
):
    update_data = {
        "name": "Updated Material",
        "tags": ["updated", "new"],
        "description": "This is an updated material",
    }

    response = await client.patch(
        f"/api/materials/{test_material.id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["name"] == "Updated Material"
    assert "updated" in data["meta"]["tags"]


@pytest.mark.asyncio
async def test_update_material_not_owner(
    client: AsyncClient, auth_headers: dict, other_user_material: Material
):
    update_data = {"name": "Hacked Material"}

    response = await client.patch(
        f"/api/materials/{other_user_material.id}",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_material_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.patch(
        "/api/materials/99999",
        headers=auth_headers,
        json={"name": "Test"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_material_success(
    client: AsyncClient,
    auth_headers: dict,
    test_material: Material,
    db_session: AsyncSession,
):
    response = await client.delete(f"/api/materials/{test_material.id}", headers=auth_headers)

    assert response.status_code == 204

    result = await db_session.execute(select(Material).filter(Material.id == test_material.id))
    deleted_material = result.scalar_one()
    assert deleted_material.meta.get("is_deleted") is True


@pytest.mark.asyncio
async def test_delete_material_not_owner(
    client: AsyncClient, auth_headers: dict, other_user_material: Material
):
    response = await client.delete(f"/api/materials/{other_user_material.id}", headers=auth_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_material_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.delete("/api/materials/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_search_materials_success(
    client: AsyncClient, auth_headers: dict, test_material: Material
):
    response = await client.get(
        "/api/materials/search/",
        headers=auth_headers,
        params={"q": "Test"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_search_materials_by_tags(
    client: AsyncClient, auth_headers: dict, test_material: Material
):
    response = await client.get(
        "/api/materials/search/",
        headers=auth_headers,
        params={"q": "sample"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_search_materials_no_query(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/materials/search/",
        headers=auth_headers,
    )
    assert response.status_code == 422
