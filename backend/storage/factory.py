"""Storage factory function."""

import os

from storage.base import StorageService
from storage.local import LocalStorage
from storage.s3 import S3Storage


def get_storage_service() -> StorageService:
    """Get storage service instance based on STORAGE_TYPE environment variable.

    Defaults to LocalStorage if STORAGE_TYPE is not set or is "local".
    Uses S3Storage if STORAGE_TYPE is "s3".

    Returns:
        StorageService instance (LocalStorage or S3Storage)

    Raises:
        ValueError: If STORAGE_TYPE is set to an unsupported value
    """
    storage_type = os.getenv("STORAGE_TYPE", "local").lower()

    if storage_type == "local":
        return LocalStorage()
    elif storage_type == "s3":
        return S3Storage()
    else:
        raise ValueError(f"Unsupported STORAGE_TYPE: {storage_type}. Must be 'local' or 's3'.")
