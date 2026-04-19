"""Template management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import Template, User
from api.middleware.cache import cache
from api.rbac.permissions import require_permission
from api.storage.factory import get_storage_service

router = APIRouter(prefix="/api/templates", tags=["templates"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]


class TemplateResponse(BaseModel):
    id: int
    name: str
    image_path: str
    category: str
    is_builtin: int
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[TemplateResponse])
@cache(expire=60)
async def get_templates(session: _session_dep):
    """Get all templates (public endpoint, no auth required)."""
    result = await session.execute(select(Template))
    templates = result.scalars().all()
    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            image_path=t.image_path,
            category=t.category,
            is_builtin=t.is_builtin,
            created_at=t.created_at.isoformat(),
        )
        for t in templates
    ]


@router.post(
    "", response_model=TemplateResponse, dependencies=[Depends(require_permission("admin"))]
)
async def create_template(
    name: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    session: _session_dep = None,
    current_user: _user_dep = None,
):
    """Create new template (admin only).

    Requires admin permission. Validates file type and uploads to storage.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    # Validate category
    valid_categories = ["t-shirt", "hoodie", "tank", "long-sleeve", "polo"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}",
        )

    storage = get_storage_service()

    # Upload image
    image_data = await file.read()
    image_path = await storage.upload(image_data, f"templates/{file.filename}")

    # Create template record
    new_template = Template(
        name=name,
        image_path=image_path,
        category=category,
        is_builtin=0,
    )
    session.add(new_template)
    await session.commit()
    await session.refresh(new_template)

    return TemplateResponse(
        id=new_template.id,
        name=new_template.name,
        image_path=new_template.image_path,
        category=new_template.category,
        is_builtin=new_template.is_builtin,
        created_at=new_template.created_at.isoformat(),
    )


@router.delete("/{template_id}", dependencies=[Depends(require_permission("admin"))])
async def delete_template(
    template_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    """Delete template (admin only).

    Requires admin permission. Cannot delete built-in templates.
    """
    result = await session.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete built-in templates",
        )

    await session.delete(template)
    await session.commit()

    return {"message": "Template deleted successfully"}
