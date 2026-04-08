from ai.base import AIProvider
from ai.exceptions import UnsupportedProviderError


def get_ai_provider(provider_name: str) -> type[AIProvider]:
    """Factory function to get AI provider class by name.

    Args:
        provider_name: Name of the provider (gpt4v|stability|realesrgan|vectorizer|mockups)

    Returns:
        AIProvider subclass

    Raises:
        UnsupportedProviderError: If provider_name is not recognized
    """
    providers: dict[str, type[AIProvider]] = {}

    if provider_name not in providers:
        raise UnsupportedProviderError(
            f"Provider '{provider_name}' not found. Available: {list(providers.keys())}"
        )

    return providers[provider_name]
