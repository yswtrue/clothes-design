from config import get_settings
from api.storage.base import StorageService
from api.storage.local import LocalStorage
from api.storage.s3 import S3Storage


def get_storage_service() -> StorageService:
    settings = get_settings().storage

    if settings.storage_type == "s3":
        return S3Storage()
    return LocalStorage()
