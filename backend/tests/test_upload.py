"""Tests for file upload functionality."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Material, User
from upload.service import MAX_FILE_SIZE, UploadService


@pytest.fixture
def mock_storage():
    """Mock storage service."""
    storage = AsyncMock()
    storage.upload = AsyncMock(return_value="/path/to/stored/file.jpg")
    storage.get_url = AsyncMock(return_value="http://localhost:8000/uploads/file.jpg")
    return storage


@pytest.fixture
def valid_jpeg_bytes():
    """Valid JPEG file bytes (minimal JPEG header)."""
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
        b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
        b"\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00"
        b"\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01"
        b"\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07"
        b"\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05"
        b"\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"
        b'"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18'
        b"\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87"
        b"\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7"
        b"\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7"
        b"\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6"
        b"\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08"
        b"\x01\x01\x00\x00?\x00\xff\xd9"
    )


@pytest.fixture
def valid_png_bytes():
    """Valid PNG file bytes (minimal PNG header)."""
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    user = User(username="testuser", password_hash="hashed_password")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_upload_service_valid_file(
    db_session: AsyncSession, test_user: User, mock_storage, valid_jpeg_bytes
):
    """Test uploading a valid JPEG file."""
    with patch("upload.service.get_storage_service", return_value=mock_storage):
        service = UploadService(db_session)
        result = await service.upload_material(valid_jpeg_bytes, "test.jpg", test_user)
        await db_session.commit()

        assert result.original_filename == "test.jpg"
        assert result.mime_type == "image/jpeg"
        assert result.file_size == len(valid_jpeg_bytes)
        assert result.url == "http://localhost:8000/uploads/file.jpg"
        assert ".jpg" in result.stored_filename

        from sqlalchemy.future import select

        stmt = select(Material).filter_by(original_filename="test.jpg")
        materials = await db_session.execute(stmt)
        material = materials.scalar_one_or_none()
        assert material is not None
        assert material.uploaded_by == test_user.id


async def test_upload_service_file_too_large(
    db_session: AsyncSession, test_user: User, mock_storage
):
    """Test uploading a file that exceeds size limit."""
    large_file = b"x" * (MAX_FILE_SIZE + 1)

    with patch("upload.service.get_storage_service", return_value=mock_storage):
        service = UploadService(db_session)
        with pytest.raises(ValueError, match="size exceeds"):
            await service.upload_material(large_file, "large.jpg", test_user)


async def test_upload_service_unsupported_type(
    db_session: AsyncSession, test_user: User, mock_storage
):
    """Test uploading an unsupported file type."""
    exe_bytes = b"MZ\x90\x00"

    with patch("upload.service.get_storage_service", return_value=mock_storage):
        service = UploadService(db_session)
        with pytest.raises(ValueError, match="Unsupported file type"):
            await service.upload_material(exe_bytes, "virus.exe", test_user)


@pytest.mark.parametrize(
    "file_bytes,extension,expected_mime",
    [
        pytest.param(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
            ".png",
            "image/png",
            id="png",
        ),
        pytest.param(
            b"RIFF\x00\x00\x00\x00WEBPVP8 ",
            ".webp",
            "image/webp",
            id="webp",
        ),
    ],
)
async def test_upload_service_different_formats(
    db_session: AsyncSession,
    test_user: User,
    mock_storage,
    file_bytes,
    extension,
    expected_mime,
):
    """Test uploading different supported image formats."""
    with patch("upload.service.get_storage_service", return_value=mock_storage):
        service = UploadService(db_session)
        result = await service.upload_material(file_bytes, f"test{extension}", test_user)

        assert result.mime_type == expected_mime
        assert extension in result.stored_filename


async def test_upload_endpoint_success(client: AsyncClient, test_env, valid_jpeg_bytes):
    """Test successful file upload via API endpoint."""
    register_response = await client.post(
        "/api/auth/register",
        json={"username": "uploader", "password": "Test123!@#"},
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/auth/login",
        json={"username": "uploader", "password": "Test123!@#"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    with patch("backend.upload.service.get_storage_service") as mock_get_storage:
        mock_storage = AsyncMock()
        mock_storage.upload = AsyncMock(return_value="/uploads/stored.jpg")
        mock_storage.get_url = AsyncMock(return_value="http://localhost:8000/uploads/stored.jpg")
        mock_get_storage.return_value = mock_storage

        files = {"file": ("test.jpg", io.BytesIO(valid_jpeg_bytes), "image/jpeg")}
        upload_response = await client.post(
            "/api/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert upload_response.status_code == 201
        data = upload_response.json()
        assert data["original_filename"] == "test.jpg"
        assert data["mime_type"] == "image/jpeg"
        assert data["file_size"] == len(valid_jpeg_bytes)
        assert "url" in data


async def test_upload_endpoint_unauthenticated(client: AsyncClient, valid_jpeg_bytes):
    """Test upload endpoint rejects unauthenticated requests."""
    files = {"file": ("test.jpg", io.BytesIO(valid_jpeg_bytes), "image/jpeg")}
    response = await client.post("/api/upload", files=files)

    assert response.status_code == 401


async def test_upload_endpoint_file_too_large(client: AsyncClient, test_env):
    """Test upload endpoint rejects files exceeding size limit."""
    register_response = await client.post(
        "/api/auth/register",
        json={"username": "uploader2", "password": "Test123!@#"},
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/auth/login",
        json={"username": "uploader2", "password": "Test123!@#"},
    )
    token = login_response.json()["access_token"]

    large_file = b"x" * (MAX_FILE_SIZE + 1)
    files = {"file": ("large.jpg", io.BytesIO(large_file), "image/jpeg")}

    response = await client.post(
        "/api/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 413


async def test_upload_endpoint_unsupported_type(client: AsyncClient, test_env):
    """Test upload endpoint rejects unsupported file types."""
    register_response = await client.post(
        "/api/auth/register",
        json={"username": "uploader3", "password": "Test123!@#"},
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/auth/login",
        json={"username": "uploader3", "password": "Test123!@#"},
    )
    token = login_response.json()["access_token"]

    exe_file = b"MZ\x90\x00" + b"\x00" * 100
    files = {"file": ("virus.exe", io.BytesIO(exe_file), "application/x-msdownload")}

    response = await client.post(
        "/api/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 415


async def test_upload_endpoint_missing_file(client: AsyncClient, test_env):
    """Test upload endpoint rejects requests without file."""
    register_response = await client.post(
        "/api/auth/register",
        json={"username": "uploader4", "password": "Test123!@#"},
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/auth/login",
        json={"username": "uploader4", "password": "Test123!@#"},
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/api/upload",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
