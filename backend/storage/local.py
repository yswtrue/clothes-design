"""Local filesystem storage implementation."""

import asyncio
import os
from pathlib import Path

from fastapi.logger import logger
from storage.base import StorageService
from storage.exceptions import (
    StorageDeleteError,
    StorageDownloadError,
    StorageUploadError,
    StorageURLError,
)


class LocalStorage(StorageService):
    """Storage implementation using local filesystem."""

    def __init__(self, upload_dir: str | None = None):
        """Initialize local storage.

        Args:
            upload_dir: Directory to store files. Defaults to ./uploads
        """
        upload_path = upload_dir or os.getenv("LOCAL_UPLOAD_DIR") or "./uploads"
        self.upload_dir = Path(upload_path)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: bytes, key: str) -> str:
        """Upload file to local filesystem.

        Args:
            file: File bytes to upload
            key: Storage key/path for the file

        Returns:
            Local file path

        Raises:
            StorageUploadError: If upload fails
        """
        try:
            file_path = self.upload_dir / key
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Run file write in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, file_path.write_bytes, file)
            return key
        except Exception as e:
            raise StorageUploadError(f"Failed to upload file {key}: {e}") from e

    async def download(self, key: str) -> bytes:
        """Download file from local filesystem.

        Args:
            key: Storage key/path to retrieve

        Returns:
            File bytes

        Raises:
            StorageDownloadError: If download fails
        """
        try:
            file_path = self.upload_dir / key
            if not file_path.exists():
                raise StorageDownloadError(f"File not found: {key}")
            # Run file read in executor to avoid blocking
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, file_path.read_bytes)
            return data
        except StorageDownloadError:
            raise
        except Exception as e:
            raise StorageDownloadError(f"Failed to download file {key}: {e}") from e

    async def delete(self, key: str) -> bool:
        """Delete file from local filesystem.

        Args:
            key: Storage key/path to delete

        Returns:
            True if successful, False otherwise

        Raises:
            StorageDeleteError: If deletion fails
        """
        try:
            file_path = self.upload_dir / key
            if not file_path.exists():
                return False
            # Run file delete in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, file_path.unlink)
            return True
        except Exception as e:
            raise StorageDeleteError(f"Failed to delete file {key}: {e}") from e

    async def get_url(self, key: str, expires: int = 3600) -> str:
        """Get local file path (expires parameter ignored for local storage).

        Args:
            key: Storage key/path
            expires: Unused for local storage

        Returns:
            Local file path

        Raises:
            StorageURLError: If path generation fails
        """
        try:
            file_path = self.upload_dir / key
            if not file_path.exists():
                logger.error(f"File not found: {key}")
            return str(file_path)
        except StorageURLError as e:
            logger.error(f"Storage URL error for {key}: {e}")
        except Exception as e:
            logger.error(f"Failed to get URL for {key}: {e}")
        return str(self.upload_dir / key)
