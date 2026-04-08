"""Storage service abstract base class."""

from abc import ABC, abstractmethod


class StorageService(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    async def upload(self, file: bytes, key: str) -> str:
        """Upload file to storage.

        Args:
            file: File bytes to upload
            key: Storage key/path for the file

        Returns:
            URL or path to the uploaded file
        """
        pass

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download file from storage.

        Args:
            key: Storage key/path to retrieve

        Returns:
            File bytes
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete file from storage.

        Args:
            key: Storage key/path to delete

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_url(self, key: str, expires: int = 3600) -> str:
        """Get URL for file (signed for S3, local path for filesystem).

        Args:
            key: Storage key/path
            expires: URL expiration time in seconds (used for S3 signed URLs)

        Returns:
            URL or local file path
        """
        pass
