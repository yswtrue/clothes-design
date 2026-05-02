"""Design management API endpoints."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.ai.schemas import Position
from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import Design, DesignVersion, PrjTemplate, User
from api.rbac.permissions import require_permission
from shared.providers.mockups import (
    MockupsProvider,
    MockupsProviderError,
    ProviderConfigurationError,
    ProviderInvalidTemplateError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from api.storage.storages import generated_image_storage, preview_storage

router = APIRouter(prefix="/api/designs", tags=["designs"])


def _ensure_full_url(pattern_url: str | None) -> str | None:
    """Convert storage filename to URL path if needed (for backward compatibility with old data)."""
    if not pattern_url:
        return None
    if pattern_url.startswith(("http://", "https://", "/")):
        return pattern_url
    return generated_image_storage.get_url(pattern_url)


def _convert_version_data_urls(data: dict | None) -> dict | None:
    if not data:
        return None
    result = {**data}
    if "pattern_url" in result:
        result["pattern_url"] = _ensure_full_url(result["pattern_url"])
    if "vector_url" in result:
        result["vector_url"] = _ensure_full_url(result["vector_url"])
    return result


_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


class ColorAdjustment(BaseModel):
    """Color adjustment parameters for preview."""

    hue: float = Field(default=0, ge=-180, le=180, description="Hue shift in degrees")
    saturation: float = Field(default=0, ge=-100, le=100, description="Saturation adjustment")
    brightness: float = Field(default=0, ge=-100, le=100, description="Brightness adjustment")


class DesignPreviewState(BaseModel):
    """Design preview state (stored in DesignVersion.data)."""

    pattern_url: str | None = None
    template_id: int | None = None
    position: Position = Field(default_factory=lambda: Position(x=0, y=0, scale=1.0, rotation=0))
    colors: ColorAdjustment = Field(default_factory=ColorAdjustment)


class DesignResponse(BaseModel):
    """Design response with preview state."""

    id: int
    user_id: int | None
    name: str
    status: str
    created_at: str
    updated_at: str
    preview_state: DesignPreviewState | None = None


class CreateDesignRequest(BaseModel):
    """Request to create a new design."""

    name: str = Field(min_length=1, max_length=255)


class UpdateDesignRequest(BaseModel):
    """Request to update design preview state."""

    template_id: int | None = None
    position: Position | None = None
    colors: ColorAdjustment | None = None


class PreviewResponse(BaseModel):
    """Response from preview generation."""

    preview_url: str


class DesignListItem(BaseModel):
    """Design list item response."""

    id: int
    user_id: int | None
    name: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DesignVersionResponse(BaseModel):
    """Design version response."""

    id: int
    design_id: int
    version: int
    data: dict | None
    created_at: datetime


class VersionsListResponse(BaseModel):
    """List of versions response."""

    versions: list[DesignVersionResponse]


class RollbackRequest(BaseModel):
    """Request to rollback to specific version."""

    version: int = Field(ge=1)


class RollbackResponse(BaseModel):
    """Response from rollback operation."""

    id: int
    version: int
    message: str


@router.get("/{design_id}", response_model=DesignResponse)
async def get_design(
    design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    """Get design by ID with preview state.

    Args:
        design_id: Design ID to fetch
        session: Database session
        current_user: Authenticated user

    Returns:
        Design with preview state from latest version

    Raises:
        HTTPException: If design not found or access denied
    """
    result = await session.execute(
        select(Design).where(Design.id == design_id, Design.user_id == current_user.id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or access denied",
        )

    version_result = await session.execute(
        select(DesignVersion)
        .where(DesignVersion.design_id == design_id)
        .order_by(DesignVersion.version.desc())
        .limit(1)
    )
    latest_version = version_result.scalar_one_or_none()

    preview_state = None
    if latest_version and latest_version.data:
        try:
            preview_state = DesignPreviewState(**latest_version.data)
            if preview_state.pattern_url:
                preview_state.pattern_url = _ensure_full_url(preview_state.pattern_url)
        except Exception:
            preview_state = None

    return DesignResponse(
        id=design.id,
        user_id=design.user_id,
        name=design.name,
        status=design.status,
        created_at=design.created_at.isoformat(),
        updated_at=design.updated_at.isoformat(),
        preview_state=preview_state,
    )


@router.patch("/{design_id}", response_model=DesignResponse)
async def update_design(
    design_id: int,
    request: UpdateDesignRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    """Update design preview state.

    Args:
        design_id: Design ID to update
        request: Update parameters
        session: Database session
        current_user: Authenticated user

    Returns:
        Updated design with new preview state

    Raises:
        HTTPException: If design not found or access denied
    """
    result = await session.execute(
        select(Design).where(Design.id == design_id, Design.user_id == current_user.id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or access denied",
        )

    version_result = await session.execute(
        select(DesignVersion)
        .where(DesignVersion.design_id == design_id)
        .order_by(DesignVersion.version.desc())
        .limit(1)
    )
    latest_version = version_result.scalar_one_or_none()

    current_state = DesignPreviewState()
    if latest_version and latest_version.data:
        try:
            current_state = DesignPreviewState(**latest_version.data)
        except Exception:
            pass

    if request.template_id is not None:
        current_state.template_id = request.template_id

    if request.position is not None:
        current_state.position = request.position

    if request.colors is not None:
        current_state.colors = request.colors

    next_version = 1
    if latest_version:
        next_version = latest_version.version + 1

    new_version = DesignVersion(
        design_id=design_id,
        version=next_version,
        data=current_state.model_dump(mode="json"),
    )
    session.add(new_version)
    await session.commit()
    await session.refresh(design)

    if current_state.pattern_url:
        current_state.pattern_url = _ensure_full_url(current_state.pattern_url)

    return DesignResponse(
        id=design.id,
        user_id=design.user_id,
        name=design.name,
        status=design.status,
        created_at=design.created_at.isoformat(),
        updated_at=design.updated_at.isoformat(),
        preview_state=current_state,
    )


@router.get("/{design_id}/preview", response_model=PreviewResponse)
async def generate_preview(
    design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    """Generate mockup preview for current design state.

    Args:
        design_id: Design ID to generate preview for
        session: Database session
        current_user: Authenticated user

    Returns:
        Preview URL from Dynamic Mockups API

    Raises:
        HTTPException: If design not found, missing required state, or API error
    """
    result = await session.execute(
        select(Design).where(Design.id == design_id, Design.user_id == current_user.id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or access denied",
        )

    version_result = await session.execute(
        select(DesignVersion)
        .where(DesignVersion.design_id == design_id)
        .order_by(DesignVersion.version.desc())
        .limit(1)
    )
    latest_version = version_result.scalar_one_or_none()

    if not latest_version or not latest_version.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Design has no preview state",
        )

    try:
        preview_state = DesignPreviewState(**latest_version.data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preview state: {e}",
        )

    if not preview_state.pattern_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Design has no pattern URL",
        )

    if not preview_state.template_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No template selected",
        )

    template_result = await session.execute(
        select(PrjTemplate).where(PrjTemplate.id == preview_state.template_id)  # type: ignore[arg-type]
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {preview_state.template_id} not found",
        )

    if not template.preview_image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template has no preview image for mockup",
        )

    try:
        pattern_bytes = await generated_image_storage.download(preview_state.pattern_url)
        template_bytes = await preview_storage.download(str(template.preview_image))

        mockups_provider = MockupsProvider()

        composite_result = await mockups_provider.composite_mockup(
            pattern=pattern_bytes,
            template=template_bytes,
            position=preview_state.position,
            template_id=None,
        )

        preview_filename = f"{uuid.uuid4()}.png"
        preview_url = await generated_image_storage.upload(composite_result, preview_filename)

        return PreviewResponse(preview_url=preview_url)

    except ProviderConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mockups provider configuration error: {e}",
        )
    except ProviderTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Mockups API timeout: {e}",
        )
    except ProviderRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Mockups API rate limit: {e}",
        )
    except ProviderInvalidTemplateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template or position: {e}",
        )
    except MockupsProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mockups API error: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate preview: {e}",
        )


@router.post("", response_model=DesignResponse, status_code=status.HTTP_201_CREATED)
async def create_design(
    request: CreateDesignRequest,
    session: _session_dep,
    current_user: Annotated[User, Depends(require_permission("designs.create"))],
):
    """Create a new design.

    Args:
        request: Create design request with name
        session: Database session
        current_user: Authenticated user

    Returns:
        Created design with initial empty preview state

    Raises:
        HTTPException: If design creation fails
    """
    design = Design(
        user_id=current_user.id,
        name=request.name,
        status="draft",
    )
    session.add(design)
    await session.flush()

    initial_version = DesignVersion(
        design_id=design.id,
        version=1,
        data={},
    )
    session.add(initial_version)
    await session.commit()
    await session.refresh(design)

    return DesignResponse(
        id=design.id,
        user_id=design.user_id,
        name=design.name,
        status=design.status,
        created_at=design.created_at.isoformat(),
        updated_at=design.updated_at.isoformat(),
        preview_state=None,
    )


@router.get("", response_model=Page[DesignListItem])
async def list_designs(
    session: _session_dep,
    current_user: _user_dep,
) -> Page[DesignListItem]:
    """List all user's designs with pagination.

    Args:
        session: Database session
        current_user: Authenticated user

    Returns:
        Paginated list of designs

    Query params (auto-injected by fastapi-pagination):
        page: Page number (default: 1)
        size: Items per page (default: 50, max: 100)
    """
    return await paginate(
        session,
        select(Design).where(Design.user_id == current_user.id).order_by(Design.updated_at.desc()),
    )


@router.get("/{design_id}/versions", response_model=VersionsListResponse)
async def list_versions(
    design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    """List all versions for a design.

    Args:
        design_id: Design ID to fetch versions for
        session: Database session
        current_user: Authenticated user

    Returns:
        List of all design versions

    Raises:
        HTTPException: If design not found or access denied
    """
    result = await session.execute(
        select(Design).where(Design.id == design_id, Design.user_id == current_user.id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or access denied",
        )

    version_result = await session.execute(
        select(DesignVersion)
        .where(DesignVersion.design_id == design_id)
        .order_by(DesignVersion.version.desc())
    )
    versions = version_result.scalars().all()

    return VersionsListResponse(
        versions=[
            DesignVersionResponse(
                id=v.id,
                design_id=v.design_id,
                version=v.version,
                data=_convert_version_data_urls(v.data),
                created_at=v.created_at,
            )
            for v in versions
        ]
    )


@router.post("/{design_id}/rollback", response_model=RollbackResponse)
async def rollback_version(
    design_id: int,
    request: RollbackRequest,
    session: _session_dep,
    current_user: _user_dep,
):
    """Rollback design to specific version.

    Creates a new version with the data from the target version.

    Args:
        design_id: Design ID to rollback
        request: Rollback request with target version
        session: Database session
        current_user: Authenticated user

    Returns:
        New version created from rollback

    Raises:
        HTTPException: If design not found, access denied, or version not found
    """
    result = await session.execute(
        select(Design).where(Design.id == design_id, Design.user_id == current_user.id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or access denied",
        )

    target_result = await session.execute(
        select(DesignVersion).where(
            DesignVersion.design_id == design_id, DesignVersion.version == request.version
        )
    )
    target_version = target_result.scalar_one_or_none()

    if not target_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {request.version} not found",
        )

    max_version_result = await session.execute(
        select(func.max(DesignVersion.version)).where(DesignVersion.design_id == design_id)
    )
    max_version = max_version_result.scalar_one() or 0

    new_version = DesignVersion(
        design_id=design_id,
        version=max_version + 1,
        data=target_version.data,
    )
    session.add(new_version)
    await session.commit()
    await session.refresh(new_version)

    return RollbackResponse(
        id=new_version.id,
        version=new_version.version,
        message=f"Rolled back to version {request.version} (created new version {new_version.version})",
    )


@router.delete("/{design_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_design(
    design_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    """Delete design and all its versions.

    Args:
        design_id: Design ID to delete
        session: Database session
        current_user: Authenticated user

    Raises:
        HTTPException: If design not found or access denied
    """
    result = await session.execute(
        select(Design).where(Design.id == design_id, Design.user_id == current_user.id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design not found or access denied",
        )

    await session.execute(delete(Design).where(Design.id == design_id))
    await session.commit()
