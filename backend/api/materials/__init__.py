"""Material management module."""

from api.materials.schemas import (
    MaterialDetailResponse,
    MaterialListResponse,
    MaterialUpdateRequest,
)
from api.materials.service import MaterialService

__all__ = [
    "MaterialDetailResponse",
    "MaterialListResponse",
    "MaterialService",
    "MaterialUpdateRequest",
]
