from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import PromptFeature, User
from api.rbac import require_permission

router = APIRouter(prefix="/api/prompt-features", tags=["prompt-features"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]
_admin_dep = Annotated[User, Depends(require_permission("admin:manage"))]


def _condition(value: object) -> ColumnElement[bool]:
    return cast(ColumnElement[bool], value)


def _order_by(value: object) -> ColumnElement[object]:
    return cast(ColumnElement[object], value)


class PromptFeatureCreate(BaseModel):
    key: str
    label: str
    description: str | None = None
    prompt: str
    sort_order: int = 0
    is_default: bool = False
    is_active: bool = True


class PromptFeatureUpdate(BaseModel):
    key: str | None = None
    label: str | None = None
    description: str | None = None
    prompt: str | None = None
    sort_order: int | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class PromptFeatureResponse(BaseModel):
    id: int
    key: str
    label: str
    description: str | None
    prompt: str
    sort_order: int
    is_default: bool
    is_active: bool

    class Config:
        from_attributes = True


def _to_response(feature: PromptFeature) -> PromptFeatureResponse:
    if feature.id is None:
        raise ValueError("Prompt feature has no id")

    return PromptFeatureResponse(
        id=feature.id,
        key=feature.key,
        label=feature.label,
        description=feature.description,
        prompt=feature.prompt,
        sort_order=feature.sort_order,
        is_default=bool(feature.is_default),
        is_active=bool(feature.is_active),
    )


@router.get("", response_model=Page[PromptFeatureResponse])
async def list_prompt_features(
    session: _session_dep,
    current_user: _user_dep,
    active_only: bool = True,
) -> Page[PromptFeatureResponse]:
    query = select(PromptFeature)
    if active_only:
        query = query.where(_condition(PromptFeature.is_active == 1))

    query = query.order_by(_order_by(PromptFeature.sort_order), _order_by(PromptFeature.id))
    return await paginate(session, query)


@router.get("/{feature_id}", response_model=PromptFeatureResponse)
async def get_prompt_feature(
    feature_id: int,
    session: _session_dep,
    current_user: _admin_dep,
) -> PromptFeatureResponse:
    result = await session.execute(
        select(PromptFeature).where(_condition(PromptFeature.id == feature_id))
    )
    feature = result.scalar_one_or_none()

    if not feature:
        raise HTTPException(status_code=404, detail="Prompt feature not found")

    return _to_response(feature)


@router.post("", response_model=PromptFeatureResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_feature(
    data: PromptFeatureCreate,
    session: _session_dep,
    current_user: _admin_dep,
) -> PromptFeatureResponse:
    feature = PromptFeature(
        key=data.key,
        label=data.label,
        description=data.description,
        prompt=data.prompt,
        sort_order=data.sort_order,
        is_default=1 if data.is_default else 0,
        is_active=1 if data.is_active else 0,
    )

    session.add(feature)
    await session.commit()
    await session.refresh(feature)

    return _to_response(feature)


@router.patch("/{feature_id}", response_model=PromptFeatureResponse)
async def update_prompt_feature(
    feature_id: int,
    data: PromptFeatureUpdate,
    session: _session_dep,
    current_user: _admin_dep,
) -> PromptFeatureResponse:
    result = await session.execute(
        select(PromptFeature).where(_condition(PromptFeature.id == feature_id))
    )
    feature = result.scalar_one_or_none()

    if not feature:
        raise HTTPException(status_code=404, detail="Prompt feature not found")

    update_data = data.model_dump(exclude_unset=True)
    if "is_default" in update_data:
        update_data["is_default"] = 1 if update_data["is_default"] else 0
    if "is_active" in update_data:
        update_data["is_active"] = 1 if update_data["is_active"] else 0

    for key, value in update_data.items():
        setattr(feature, key, value)

    await session.commit()
    await session.refresh(feature)

    return _to_response(feature)


@router.delete("/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_feature(
    feature_id: int,
    session: _session_dep,
    current_user: _admin_dep,
) -> None:
    result = await session.execute(
        select(PromptFeature).where(_condition(PromptFeature.id == feature_id))
    )
    feature = result.scalar_one_or_none()

    if not feature:
        raise HTTPException(status_code=404, detail="Prompt feature not found")

    feature.soft_delete()
    await session.commit()
