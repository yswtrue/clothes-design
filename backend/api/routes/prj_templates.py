import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import PrjTemplate, User
from api.rbac import require_permission
from api.storage.factory import get_storage_service

router = APIRouter(prefix="/api/prj-templates", tags=["prj-templates"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]
_admin_dep = Annotated[User, Depends(require_permission("admin:manage"))]


def get_file_path(file_obj) -> str | None:
    if file_obj is None:
        return None
    if hasattr(file_obj, "path"):
        return file_obj.path
    if isinstance(file_obj, str):
        return file_obj
    return None


class PrjTemplateResponse(BaseModel):
    id: int
    name: str
    category: str
    preview_url: str | None = None
    is_builtin: bool

    class Config:
        from_attributes = True


class PrjTemplateDetailResponse(PrjTemplateResponse):
    prj_path: str | None = None
    regions: dict | None = None


@router.get("", response_model=Page[PrjTemplateResponse])
async def list_prj_templates(
    session: _session_dep,
    current_user: _user_dep,
    category: str | None = Query(None),
) -> Page[PrjTemplateResponse]:
    query = select(PrjTemplate)

    if category:
        query = query.where(PrjTemplate.category == category)  # type: ignore[arg-type]

    query = query.order_by(PrjTemplate.name)

    page = await paginate(session, query)

    storage = get_storage_service()
    items_with_urls = []
    for item in page.items:
        preview_url = None
        preview_path = get_file_path(item.preview_image)
        if preview_path:
            preview_url = await storage.get_url(preview_path)
        items_with_urls.append(PrjTemplateResponse(
            id=item.id,
            name=item.name,
            category=item.category,
            preview_url=preview_url,
            is_builtin=bool(item.is_builtin),
        ))

    page.items = items_with_urls
    return page


@router.get("/categories")
async def list_categories(
    session: _session_dep,
    current_user: _user_dep,
) -> list[str]:
    result = await session.execute(
        select(PrjTemplate.category).distinct().order_by(PrjTemplate.category)  # type: ignore[arg-type]
    )
    return [row[0] for row in result.all()]


@router.get("/{template_id}", response_model=PrjTemplateDetailResponse)
async def get_prj_template(
    template_id: int,
    session: _session_dep,
    current_user: _user_dep,
):
    result = await session.execute(
        select(PrjTemplate).where(PrjTemplate.id == template_id)  # type: ignore[arg-type]
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    storage = get_storage_service()
    preview_url = None
    preview_path = get_file_path(template.preview_image)
    if preview_path:
        preview_url = await storage.get_url(preview_path)

    return PrjTemplateDetailResponse(
        id=template.id,  # type: ignore[arg-type]
        name=template.name,
        category=template.category,
        prj_path=get_file_path(template.prj_file),
        preview_url=preview_url,
        regions=template.regions,
        is_builtin=bool(template.is_builtin),
    )


@router.post("", response_model=PrjTemplateDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_prj_template(
    session: _session_dep,
    admin_user: _admin_dep,
    name: str = Form(...),
    category: str = Form(...),
    prj_file: UploadFile = File(...),
    preview_file: UploadFile | None = File(None),
    regions: str | None = Form(None),
):
    import json
    regions_dict = None
    if regions:
        try:
            regions_dict = json.loads(regions)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in regions field",
            )

    template = PrjTemplate(
        name=name,
        category=category,
        prj_file=prj_file,
        preview_image=preview_file,
        regions=regions_dict,
        is_builtin=1,
    )

    session.add(template)
    await session.commit()
    await session.refresh(template)

    storage = get_storage_service()
    preview_url = None
    preview_path = get_file_path(template.preview_image)
    if preview_path:
        preview_url = await storage.get_url(preview_path)

    return PrjTemplateDetailResponse(
        id=template.id,  # type: ignore[arg-type]
        name=template.name,
        category=template.category,
        prj_path=get_file_path(template.prj_file),
        preview_url=preview_url,
        regions=template.regions,
        is_builtin=bool(template.is_builtin),
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prj_template(
    template_id: int,
    session: _session_dep,
    admin_user: _admin_dep,
):
    result = await session.execute(
        select(PrjTemplate).where(PrjTemplate.id == template_id)  # type: ignore[arg-type]
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    template.soft_delete()
    await session.commit()
