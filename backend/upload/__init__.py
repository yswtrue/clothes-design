"""File upload module for materials."""

from upload.schemas import MaterialResponse, UploadResponse
from upload.service import UploadService

__all__ = ["MaterialResponse", "UploadResponse", "UploadService"]
