"""Pydantic schemas for file upload."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    """Response model for file upload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    created_at: datetime


class MaterialResponse(BaseModel):
    """Response model for material metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_by: int | None
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    storage_path: str
    meta: dict | None
    created_at: datetime
