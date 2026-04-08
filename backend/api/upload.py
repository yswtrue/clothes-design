"""Upload API endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.base import get_session
from db.models import User
from upload.schemas import UploadResponse
from upload.service import UploadService

router = APIRouter(prefix="/api/upload", tags=["upload"])

_file_dep = File(...)
_session_dep = Depends(get_session)
_user_dep = Depends(get_current_user)


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = _file_dep,
    session: AsyncSession = _session_dep,
    user: User = _user_dep,
) -> UploadResponse:
    """Upload a material file."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    try:
        content = await file.read()
        service = UploadService(session)
        result = await service.upload_material(content, file.filename, user)
        await session.commit()
        return result
    except ValueError as e:
        error_msg = str(e)
        if "size exceeds" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=error_msg,
            ) from e
        elif "Unsupported file type" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=error_msg,
            ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            ) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {e!s}",
        ) from e
