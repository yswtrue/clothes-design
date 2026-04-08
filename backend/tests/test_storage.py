"""Tests for storage service implementations."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from backend.storage import (
    LocalStorage,
    S3Storage,
    StorageDownloadError,
    StorageURLError,
    get_storage_service,
)


class TestLocalStorage:
    """Tests for LocalStorage implementation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def storage(self, temp_dir):
        """Create LocalStorage instance."""
        return LocalStorage(upload_dir=temp_dir)

    @pytest.mark.asyncio
    async def test_upload_creates_file(self, storage: LocalStorage, temp_dir: str):
        """Test uploading file creates it on filesystem."""
        file_data = b"test file content"
        key = "test_file.txt"

        path = await storage.upload(file_data, key)

        assert Path(path).exists()
        assert Path(path).read_bytes() == file_data

    @pytest.mark.asyncio
    async def test_upload_creates_nested_directories(self, storage: LocalStorage, temp_dir: str):
        """Test uploading file with nested key creates directories."""
        file_data = b"test content"
        key = "path/to/nested/file.txt"

        path = await storage.upload(file_data, key)

        assert Path(path).exists()
        assert Path(path).read_bytes() == file_data

    @pytest.mark.asyncio
    async def test_download_returns_file_content(self, storage: LocalStorage, temp_dir: str):
        """Test downloading file returns correct content."""
        file_data = b"test file content"
        key = "test_file.txt"
        await storage.upload(file_data, key)

        downloaded = await storage.download(key)

        assert downloaded == file_data

    @pytest.mark.asyncio
    async def test_download_nonexistent_file_raises_error(self, storage: LocalStorage):
        """Test downloading nonexistent file raises StorageDownloadError."""
        with pytest.raises(StorageDownloadError):
            await storage.download("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_delete_removes_file(self, storage: LocalStorage, temp_dir: str):
        """Test deleting file removes it."""
        file_data = b"test content"
        key = "test_file.txt"
        file_path = await storage.upload(file_data, key)

        result = await storage.delete(key)

        assert result is True
        assert not Path(file_path).exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file_returns_false(self, storage: LocalStorage):
        """Test deleting nonexistent file returns False."""
        result = await storage.delete("nonexistent.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_url_returns_file_path(self, storage: LocalStorage, temp_dir: str):
        """Test get_url returns local file path."""
        file_data = b"test content"
        key = "test_file.txt"
        await storage.upload(file_data, key)

        url = await storage.get_url(key)

        assert url == str(Path(temp_dir) / key)
        assert Path(url).exists()

    @pytest.mark.asyncio
    async def test_get_url_nonexistent_file_raises_error(self, storage: LocalStorage):
        """Test get_url for nonexistent file raises StorageURLError."""
        with pytest.raises(StorageURLError):
            await storage.get_url("nonexistent.txt")


@mock_aws
def test_s3_upload_creates_object():
    """Test uploading file creates S3 object."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="test-bucket")
    storage = S3Storage(
        bucket_name="test-bucket",
        region_name="us-east-1",
        access_key="testing",
        secret_key="testing",
    )
    file_data = b"test file content"
    key = "test_file.txt"

    import asyncio

    result = asyncio.run(storage.upload(file_data, key))

    response = client.get_object(Bucket="test-bucket", Key=key)
    assert response["Body"].read() == file_data
    assert "s3://" in result or "test-bucket" in result


@mock_aws
def test_s3_upload_nested_key():
    """Test uploading file with nested key."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="test-bucket")
    storage = S3Storage(
        bucket_name="test-bucket",
        region_name="us-east-1",
        access_key="testing",
        secret_key="testing",
    )
    file_data = b"test content"
    key = "path/to/nested/file.txt"

    import asyncio

    asyncio.run(storage.upload(file_data, key))

    response = client.get_object(Bucket="test-bucket", Key=key)
    assert response["Body"].read() == file_data


@mock_aws
def test_s3_download_returns_object():
    """Test downloading file returns correct S3 object."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="test-bucket")
    storage = S3Storage(
        bucket_name="test-bucket",
        region_name="us-east-1",
        access_key="testing",
        secret_key="testing",
    )
    file_data = b"test file content"
    key = "test_file.txt"
    client.put_object(Bucket="test-bucket", Key=key, Body=file_data)

    import asyncio

    downloaded = asyncio.run(storage.download(key))

    assert downloaded == file_data


@mock_aws
def test_s3_download_nonexistent_raises_error():
    """Test downloading nonexistent file raises StorageDownloadError."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="test-bucket")
    storage = S3Storage(
        bucket_name="test-bucket",
        region_name="us-east-1",
        access_key="testing",
        secret_key="testing",
    )

    import asyncio

    with pytest.raises(StorageDownloadError):
        asyncio.run(storage.download("nonexistent.txt"))


@mock_aws
def test_s3_delete_removes_object():
    """Test deleting S3 object."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="test-bucket")
    storage = S3Storage(
        bucket_name="test-bucket",
        region_name="us-east-1",
        access_key="testing",
        secret_key="testing",
    )
    key = "test_file.txt"
    client.put_object(Bucket="test-bucket", Key=key, Body=b"content")

    import asyncio

    result = asyncio.run(storage.delete(key))

    assert result is True
    with pytest.raises(client.exceptions.NoSuchKey):
        client.get_object(Bucket="test-bucket", Key=key)


@mock_aws
def test_s3_delete_nonexistent_object():
    """Test deleting nonexistent S3 object returns True (S3 behavior)."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="test-bucket")
    storage = S3Storage(
        bucket_name="test-bucket",
        region_name="us-east-1",
        access_key="testing",
        secret_key="testing",
    )

    import asyncio

    result = asyncio.run(storage.delete("nonexistent.txt"))
    assert result is True


@mock_aws
def test_s3_get_url_returns_signed_url():
    """Test get_url returns signed URL."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="test-bucket")
    storage = S3Storage(
        bucket_name="test-bucket",
        region_name="us-east-1",
        access_key="testing",
        secret_key="testing",
    )
    key = "test_file.txt"
    client.put_object(Bucket="test-bucket", Key=key, Body=b"content")

    import asyncio

    url = asyncio.run(storage.get_url(key))

    assert url is not None
    assert "test-bucket" in url or "test_file.txt" in url


@mock_aws
def test_s3_get_url_with_custom_expires():
    """Test get_url with custom expiration."""
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="test-bucket")
    storage = S3Storage(
        bucket_name="test-bucket",
        region_name="us-east-1",
        access_key="testing",
        secret_key="testing",
    )
    key = "test_file.txt"
    client.put_object(Bucket="test-bucket", Key=key, Body=b"content")

    import asyncio

    url = asyncio.run(storage.get_url(key, expires=7200))

    assert url is not None


class TestStorageFactory:
    """Tests for storage factory function."""

    def test_get_storage_service_default_returns_local(self):
        """Test get_storage_service defaults to LocalStorage."""
        if "STORAGE_TYPE" in os.environ:
            del os.environ["STORAGE_TYPE"]
        storage = get_storage_service()
        assert isinstance(storage, LocalStorage)

    def test_get_storage_service_local(self):
        """Test get_storage_service returns LocalStorage when set to 'local'."""
        with patch.dict(os.environ, {"STORAGE_TYPE": "local"}):
            storage = get_storage_service()
            assert isinstance(storage, LocalStorage)

    def test_get_storage_service_s3(self):
        """Test get_storage_service returns S3Storage when set to 's3'."""
        with patch.dict(
            os.environ,
            {
                "STORAGE_TYPE": "s3",
                "AWS_S3_BUCKET": "test-bucket",
                "AWS_REGION": "us-east-1",
            },
        ):
            storage = get_storage_service()
            assert isinstance(storage, S3Storage)

    def test_get_storage_service_invalid_type_raises_error(self):
        """Test get_storage_service raises ValueError for invalid type."""
        with patch.dict(os.environ, {"STORAGE_TYPE": "invalid"}):
            with pytest.raises(ValueError, match="Unsupported STORAGE_TYPE"):
                get_storage_service()

    def test_get_storage_service_case_insensitive(self):
        """Test get_storage_service is case-insensitive."""
        with patch.dict(os.environ, {"STORAGE_TYPE": "LOCAL"}):
            storage = get_storage_service()
            assert isinstance(storage, LocalStorage)

        with patch.dict(os.environ, {"STORAGE_TYPE": "S3"}):
            storage = get_storage_service()
            assert isinstance(storage, S3Storage)
