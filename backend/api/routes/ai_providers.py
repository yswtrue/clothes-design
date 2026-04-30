from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.dependencies import get_current_user
from api.db.base import get_session
from api.db.models import AIProviderConfig, User
from api.rbac import require_permission

router = APIRouter(prefix="/api/ai-providers", tags=["ai-providers"])

_session_dep = Annotated[AsyncSession, Depends(get_session)]
_user_dep = Annotated[User, Depends(get_current_user)]
_admin_dep = Annotated[User, Depends(require_permission("admin:manage"))]


class ProviderConfigCreate(BaseModel):
    provider_type: str
    name: str
    base_url: str
    api_key: str
    model_name: str
    is_active: bool = True
    priority: int = 0
    rate_limit: int | None = None
    config: dict | None = None


class ProviderConfigUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    rate_limit: int | None = None
    config: dict | None = None


class ProviderConfigResponse(BaseModel):
    id: int
    provider_type: str
    name: str
    base_url: str
    model_name: str
    is_active: bool
    priority: int
    rate_limit: int | None

    class Config:
        from_attributes = True


class ProviderConfigDetailResponse(ProviderConfigResponse):
    api_key_masked: str
    config: dict | None = None


@router.get("", response_model=Page[ProviderConfigResponse])
async def list_provider_configs(
    session: _session_dep,
    current_user: _admin_dep,
    provider_type: str | None = None,
) -> Page[ProviderConfigResponse]:
    query = select(AIProviderConfig)

    if provider_type:
        query = query.where(AIProviderConfig.provider_type == provider_type)

    query = query.order_by(AIProviderConfig.provider_type, AIProviderConfig.priority)

    return await paginate(session, query)


@router.get("/types")
async def list_provider_types(
    session: _session_dep,
    current_user: _admin_dep,
) -> list[str]:
    result = await session.execute(
        select(AIProviderConfig.provider_type).distinct().order_by(AIProviderConfig.provider_type)
    )
    return [row[0] for row in result.all()]


@router.get("/{config_id}", response_model=ProviderConfigDetailResponse)
async def get_provider_config(
    config_id: int,
    session: _session_dep,
    current_user: _admin_dep,
) -> ProviderConfigDetailResponse:
    result = await session.execute(
        select(AIProviderConfig).where(AIProviderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found")

    return ProviderConfigDetailResponse(
        id=config.id,
        provider_type=config.provider_type,
        name=config.name,
        base_url=config.base_url,
        model_name=config.model_name,
        is_active=bool(config.is_active),
        priority=config.priority,
        rate_limit=config.rate_limit,
        api_key_masked=config.api_key[:8] + "****" + config.api_key[-4:] if len(config.api_key) > 12 else "****",
        config=config.config,
    )


@router.post("", response_model=ProviderConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_config(
    data: ProviderConfigCreate,
    session: _session_dep,
    current_user: _admin_dep,
) -> ProviderConfigResponse:
    config = AIProviderConfig(
        provider_type=data.provider_type,
        name=data.name,
        base_url=data.base_url,
        api_key=data.api_key,
        model_name=data.model_name,
        is_active=1 if data.is_active else 0,
        priority=data.priority,
        rate_limit=data.rate_limit,
        config=data.config,
    )

    session.add(config)
    await session.commit()
    await session.refresh(config)

    return ProviderConfigResponse(
        id=config.id,
        provider_type=config.provider_type,
        name=config.name,
        base_url=config.base_url,
        model_name=config.model_name,
        is_active=bool(config.is_active),
        priority=config.priority,
        rate_limit=config.rate_limit,
    )


@router.patch("/{config_id}", response_model=ProviderConfigResponse)
async def update_provider_config(
    config_id: int,
    data: ProviderConfigUpdate,
    session: _session_dep,
    current_user: _admin_dep,
) -> ProviderConfigResponse:
    result = await session.execute(
        select(AIProviderConfig).where(AIProviderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found")

    update_data = data.model_dump(exclude_unset=True)
    if "is_active" in update_data:
        update_data["is_active"] = 1 if update_data["is_active"] else 0

    for key, value in update_data.items():
        setattr(config, key, value)

    await session.commit()
    await session.refresh(config)

    return ProviderConfigResponse(
        id=config.id,
        provider_type=config.provider_type,
        name=config.name,
        base_url=config.base_url,
        model_name=config.model_name,
        is_active=bool(config.is_active),
        priority=config.priority,
        rate_limit=config.rate_limit,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_config(
    config_id: int,
    session: _session_dep,
    current_user: _admin_dep,
) -> None:
    result = await session.execute(
        select(AIProviderConfig).where(AIProviderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found")

    config.soft_delete()
    await session.commit()


@router.post("/{config_id}/test")
async def test_provider_config(
    config_id: int,
    session: _session_dep,
    current_user: _admin_dep,
) -> dict:
    result = await session.execute(
        select(AIProviderConfig).where(AIProviderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found")

    import aiohttp

    try:
        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(
                f"{config.base_url}/models",
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    return {"status": "ok", "message": "连接成功"}
                elif response.status == 401:
                    return {"status": "error", "message": "API Key 无效"}
                else:
                    return {"status": "error", "message": f"HTTP {response.status}"}
    except aiohttp.ClientError as e:
        return {"status": "error", "message": f"连接失败: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
