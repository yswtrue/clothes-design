"""Upload API endpoints."""

import base64
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import Material, User
from api.materials.schemas import MaterialDetailResponse
from api.storage.factory import get_storage_service
from shared.task_queue.celery_integration import enqueue_task

router = APIRouter(prefix="/api/upload", tags=["upload"])


_file_dep = File(...)
_session_dep = Depends(get_session)
_user_dep = Depends(get_current_user)


def generate_storage_key(user_id: int, filename: str) -> tuple[str, str]:
    """Generate unique storage key for uploaded file."""
    file_id = str(uuid.uuid4())
    stored_filename = f"{file_id}_{filename}"
    storage_key = f"uploads/{user_id}/{stored_filename}"
    return stored_filename, storage_key


@router.post("", response_model=MaterialDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = _file_dep,
    session: AsyncSession = _session_dep,
    user: User = _user_dep,
) -> MaterialDetailResponse:
    """Upload a material file and create database record."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    try:
        content = await file.read()
        user_id: int = user.id  # type: ignore[assignment]
        stored_filename, storage_key = generate_storage_key(user_id, file.filename)

        storage = get_storage_service()
        await storage.upload(content, storage_key)

        # Create Material database record
        material = Material(
            uploaded_by=user_id,
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_size=len(content),
            mime_type=file.content_type or "application/octet-stream",
            storage_path=storage_key,
            meta={},
        )

        session.add(material)
        await session.commit()
        await session.refresh(material)

        try:
            import logging

            logger = logging.getLogger(__name__)

            image_base64 = base64.b64encode(content).decode("utf-8")
            material_id: int = material.id  # type: ignore[assignment]

            logger.info(f"Enqueueing analyze task for material_id={material_id}")

            task_id = await enqueue_task(
                task_type="analyze",
                user_id=user_id,
                data={
                    "material_id": material_id,
                    "image_data": image_base64,
                },
            )

            logger.info(f"Analyze task enqueued successfully: task_id={task_id}")

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to enqueue analyze task: {e}", exc_info=True)

        return MaterialDetailResponse.model_validate(material)

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {e!s}",
        ) from e
