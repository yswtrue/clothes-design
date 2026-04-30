from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings


DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "replicate": "https://api.replicate.com/v1",
    "vectorizer": "https://api.vectorizer.ai/api/v1",
    "esrgan": "https://api.replicate.com/v1",
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

    settings = get_settings()
    engine = create_async_engine(settings.database.async_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
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
    finally:
        await engine.dispose()


async def get_all_active_configs(provider_type: str) -> list[ProviderConfig]:
    from api.db.models import AIProviderConfig

    settings = get_settings()
    engine = create_async_engine(settings.database.async_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
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
    finally:
        await engine.dispose()
