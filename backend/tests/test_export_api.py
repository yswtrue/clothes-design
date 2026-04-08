"""Tests for export API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Design, DesignVersion


@pytest.fixture
async def test_design_with_pattern(db_session: AsyncSession, test_user):
    design = Design(
        user_id=test_user.id,
        name="Test Design",
        status="generated",
    )
    db_session.add(design)
    await db_session.commit()
    await db_session.refresh(design)

    version = DesignVersion(
        design_id=design.id,
        version=1,
        data={
            "pattern_url": "s3://bucket/patterns/test-pattern.png",
            "template_id": 1,
        },
    )
    db_session.add(version)
    await db_session.commit()
    return design


@pytest.fixture
async def test_design_without_pattern(db_session: AsyncSession, test_user):
    design = Design(
        user_id=test_user.id,
        name="Empty Design",
        status="draft",
    )
    db_session.add(design)
    await db_session.commit()
    await db_session.refresh(design)

    version = DesignVersion(
        design_id=design.id,
        version=1,
        data={"template_id": 1},
    )
    db_session.add(version)
    await db_session.commit()
    return design


@pytest.fixture
async def other_user_design(db_session: AsyncSession):
    design = Design(
        user_id=999,
        name="Other User Design",
        status="generated",
    )
    db_session.add(design)
    await db_session.commit()
    await db_session.refresh(design)

    version = DesignVersion(
        design_id=design.id,
        version=1,
        data={"pattern_url": "s3://bucket/patterns/other.png"},
    )
    db_session.add(version)
    await db_session.commit()
    return design


@pytest.mark.asyncio
@patch("api.export.enqueue_task")
async def test_trigger_export_success(
    mock_enqueue, client: AsyncClient, auth_headers: dict, test_design_with_pattern: Design
):
    mock_enqueue.return_value = "export-task-123"

    response = await client.post(
        f"/api/export/designs/{test_design_with_pattern.id}",
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["task_id"] == "export-task-123"
    assert data["design_id"] == test_design_with_pattern.id
    assert data["status"] == "pending"
    mock_enqueue.assert_called_once()

    call_args = mock_enqueue.call_args
    assert call_args[1]["task_type"] == "export_pattern"
    assert call_args[1]["data"]["design_id"] == test_design_with_pattern.id
    assert call_args[1]["data"]["target_resolution"] == 12000
    assert call_args[1]["data"]["color_space"] == "CMYK"


@pytest.mark.asyncio
async def test_trigger_export_design_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/export/designs/99999",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_export_access_denied(
    client: AsyncClient, auth_headers: dict, other_user_design: Design
):
    response = await client.post(
        f"/api/export/designs/{other_user_design.id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_export_no_pattern(
    client: AsyncClient, auth_headers: dict, test_design_without_pattern: Design
):
    response = await client.post(
        f"/api/export/designs/{test_design_without_pattern.id}",
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "no pattern" in data["detail"].lower()


@pytest.mark.asyncio
async def test_trigger_export_unauthenticated(
    client: AsyncClient, test_design_with_pattern: Design
):
    response = await client.post(
        f"/api/export/designs/{test_design_with_pattern.id}",
    )

    assert response.status_code == 401


@pytest.mark.asyncio
@patch("api.export.get_task_status")
async def test_get_export_status_pending(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime, UTC

    mock_get_status.return_value = TaskStatus(
        task_id="export-task-123",
        task_type="export_pattern",
        user_id=test_user.id,
        status="pending",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        data={"design_id": 1, "target_resolution": 12000},
        result=None,
        error=None,
    )

    response = await client.get(
        "/api/export/tasks/export-task-123",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "export-task-123"
    assert data["status"] == "pending"
    assert data["design_id"] == 1
    assert data["progress"] == 0
    assert data["current_step"] is None
    assert data["download_url"] is None


@pytest.mark.asyncio
@patch("api.export.get_task_status")
async def test_get_export_status_processing_upscaling(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime, UTC

    mock_get_status.return_value = TaskStatus(
        task_id="export-task-456",
        task_type="export_pattern",
        user_id=test_user.id,
        status="processing",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        data={"design_id": 2, "current_step": "upscaling"},
        result=None,
        error=None,
    )

    response = await client.get(
        "/api/export/tasks/export-task-456",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["current_step"] == "upscaling"
    assert data["progress"] == 25


@pytest.mark.asyncio
@patch("api.export.get_task_status")
async def test_get_export_status_processing_vectorizing(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime, UTC

    mock_get_status.return_value = TaskStatus(
        task_id="export-task-789",
        task_type="export_pattern",
        user_id=test_user.id,
        status="processing",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        data={"design_id": 3, "current_step": "vectorizing"},
        result=None,
        error=None,
    )

    response = await client.get(
        "/api/export/tasks/export-task-789",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["current_step"] == "vectorizing"
    assert data["progress"] == 60


@pytest.mark.asyncio
@patch("api.export.get_task_status")
async def test_get_export_status_completed(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime, UTC

    mock_get_status.return_value = TaskStatus(
        task_id="export-task-complete",
        task_type="export_pattern",
        user_id=test_user.id,
        status="completed",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        data={"design_id": 4},
        result={
            "download_url": "s3://bucket/exports/design-4-12K-CMYK.tif",
            "design_id": 4,
            "resolution": 12000,
            "color_space": "CMYK",
            "format": "tif",
        },
        error=None,
    )

    response = await client.get(
        "/api/export/tasks/export-task-complete",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"
    assert data["progress"] == 100
    assert data["current_step"] == "complete"
    assert data["download_url"] == "s3://bucket/exports/design-4-12K-CMYK.tif"


@pytest.mark.asyncio
@patch("api.export.get_task_status")
async def test_get_export_status_failed(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime, UTC

    mock_get_status.return_value = TaskStatus(
        task_id="export-task-failed",
        task_type="export_pattern",
        user_id=test_user.id,
        status="failed",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        data={"design_id": 5},
        result=None,
        error="Provider timeout during upscaling",
    )

    response = await client.get(
        "/api/export/tasks/export-task-failed",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error"] == "Provider timeout during upscaling"


@pytest.mark.asyncio
@patch("api.export.get_task_status")
async def test_get_export_status_not_found(
    mock_get_status, client: AsyncClient, auth_headers: dict
):
    mock_get_status.return_value = None

    response = await client.get(
        "/api/export/tasks/nonexistent-task",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@patch("api.export.get_task_status")
async def test_get_export_status_access_denied(
    mock_get_status, client: AsyncClient, auth_headers: dict, test_user
):
    from task_queue.schemas import TaskStatus
    from datetime import datetime, UTC

    mock_get_status.return_value = TaskStatus(
        task_id="export-task-other",
        task_type="export_pattern",
        user_id=999,
        status="pending",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        data={"design_id": 6},
        result=None,
        error=None,
    )

    response = await client.get(
        "/api/export/tasks/export-task-other",
        headers=auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_export_status_unauthenticated(client: AsyncClient):
    response = await client.get("/api/export/tasks/some-task")

    assert response.status_code == 401
