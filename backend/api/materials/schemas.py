"""Pydantic schemas for material management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MaterialListResponse(BaseModel):
    """Response model for material list item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_by: int | None
    original_filename: str
    file_size: int
    mime_type: str
    created_at: datetime
    thumbnail_url: str | None = None


class MaterialDetailResponse(BaseModel):
    """Response model for material detail with full metadata."""

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
    thumbnail_url: str | None = None


class MaterialUpdateRequest(BaseModel):
    """Request model for updating material metadata."""

    name: str | None = Field(None, max_length=255)
    tags: list[str] | None = None
    description: str | None = Field(None, max_length=1000)


class PaginatedMaterialsResponse(BaseModel):
    """Response model for paginated material list."""

    items: list[MaterialListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
