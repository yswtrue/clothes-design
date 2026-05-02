from enum import Enum
from typing import Any, Protocol

from shared.ai.base import AIProvider
from shared.ai.exceptions import UnsupportedProviderError
from shared.providers.config_loader import ProviderConfig


class ProviderWithConfig(Protocol):
    @classmethod
    def from_config(cls, config: ProviderConfig) -> AIProvider: ...


class Capability(str, Enum):
    ANALYSIS = "analysis"
    IMAGE_GENERATION = "image_generation"
    UPSCALE = "upscale"
    VECTORIZE = "vectorize"


CAPABILITY_PROVIDER_TYPES: dict[Capability, list[str]] = {
    Capability.ANALYSIS: ["openai"],
    Capability.IMAGE_GENERATION: ["openai_image_edit"],
    Capability.UPSCALE: ["replicate"],
    Capability.VECTORIZE: ["vectorizer_ai"],
}


def _get_provider_class(provider_type: str) -> type[Any]:
    from shared.providers.gpt4v import GPT4VProvider
    from shared.providers.openai_image import OpenAIImageProvider
    from shared.providers.replicate import ReplicateProvider
    from shared.providers.vectorizer import VectorizerProvider

    providers: dict[str, type[Any]] = {
        "openai": GPT4VProvider,
        "openai_image_edit": OpenAIImageProvider,
        "replicate": ReplicateProvider,
        "vectorizer_ai": VectorizerProvider,
    }

    if provider_type not in providers:
        raise UnsupportedProviderError(
            f"Provider '{provider_type}' not found. Available: {list(providers.keys())}"
        )

    return providers[provider_type]


def get_ai_provider(provider_name: str) -> type[Any]:
    return _get_provider_class(provider_name)


async def get_provider_by_capability(capability: Capability) -> tuple[AIProvider, str] | None:
    from shared.providers.config_loader import get_provider_configs_by_capability

    configs = await get_provider_configs_by_capability(capability)

    if not configs:
        return None

    for config, provider_type in configs:
        try:
            provider_class = _get_provider_class(provider_type)
            provider = provider_class.from_config(config)
            return provider, provider_type
        except Exception:
            continue

    return None


async def get_provider_for_analysis() -> tuple[AIProvider, str] | None:
    return await get_provider_by_capability(Capability.ANALYSIS)


async def get_provider_for_image_generation() -> tuple[AIProvider, str] | None:
    return await get_provider_by_capability(Capability.IMAGE_GENERATION)


async def get_provider_for_upscale() -> tuple[AIProvider, str] | None:
    return await get_provider_by_capability(Capability.UPSCALE)


async def get_provider_for_vectorize() -> tuple[AIProvider, str] | None:
    return await get_provider_by_capability(Capability.VECTORIZE)
