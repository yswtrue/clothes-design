"""Tests for template management API."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Role, Template, User, UserRole


@pytest.fixture
async def admin_user(db_session: AsyncSession):
    """Create admin user with admin role."""
    from auth.security import hash_password

    admin_role = Role(name="admin", permissions={"*": True})
    db_session.add(admin_role)
    await db_session.flush()

    admin = User(username="adminuser", password_hash=hash_password("Admin123!@#"))
    db_session.add(admin)
    await db_session.flush()

    user_role = UserRole(user_id=admin.id, role_id=admin_role.id)
    db_session.add(user_role)
    await db_session.commit()
    await db_session.refresh(admin)

    return admin


@pytest.fixture
async def admin_headers(client: AsyncClient, admin_user: User, test_env) -> dict:
    """Get auth headers for admin user."""
    response = await client.post(
        "/api/auth/login", json={"username": "adminuser", "password": "Admin123!@#"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def sample_template(db_session: AsyncSession):
    """Create a sample template."""
    template = Template(
        name="Test Template",
        image_path="/static/templates/test.png",
        category="t-shirt",
        is_builtin=0,
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.mark.asyncio
async def test_get_templates_public(client: AsyncClient):
    """Public endpoint returns all templates without authentication."""
    response = await client.get("/api/templates")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_templates_returns_correct_data(client: AsyncClient, sample_template: Template):
    """Verify template response structure and data."""
    response = await client.get("/api/templates")
    assert response.status_code == 200

    templates = response.json()
    assert len(templates) == 1

    template = templates[0]
    assert template["id"] == sample_template.id
    assert template["name"] == "Test Template"
    assert template["image_path"] == "/static/templates/test.png"
    assert template["category"] == "t-shirt"
    assert template["is_builtin"] == 0
    assert "created_at" in template


@pytest.mark.asyncio
async def test_create_template_admin_success(client: AsyncClient, admin_headers: dict):
    """Admin can create new templates."""
    with patch("storage.factory.get_storage_service") as mock_storage:
        mock_service = AsyncMock()
        mock_service.upload.return_value = "/uploads/templates/test_template.png"
        mock_storage.return_value = mock_service

        files = {"file": ("test.png", io.BytesIO(b"fake image data"), "image/png")}
        data = {"name": "New Template", "category": "hoodie"}

        response = await client.post(
            "/api/templates", files=files, data=data, headers=admin_headers
        )

        assert response.status_code == 200
        result = response.json()
        assert result["name"] == "New Template"
        assert result["category"] == "hoodie"
        assert result["is_builtin"] == 0
        assert "/uploads/templates/" in result["image_path"]


@pytest.mark.asyncio
async def test_create_template_non_admin_fails(
    client: AsyncClient, auth_headers: dict, admin_user: User
):
    """Non-admin users cannot create templates."""
    files = {"file": ("test.png", io.BytesIO(b"fake image data"), "image/png")}
    data = {"name": "New Template", "category": "t-shirt"}

    response = await client.post("/api/templates", files=files, data=data, headers=auth_headers)

    assert response.status_code == 403
    assert "Permission denied" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_template_no_auth_fails(client: AsyncClient):
    """Unauthenticated requests cannot create templates."""
    files = {"file": ("test.png", io.BytesIO(b"fake image data"), "image/png")}
    data = {"name": "New Template", "category": "t-shirt"}

    response = await client.post("/api/templates", files=files, data=data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_template_invalid_file_type(client: AsyncClient, admin_headers: dict):
    """Template creation fails with non-image files."""
    files = {"file": ("test.txt", io.BytesIO(b"plain text"), "text/plain")}
    data = {"name": "Invalid Template", "category": "t-shirt"}

    response = await client.post("/api/templates", files=files, data=data, headers=admin_headers)

    assert response.status_code == 400
    assert "must be an image" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_template_invalid_category(client: AsyncClient, admin_headers: dict):
    """Template creation fails with invalid category."""
    with patch("storage.factory.get_storage_service") as mock_storage:
        mock_service = AsyncMock()
        mock_service.upload.return_value = "/uploads/templates/test.png"
        mock_storage.return_value = mock_service

        files = {"file": ("test.png", io.BytesIO(b"fake image data"), "image/png")}
        data = {"name": "Invalid Category Template", "category": "invalid-category"}

        response = await client.post(
            "/api/templates", files=files, data=data, headers=admin_headers
        )

        assert response.status_code == 400
        assert "Invalid category" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_template_admin_success(
    client: AsyncClient, admin_headers: dict, sample_template: Template
):
    """Admin can delete non-builtin templates."""
    response = await client.delete(f"/api/templates/{sample_template.id}", headers=admin_headers)

    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]

    verify_response = await client.get("/api/templates")
    templates = verify_response.json()
    assert len(templates) == 0


@pytest.mark.asyncio
async def test_delete_template_builtin_fails(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """Admin cannot delete built-in templates."""
    builtin_template = Template(
        name="Built-in Template",
        image_path="/static/templates/builtin.png",
        category="t-shirt",
        is_builtin=1,
    )
    db_session.add(builtin_template)
    await db_session.commit()
    await db_session.refresh(builtin_template)

    response = await client.delete(f"/api/templates/{builtin_template.id}", headers=admin_headers)

    assert response.status_code == 403
    assert "Cannot delete built-in templates" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_template_not_found(client: AsyncClient, admin_headers: dict):
    """Deleting non-existent template returns 404."""
    response = await client.delete("/api/templates/99999", headers=admin_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_template_non_admin_fails(
    client: AsyncClient, auth_headers: dict, sample_template: Template, admin_user: User
):
    """Non-admin users cannot delete templates."""
    response = await client.delete(f"/api/templates/{sample_template.id}", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_template_no_auth_fails(client: AsyncClient, sample_template: Template):
    """Unauthenticated requests cannot delete templates."""
    response = await client.delete(f"/api/templates/{sample_template.id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_templates_ordered_by_id(client: AsyncClient, db_session: AsyncSession):
    """Templates are returned in consistent order."""
    templates_data = [
        {"name": "Template A", "category": "t-shirt"},
        {"name": "Template B", "category": "hoodie"},
        {"name": "Template C", "category": "tank"},
    ]

    for tpl in templates_data:
        template = Template(
            name=tpl["name"],
            image_path=f"/static/templates/{tpl['name'].lower().replace(' ', '_')}.png",
            category=tpl["category"],
            is_builtin=0,
        )
        db_session.add(template)

    await db_session.commit()

    response = await client.get("/api/templates")
    assert response.status_code == 200

    templates = response.json()
    assert len(templates) == 3
    assert templates[0]["name"] == "Template A"
    assert templates[1]["name"] == "Template B"
    assert templates[2]["name"] == "Template C"
