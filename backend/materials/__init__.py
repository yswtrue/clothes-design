"""Material management module."""

from materials.schemas import (
    MaterialDetailResponse,
    MaterialListResponse,
    MaterialUpdateRequest,
)
from materials.service import MaterialService

__all__ = [
    "MaterialDetailResponse",
    "MaterialListResponse",
    "MaterialService",
    "MaterialUpdateRequest",
]
