from shared.ai.base import AIProvider
from shared.ai.exceptions import UnsupportedProviderError


def get_ai_provider(provider_name: str) -> type[AIProvider]:
    """Factory function to get AI provider class by name.

    Args:
        provider_name: Name of the provider (gpt4v|replicate|realesrgan|vectorizer|mockups)

    Returns:
        AIProvider subclass

    Raises:
        UnsupportedProviderError: If provider_name is not recognized
    """
    from shared.providers.esrgan import ESRGANProvider
    from shared.providers.gpt4v import GPT4VProvider
    from shared.providers.mockups import MockupsProvider
    from shared.providers.replicate import ReplicateProvider
    from shared.providers.vectorizer import VectorizerProvider

    providers: dict[str, type[AIProvider]] = {
        "gpt4v": GPT4VProvider,
        "replicate": ReplicateProvider,
        "realesrgan": ESRGANProvider,
        "esrgan": ESRGANProvider,
        "vectorizer": VectorizerProvider,
        "mockups": MockupsProvider,
    }

    if provider_name not in providers:
        raise UnsupportedProviderError(
            f"Provider '{provider_name}' not found. Available: {list(providers.keys())}"
        )

    return providers[provider_name]
