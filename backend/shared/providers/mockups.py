"""Dynamic Mockups provider implementation for garment preview compositing."""

import logging
import os

import aiohttp
from shared.ai.base import AIProvider
from shared.ai.schemas import GenerationParams, Position, StyleAnalysis

logger = logging.getLogger(__name__)


class MockupsProviderError(Exception):
    """Base error for Mockups provider."""

    pass


class ProviderConfigurationError(MockupsProviderError):
    """Provider configuration error."""

    pass


class ProviderTimeoutError(MockupsProviderError):
    """Provider timeout error."""

    pass


class ProviderRateLimitError(MockupsProviderError):
    """Provider rate limit error."""

    pass


class ProviderInvalidTemplateError(MockupsProviderError):
    """Invalid template or position parameters."""

    pass


class MockupsProvider(AIProvider):
    """Dynamic Mockups provider for compositing patterns onto garment templates."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 60,
    ) -> None:
        """Initialize Dynamic Mockups provider.

        Args:
            api_key: Mockups API key (falls back to env vars)
            base_url: Base API URL (for testing)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("MOCKUPS_API_KEY") or os.getenv("DYNAMIC_MOCKUPS_KEY")
        if not self.api_key:
            raise ProviderConfigurationError(
                "Missing Mockups API key. Set MOCKUPS_API_KEY or DYNAMIC_MOCKUPS_KEY environment variable."
            )

        self.base_url = base_url or "https://api.mockups.example.com"
        self.timeout = timeout

    async def composite_mockup(
        self,
        pattern: bytes,
        template: bytes,
        position: Position,
        template_id: str | None = None,
    ) -> bytes:
        """Composite pattern onto garment template using Dynamic Mockups API.

        Args:
            pattern: Pattern image bytes
            template: Template/mockup image bytes (used if template_id is None)
            position: Position and transformation parameters
            template_id: Optional built-in template ID (if provided, template bytes are ignored)

        Returns:
            Composited mockup as bytes (JPEG or PNG)

        Raises:
            ProviderConfigurationError: Missing API key
            ProviderTimeoutError: Request timeout
            ProviderRateLimitError: Rate limit exceeded
            ProviderInvalidTemplateError: Invalid template or position parameters
            MockupsProviderError: Other API errors
        """
        form = aiohttp.FormData()
        form.add_field("pattern", pattern, content_type="image/png", filename="pattern.png")

        # Use built-in template or uploaded template
        if template_id:
            form.add_field("template_id", template_id)
        else:
            form.add_field("template", template, content_type="image/png", filename="template.png")

        # Position parameters
        form.add_field("x", str(position.x))
        form.add_field("y", str(position.y))
        form.add_field("scale", str(position.scale))
        form.add_field("rotation", str(position.rotation))
        form.add_field("opacity", str(position.opacity))

        url = f"{self.base_url}/v1/composite"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status == 429:
                        raise ProviderRateLimitError("Rate limit exceeded. Please retry later.")

                    if response.status == 422:
                        error_data = await response.text()
                        raise ProviderInvalidTemplateError(
                            f"Invalid template or position parameters: {error_data}"
                        )

                    if response.status == 401:
                        raise ProviderConfigurationError("Invalid API key")

                    response.raise_for_status()
                    return await response.read()

        except TimeoutError as e:
            logger.error(f"Mockups API timeout: {e}")
            raise ProviderTimeoutError(f"Request timed out after {self.timeout} seconds") from e
        except aiohttp.ClientError as e:
            logger.error(f"Mockups API client error: {e}")
            raise MockupsProviderError(f"HTTP client error: {e}") from e

    async def analyze_style(self, image: bytes, prompt_override: str | None = None) -> StyleAnalysis:
        raise NotImplementedError(
            "MockupsProvider does not support style analysis. Use GPT4VProvider."
        )

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        """Generate pattern based on style analysis.

        Note: MockupsProvider doesn't support pattern generation.

        Args:
            style: StyleAnalysis object
            params: GenerationParams object

        Returns:
            Generated pattern as bytes

        Raises:
            NotImplementedError: This provider doesn't support pattern generation
        """
        raise NotImplementedError(
            "MockupsProvider does not support pattern generation. Use StabilityProvider."
        )

    async def upscale_image(self, image: bytes, target_size: int, *, content_type: str = "pattern", sharpen: bool = False) -> bytes:
        """Upscale image to target size.

        Note: MockupsProvider doesn't support upscaling.

        Args:
            image: Image bytes to upscale
            target_size: Target width/height in pixels
            content_type: Content type hint ("line-art" or "pattern")
            sharpen: Whether to apply post-upscale sharpening

        Returns:
            Upscaled image as bytes

        Raises:
            NotImplementedError: This provider doesn't support upscaling
        """
        raise NotImplementedError("MockupsProvider does not support upscaling. Use ESRGANProvider.")


__all__ = [
    "MockupsProvider",
    "MockupsProviderError",
    "ProviderConfigurationError",
    "ProviderInvalidTemplateError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
]
