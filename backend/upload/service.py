"""Upload service business logic."""

import uuid
from datetime import datetime
from pathlib import Path

import filetype
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Material, User
from storage.factory import get_storage_service
from storage.thumbnail import ThumbnailGenerator
from upload.schemas import UploadResponse

MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}


class UploadService:
    """Service for handling file uploads."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.storage = get_storage_service()

    async def upload_material(
        self,
        file_content: bytes,
        original_filename: str,
        user: User,
    ) -> UploadResponse:
        """Upload a material file and create database record."""
        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds {MAX_FILE_SIZE} bytes")

        kind = filetype.guess(file_content)
        if not kind or kind.mime not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported file type. Allowed: {ALLOWED_MIME_TYPES}")

        file_extension = Path(original_filename).suffix or f".{kind.extension}"
        stored_filename = f"{uuid.uuid4()}{file_extension}"

        storage_path = await self.storage.upload(file_content, stored_filename)

        thumbnail_bytes, thumbnail_filename = await ThumbnailGenerator.generate(
            file_content, stored_filename
        )
        thumbnail_path = await self.storage.upload(
            thumbnail_bytes, f"thumbnails/{thumbnail_filename}"
        )

        meta = {
            "thumbnail_path": thumbnail_path,
        }

        material = Material(
            uploaded_by=int(user.id) if user.id else None,  # type: ignore[assignment]
            original_filename=original_filename,
            stored_filename=stored_filename,  # type: ignore[assignment]
            file_size=len(file_content),  # type: ignore[assignment]
            mime_type=kind.mime,  # type: ignore[assignment]
            storage_path=storage_path,  # type: ignore[assignment]
            meta=meta,  # type: ignore[assignment]
        )
        self.session.add(material)
        await self.session.flush()

        url = await self.storage.get_url(stored_filename)

        return UploadResponse(
            id=int(material.id) if material.id else 0,
            url=url,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_size=len(file_content),
            mime_type=kind.mime,
            created_at=material.created_at if material.created_at else datetime.now(),  # type: ignore[arg-type]
        )
