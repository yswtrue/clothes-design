from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import PromptTemplate, User
from api.rbac import require_permission

router = APIRouter(prefix="/api/prompt-templates", tags=["prompt-templates"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]
_admin_dep = Annotated[User, Depends(require_permission("admin:manage"))]


class PromptTemplateCreate(BaseModel):
    name: str
    task_type: str
    provider_type: str | None = None
    template: str
    description: str | None = None
    is_default: bool = False
    is_active: bool = True


class PromptTemplateUpdate(BaseModel):
    name: str | None = None
    task_type: str | None = None
    provider_type: str | None = None
    template: str | None = None
    description: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class PromptTemplateResponse(BaseModel):
    id: int
    name: str
    task_type: str
    provider_type: str | None
    template: str
    description: str | None
    is_default: bool
    is_active: bool

    class Config:
        from_attributes = True


class PromptTemplatePreview(BaseModel):
    style_description: str = "watercolor floral pattern with soft edges"
    color_palette: list[str] = ["#FF6B6B", "#4ECDC4", "#45B7D1"]
    pattern_type: str = "seamless"
    width: int = 1024
    height: int = 1024


@router.get("", response_model=Page[PromptTemplateResponse])
async def list_prompt_templates(
    session: _session_dep,
    current_user: _admin_dep,
    task_type: str | None = None,
    provider_type: str | None = None,
) -> Page[PromptTemplateResponse]:
    query = select(PromptTemplate)

    if task_type:
        query = query.where(PromptTemplate.task_type == task_type)
    if provider_type:
        query = query.where(PromptTemplate.provider_type == provider_type)

    query = query.order_by(PromptTemplate.task_type, PromptTemplate.is_default.desc())

    return await paginate(session, query)


@router.get("/task-types")
async def list_task_types(
    session: _session_dep,
    current_user: _admin_dep,
) -> list[str]:
    result = await session.execute(
        select(PromptTemplate.task_type).distinct().order_by(PromptTemplate.task_type)
    )
    return [row[0] for row in result.all()]


@router.get("/default/{task_type}", response_model=PromptTemplateResponse | None)
async def get_default_template(
    task_type: str,
    session: _session_dep,
    current_user: _user_dep,
    provider_type: str | None = None,
) -> PromptTemplateResponse | None:
    conditions = [
        PromptTemplate.task_type == task_type,
        PromptTemplate.is_default == 1,
        PromptTemplate.is_active == 1,
    ]
    if provider_type:
        conditions.append(
            (PromptTemplate.provider_type == provider_type) | (PromptTemplate.provider_type == None)
        )

    result = await session.execute(
        select(PromptTemplate)
        .where(and_(*conditions))
        .order_by(PromptTemplate.provider_type.desc())
        .limit(1)
    )
    template = result.scalar_one_or_none()

    if not template:
        return None

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        task_type=template.task_type,
        provider_type=template.provider_type,
        template=template.template,
        description=template.description,
        is_default=bool(template.is_default),
        is_active=bool(template.is_active),
    )


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    template_id: int,
    session: _session_dep,
    current_user: _admin_dep,
) -> PromptTemplateResponse:
    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        task_type=template.task_type,
        provider_type=template.provider_type,
        template=template.template,
        description=template.description,
        is_default=bool(template.is_default),
        is_active=bool(template.is_active),
    )


@router.post("", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    data: PromptTemplateCreate,
    session: _session_dep,
    current_user: _admin_dep,
) -> PromptTemplateResponse:
    if data.is_default:
        await _clear_default_for_task(session, data.task_type, data.provider_type)

    template = PromptTemplate(
        name=data.name,
        task_type=data.task_type,
        provider_type=data.provider_type,
        template=data.template,
        description=data.description,
        is_default=1 if data.is_default else 0,
        is_active=1 if data.is_active else 0,
    )

    session.add(template)
    await session.commit()
    await session.refresh(template)

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        task_type=template.task_type,
        provider_type=template.provider_type,
        template=template.template,
        description=template.description,
        is_default=bool(template.is_default),
        is_active=bool(template.is_active),
    )


@router.patch("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: int,
    data: PromptTemplateUpdate,
    session: _session_dep,
    current_user: _admin_dep,
) -> PromptTemplateResponse:
    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    update_data = data.model_dump(exclude_unset=True)

    if update_data.get("is_default"):
        task_type = update_data.get("task_type", template.task_type)
        provider_type = update_data.get("provider_type", template.provider_type)
        await _clear_default_for_task(session, task_type, provider_type, exclude_id=template_id)

    if "is_default" in update_data:
        update_data["is_default"] = 1 if update_data["is_default"] else 0
    if "is_active" in update_data:
        update_data["is_active"] = 1 if update_data["is_active"] else 0

    for key, value in update_data.items():
        setattr(template, key, value)

    await session.commit()
    await session.refresh(template)

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        task_type=template.task_type,
        provider_type=template.provider_type,
        template=template.template,
        description=template.description,
        is_default=bool(template.is_default),
        is_active=bool(template.is_active),
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_template(
    template_id: int,
    session: _session_dep,
    current_user: _admin_dep,
) -> None:
    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    template.soft_delete()
    await session.commit()


@router.post("/{template_id}/preview")
async def preview_prompt_template(
    template_id: int,
    preview_data: PromptTemplatePreview,
    session: _session_dep,
    current_user: _admin_dep,
) -> dict:
    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    rendered = template.template.format(
        style_description=preview_data.style_description,
        color_palette=", ".join(preview_data.color_palette),
        pattern_type=preview_data.pattern_type,
        width=preview_data.width,
        height=preview_data.height,
    )

    return {"rendered": rendered}


@router.post("/{template_id}/set-default", response_model=PromptTemplateResponse)
async def set_default_template(
    template_id: int,
    session: _session_dep,
    current_user: _admin_dep,
) -> PromptTemplateResponse:
    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    await _clear_default_for_task(session, template.task_type, template.provider_type, exclude_id=template_id)
    template.is_default = 1
    await session.commit()
    await session.refresh(template)

    return PromptTemplateResponse(
        id=template.id,
        name=template.name,
        task_type=template.task_type,
        provider_type=template.provider_type,
        template=template.template,
        description=template.description,
        is_default=bool(template.is_default),
        is_active=bool(template.is_active),
    )


async def _clear_default_for_task(
    session: AsyncSession,
    task_type: str,
    provider_type: str | None,
    exclude_id: int | None = None,
) -> None:
    conditions = [
        PromptTemplate.task_type == task_type,
        PromptTemplate.is_default == 1,
    ]
    if provider_type:
        conditions.append(PromptTemplate.provider_type == provider_type)
    else:
        conditions.append(PromptTemplate.provider_type == None)
    if exclude_id:
        conditions.append(PromptTemplate.id != exclude_id)

    result = await session.execute(
        select(PromptTemplate).where(and_(*conditions))
    )
    for t in result.scalars().all():
        t.is_default = 0
