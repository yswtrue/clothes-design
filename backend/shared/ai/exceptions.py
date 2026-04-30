class AIProviderError(Exception):
    """Base exception for AI provider errors."""

    pass


class ProviderError(AIProviderError):
    """General provider error."""

    pass


class UnsupportedProviderError(AIProviderError):
    """Raised when requested provider is not supported."""

    pass


class ProviderConfigurationError(AIProviderError):
    """Raised when provider configuration is invalid."""

    pass


class ProviderTimeoutError(AIProviderError):
    """Raised when provider operation times out."""

    pass


class ProviderRateLimitError(AIProviderError):
    """Raised when provider rate limit is exceeded."""

    pass
