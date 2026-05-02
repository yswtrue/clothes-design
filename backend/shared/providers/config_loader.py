from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

from shared.db import get_session_context

if TYPE_CHECKING:
    from shared.ai.factory import Capability


DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openai_image_edit": "https://api.openai.com/v1",
    "replicate": "https://api.replicate.com/v1",
    "vectorizer_ai": "https://api.vectorizer.ai/api/v1",
}


@dataclass
class ProviderConfig:
    api_key: str
    base_url: str
    model_name: str
    config: dict | None = None


def _get_base_url(provider_type: str, base_url: str | None) -> str:
    if base_url:
        return base_url
    return DEFAULT_BASE_URLS.get(provider_type, "")


async def get_provider_config(provider_type: str) -> ProviderConfig | None:
    from api.db.models import AIProviderConfig

    async with get_session_context() as session:
        stmt = (
            select(AIProviderConfig)
            .where(AIProviderConfig.provider_type == provider_type)  # type: ignore[arg-type]
            .where(AIProviderConfig.is_active == 1)  # type: ignore[arg-type]
            .order_by(AIProviderConfig.priority)  # type: ignore[arg-type]
            .limit(1)
        )
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()

        if config is None:
            return None

        return ProviderConfig(
            api_key=config.api_key,
            base_url=_get_base_url(provider_type, config.base_url),
            model_name=config.model_name,
            config=config.config,
        )


async def get_all_active_configs(provider_type: str) -> list[ProviderConfig]:
    from api.db.models import AIProviderConfig

    async with get_session_context() as session:
        stmt = (
            select(AIProviderConfig)
            .where(AIProviderConfig.provider_type == provider_type)  # type: ignore[arg-type]
            .where(AIProviderConfig.is_active == 1)  # type: ignore[arg-type]
            .order_by(AIProviderConfig.priority)  # type: ignore[arg-type]
        )
        result = await session.execute(stmt)
        configs = result.scalars().all()

        return [
            ProviderConfig(
                api_key=c.api_key,
                base_url=_get_base_url(provider_type, c.base_url),
                model_name=c.model_name,
                config=c.config,
            )
            for c in configs
        ]


async def get_provider_configs_by_capability(
    capability: "Capability",
) -> list[tuple[ProviderConfig, str]]:
    from api.db.models import AIProviderConfig
    from shared.ai.factory import CAPABILITY_PROVIDER_TYPES

    provider_types = CAPABILITY_PROVIDER_TYPES.get(capability, [])
    if not provider_types:
        return []

    async with get_session_context() as session:
        stmt = (
            select(AIProviderConfig)
            .where(AIProviderConfig.provider_type.in_(provider_types))  # type: ignore[union-attr]
            .where(AIProviderConfig.is_active == 1)  # type: ignore[arg-type]
            .order_by(AIProviderConfig.priority)  # type: ignore[arg-type]
        )
        result = await session.execute(stmt)
        configs = result.scalars().all()

        return [
            (
                ProviderConfig(
                    api_key=c.api_key,
                    base_url=_get_base_url(c.provider_type, c.base_url),
                    model_name=c.model_name,
                    config=c.config,
                ),
                c.provider_type,
            )
            for c in configs
        ]
