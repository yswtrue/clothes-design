"""Tests for designs API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Design, DesignVersion, Template, User


@pytest.mark.asyncio
async def test_create_design_success(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test successful design creation."""
    response = await client.post(
        "/api/designs",
        headers=auth_headers,
        json={"name": "New Design"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "New Design"
    assert data["status"] == "draft"
    assert data["user_id"] > 0
    assert data["preview_state"] is None

    from sqlalchemy import select

    result = await db_session.execute(
        select(DesignVersion).where(DesignVersion.design_id == data["id"])
    )
    versions = result.scalars().all()
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].data == {}


@pytest.mark.asyncio
async def test_create_design_invalid_name(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test design creation with invalid name."""
    response = await client.post(
        "/api/designs",
        headers=auth_headers,
        json={"name": ""},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_design_success(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test successful design retrieval."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version = DesignVersion(
        design_id=design.id,
        version=1,
        data={
            "pattern_url": "http://example.com/pattern.png",
            "template_id": 1,
            "position": {"x": 100, "y": 150, "scale": 1.5, "rotation": 0, "opacity": 1.0},
            "colors": {"hue": 10, "saturation": 20, "brightness": 5},
        },
    )
    db_session.add(version)
    await db_session.commit()

    response = await client.get(f"/api/designs/{design.id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == design.id
    assert data["name"] == "Test Design"
    assert data["preview_state"] is not None
    assert data["preview_state"]["pattern_url"] == "http://example.com/pattern.png"
    assert data["preview_state"]["template_id"] == 1
    assert data["preview_state"]["position"]["scale"] == 1.5


@pytest.mark.asyncio
async def test_get_design_not_found(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test design not found returns 404."""
    response = await client.get("/api/designs/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_design_no_preview_state(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test design without preview state returns null."""
    design = Design(user_id=auth_user.id, name="Empty Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    response = await client.get(f"/api/designs/{design.id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == design.id
    assert data["preview_state"] is None


@pytest.mark.asyncio
async def test_update_design_template(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test updating design template."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    response = await client.patch(
        f"/api/designs/{design.id}",
        headers=auth_headers,
        json={"template_id": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["preview_state"]["template_id"] == 2


@pytest.mark.asyncio
async def test_update_design_position(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test updating design position."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    new_position = {"x": 200, "y": 300, "scale": 2.0, "rotation": 45, "opacity": 0.8}
    response = await client.patch(
        f"/api/designs/{design.id}",
        headers=auth_headers,
        json={"position": new_position},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["preview_state"]["position"]["x"] == 200
    assert data["preview_state"]["position"]["scale"] == 2.0
    assert data["preview_state"]["position"]["rotation"] == 45


@pytest.mark.asyncio
async def test_update_design_colors(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test updating design colors."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    new_colors = {"hue": 30, "saturation": 50, "brightness": -10}
    response = await client.patch(
        f"/api/designs/{design.id}",
        headers=auth_headers,
        json={"colors": new_colors},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["preview_state"]["colors"]["hue"] == 30
    assert data["preview_state"]["colors"]["saturation"] == 50
    assert data["preview_state"]["colors"]["brightness"] == -10


@pytest.mark.asyncio
async def test_update_design_creates_version(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test that update creates a new version."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version1 = DesignVersion(
        design_id=design.id,
        version=1,
        data={"template_id": 1, "position": {"x": 0, "y": 0, "scale": 1.0, "rotation": 0}},
    )
    db_session.add(version1)
    await db_session.commit()

    response = await client.patch(
        f"/api/designs/{design.id}",
        headers=auth_headers,
        json={"template_id": 2},
    )

    assert response.status_code == 200

    from sqlalchemy import select

    result = await db_session.execute(
        select(DesignVersion).where(DesignVersion.design_id == design.id)
    )
    versions = result.scalars().all()
    assert len(versions) == 2
    assert versions[1].version == 2


@pytest.mark.asyncio
async def test_generate_preview_missing_state(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test preview generation fails without state."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.commit()

    response = await client.get(f"/api/designs/{design.id}/preview", headers=auth_headers)

    assert response.status_code == 400
    assert "no preview state" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_preview_missing_pattern_url(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test preview generation fails without pattern URL."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version = DesignVersion(
        design_id=design.id,
        version=1,
        data={"template_id": 1, "position": {"x": 0, "y": 0, "scale": 1.0, "rotation": 0}},
    )
    db_session.add(version)
    await db_session.commit()

    response = await client.get(f"/api/designs/{design.id}/preview", headers=auth_headers)

    assert response.status_code == 400
    assert "no pattern url" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_preview_missing_template(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test preview generation fails without template."""
    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version = DesignVersion(
        design_id=design.id,
        version=1,
        data={
            "pattern_url": "http://example.com/pattern.png",
            "position": {"x": 0, "y": 0, "scale": 1.0, "rotation": 0},
        },
    )
    db_session.add(version)
    await db_session.commit()

    response = await client.get(f"/api/designs/{design.id}/preview", headers=auth_headers)

    assert response.status_code == 400
    assert "no template selected" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_preview_success(
    client: AsyncClient,
    auth_user: User,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Test successful preview generation with MockupsProvider integration."""
    template = Template(
        name="Test T-Shirt",
        category="t-shirt",
        image_path="templates/tshirt.png",
        is_builtin=1,
    )
    db_session.add(template)
    await db_session.flush()

    design = Design(user_id=auth_user.id, name="Test Design", status="draft")
    db_session.add(design)
    await db_session.flush()

    version = DesignVersion(
        design_id=design.id,
        version=1,
        data={
            "pattern_url": "patterns/test-pattern.png",
            "template_id": template.id,
            "position": {"x": 100, "y": 150, "scale": 1.5, "rotation": 0, "opacity": 1.0},
            "colors": {"hue": 0, "saturation": 0, "brightness": 0},
        },
    )
    db_session.add(version)
    await db_session.commit()

    mock_storage = AsyncMock()
    mock_storage.download = AsyncMock(return_value=b"fake_image_bytes")
    mock_storage.upload = AsyncMock(return_value="https://storage.example.com/preview.png")

    mock_provider = AsyncMock()
    mock_provider.composite_mockup = AsyncMock(return_value=b"composite_result_bytes")

    with (
        patch("api.designs.get_storage_service", return_value=mock_storage),
        patch("api.designs.MockupsProvider", return_value=mock_provider),
    ):
        response = await client.get(f"/api/designs/{design.id}/preview", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "preview_url" in data
    assert data["preview_url"] == "https://storage.example.com/preview.png"

    assert mock_storage.download.call_count == 2
    mock_storage.download.assert_any_call("patterns/test-pattern.png")
    mock_storage.download.assert_any_call("templates/tshirt.png")

    mock_provider.composite_mockup.assert_called_once()
    call_args = mock_provider.composite_mockup.call_args
    assert call_args.kwargs["pattern"] == b"fake_image_bytes"
    assert call_args.kwargs["template"] == b"fake_image_bytes"
    assert call_args.kwargs["position"].x == 100
    assert call_args.kwargs["position"].y == 150
    assert call_args.kwargs["position"].scale == 1.5

    mock_storage.upload.assert_called_once()
    upload_call = mock_storage.upload.call_args
    assert upload_call.args[0] == b"composite_result_bytes"
    assert "previews/" in upload_call.args[1]
    assert str(design.id) in upload_call.args[1]
