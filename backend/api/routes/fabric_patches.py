"""Fabric patch segmentation API endpoints."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import User
from api.services.fabric_segmentation import segment_fabric_patches
from api.storage.storages import fabric_patch_storage

router = APIRouter(prefix="/api/fabric-patches", tags=["fabric-patches"])

_file_dep = File(...)
_session_dep = Depends(get_session)
_user_dep = Depends(get_current_user)

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


class FabricPatchResponse(BaseModel):
    """Response model for a single segmented fabric patch."""

    index: int
    url: str
    width: int
    height: int


class SegmentResponse(BaseModel):
    """Response model for the segment endpoint."""

    total_patches: int
    patches: list[FabricPatchResponse]


@router.post("/segment", response_model=SegmentResponse)
async def segment_fabric_patches_endpoint(
    file: UploadFile = _file_dep,
    session: AsyncSession = _session_dep,
    user: User = _user_dep,
) -> SegmentResponse:
    """Upload an image and segment it into individual fabric patches.

    The image is processed using thresholding, morphology, and connected
    component analysis to detect and extract each patch.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: {file.content_type}. Allowed: {', '.join(_ALLOWED_CONTENT_TYPES)}",
        )

    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {exc!s}",
        ) from exc

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    try:
        patches = segment_fabric_patches(content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image segmentation failed: {exc!s}",
        ) from exc

    if not patches:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fabric patches detected in the image",
        )

    response_patches: list[FabricPatchResponse] = []
    try:
        for idx, patch in enumerate(patches):
            filename = f"{uuid.uuid4()}.png"
            url = await fabric_patch_storage.upload(patch["image_bytes"], filename)
            response_patches.append(
                FabricPatchResponse(
                    index=idx,
                    url=url,
                    width=patch["width"],
                    height=patch["height"],
                )
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store segmented patches: {exc!s}",
        ) from exc

    return SegmentResponse(total_patches=len(response_patches), patches=response_patches)
