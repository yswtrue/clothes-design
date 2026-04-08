"""Tests for pattern generation API."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Design, Material


@pytest.fixture
async def test_material_with_analysis(db_session: AsyncSession, test_user):
    material = Material(
        uploaded_by=test_user.id,
        original_filename="fabric.jpg",
        stored_filename="fabric-uuid.jpg",
        file_size=2048,
        mime_type="image/jpeg",
        storage_path="/materials/fabric-uuid.jpg",
        meta={
            "style_analysis": {
                "style_description": "Geometric pattern with bold colors",
                "color_palette": ["#FF0000", "#0000FF", "#00FF00"],
                "pattern_type": "seamless",
                "suggested_params": {"tiling": "reflect"},
            }
        },
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)
    return material


@pytest.fixture
async def test_material_without_analysis(db_session: AsyncSession, test_user):
    material = Material(
        uploaded_by=test_user.id,
        original_filename="plain.jpg",
        stored_filename="plain-uuid.jpg",
        file_size=1024,
        mime_type="image/png",
        storage_path="/materials/plain-uuid.jpg",
        meta={},
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
        file_size=512,
        mime_type="image/jpeg",
        storage_path="/materials/other-uuid.jpg",
        meta={"style_analysis": {"style_description": "test", "pattern_type": "full"}},
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)
    return material


@pytest.mark.asyncio
@patch("api.generate.enqueue_task")
async def test_generate_pattern_success(
    mock_enqueue, client: AsyncClient, auth_headers: dict, test_material_with_analysis: Material
):
    mock_enqueue.return_value = "test-task-id-123"

    response = await client.post(
        "/api/generate",
        headers=auth_headers,
        json={"material_id": test_material_with_analysis.id, "pattern_type": "seamless"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == "test-task-id-123"
    assert "design_id" in data
    assert data["status"] == "pending"
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
@patch("api.generate.enqueue_task")
async def test_generate_pattern_with_custom_prompt(
    mock_enqueue, client: AsyncClient, auth_headers: dict, test_material_with_analysis: Material
):
    mock_enqueue.return_value = "test-task-id-456"

    response = await client.post(
        "/api/generate",
        headers=auth_headers,
        json={
            "material_id": test_material_with_analysis.id,
            "pattern_type": "standalone",
            "prompt": "Custom floral design",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == "test-task-id-456"
    assert data["status"] == "pending"


@pytest.mark.asyncio
@patch("api.generate.enqueue_task")
async def test_generate_pattern_with_custom_colors(
    mock_enqueue, client: AsyncClient, auth_headers: dict, test_material_with_analysis: Material
):
    mock_enqueue.return_value = "test-task-id-789"

    response = await client.post(
        "/api/generate",
        headers=auth_headers,
        json={
            "material_id": test_material_with_analysis.id,
            "pattern_type": "seamless",
            "colors": ["#AABBCC", "#DDEEFF"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == "test-task-id-789"


@pytest.mark.asyncio
async def test_generate_pattern_material_not_found(
    client: AsyncClient, auth_headers: dict, test_material_with_analysis: Material
):
    response = await client.post(
        "/api/generate",
        headers=auth_headers,
        json={"material_id": 99999, "pattern_type": "seamless"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_pattern_other_user_material(
    client: AsyncClient, auth_headers: dict, other_user_material: Material
):
    response = await client.post(
        "/api/generate",
        headers=auth_headers,
        json={"material_id": other_user_material.id, "pattern_type": "seamless"},
    )

    assert response.status_code == 404
    assert "access denied" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_pattern_without_auth(
    client: AsyncClient, test_material_with_analysis: Material
):
    response = await client.post(
        "/api/generate",
        json={"material_id": test_material_with_analysis.id, "pattern_type": "seamless"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_pattern_no_analysis_no_prompt(
    client: AsyncClient, auth_headers: dict, test_material_without_analysis: Material
):
    response = await client.post(
        "/api/generate",
        headers=auth_headers,
        json={"material_id": test_material_without_analysis.id, "pattern_type": "full"},
    )

    assert response.status_code == 400
    assert "no style analysis" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("api.generate.enqueue_task")
async def test_generate_pattern_no_analysis_with_prompt(
    mock_enqueue, client: AsyncClient, auth_headers: dict, test_material_without_analysis: Material
):
    mock_enqueue.return_value = "test-task-id-no-analysis"

    response = await client.post(
        "/api/generate",
        headers=auth_headers,
        json={
            "material_id": test_material_without_analysis.id,
            "pattern_type": "standalone",
            "prompt": "Manual abstract design",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == "test-task-id-no-analysis"


@pytest.mark.asyncio
@patch("api.generate.get_task_status")
async def test_get_task_status_success(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime

    mock_get_status.return_value = TaskStatus(
        task_id="test-task-123",
        task_type="generate_pattern",
        user_id=test_user.id,
        status="completed",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        result={"pattern_url": "https://example.com/pattern.png", "file_size": 2048},
        error=None,
    )

    response = await client.get("/api/generate/tasks/test-task-123", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-123"
    assert data["status"] == "completed"
    assert data["result"]["pattern_url"] == "https://example.com/pattern.png"
    assert data["error"] is None


@pytest.mark.asyncio
@patch("api.generate.get_task_status")
async def test_get_task_status_pending(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime

    mock_get_status.return_value = TaskStatus(
        task_id="test-task-pending",
        task_type="generate_pattern",
        user_id=test_user.id,
        status="pending",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    response = await client.get("/api/generate/tasks/test-task-pending", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["result"] is None


@pytest.mark.asyncio
@patch("api.generate.get_task_status")
async def test_get_task_status_failed(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime

    mock_get_status.return_value = TaskStatus(
        task_id="test-task-failed",
        task_type="generate_pattern",
        user_id=test_user.id,
        status="failed",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        error="Content policy violation",
    )

    response = await client.get("/api/generate/tasks/test-task-failed", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error"] == "Content policy violation"


@pytest.mark.asyncio
@patch("api.generate.get_task_status")
async def test_get_task_status_not_found(mock_get_status, client: AsyncClient, auth_headers: dict):
    mock_get_status.return_value = None

    response = await client.get("/api/generate/tasks/nonexistent-task", headers=auth_headers)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
@patch("api.generate.get_task_status")
async def test_get_task_status_other_user(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime

    mock_get_status.return_value = TaskStatus(
        task_id="test-task-other",
        task_type="generate_pattern",
        user_id=999,
        status="completed",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    response = await client.get("/api/generate/tasks/test-task-other", headers=auth_headers)

    assert response.status_code == 403
    assert "access denied" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_task_status_without_auth(client: AsyncClient):
    response = await client.get("/api/generate/tasks/test-task-123")

    assert response.status_code == 401


@pytest.mark.asyncio
@patch("api.generate.enqueue_task")
async def test_generate_pattern_creates_design_record(
    mock_enqueue,
    client: AsyncClient,
    auth_headers: dict,
    test_material_with_analysis: Material,
    db_session: AsyncSession,
):
    mock_enqueue.return_value = "test-task-design-record"

    response = await client.post(
        "/api/generate",
        headers=auth_headers,
        json={"material_id": test_material_with_analysis.id, "pattern_type": "seamless"},
    )

    assert response.status_code == 201
    data = response.json()
    design_id = data["design_id"]

    from sqlalchemy import select

    result = await db_session.execute(select(Design).where(Design.id == design_id))
    design = result.scalar_one_or_none()

    assert design is not None
    assert design.status == "generating"
    assert "Design-" in design.name
