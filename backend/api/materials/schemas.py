"""Pydantic schemas for material management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from shared.ai.schemas import StyleAnalysis


class MaterialMeta(BaseModel):
    """Material metadata structure stored in JSON field."""

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "name": "Floral Pattern Base",
                "tags": ["floral", "spring", "pastel"],
                "description": "Watercolor floral pattern for summer collection",
                "thumbnail_path": "thumbnails/abc123.jpg",
                "style_analysis": {
                    "style_description": "Soft watercolor florals with pink and lavender tones",
                    "color_palette": ["#FFB6C1", "#E6E6FA"],
                    "pattern_type": "seamless",
                    "suggested_params": {},
                },
            }
        },
    )

    name: str | None = Field(None, max_length=255, description="User-defined material name")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    description: str | None = Field(None, max_length=1000, description="Material description")

    thumbnail_path: str | None = Field(None, description="Relative path to thumbnail image")

    style_analysis: StyleAnalysis | None = Field(None, description="AI-generated style analysis")


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
    meta: MaterialMeta | None
    created_at: datetime
    thumbnail_url: str | None = None


class MaterialUpdateRequest(BaseModel):
    """Request model for updating material metadata."""

    name: str | None = Field(None, max_length=255)
    tags: list[str] | None = None
    description: str | None = Field(None, max_length=1000)
