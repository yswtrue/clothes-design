"""Vectorizer.ai provider for raster-to-vector conversion with CMYK TIF output."""

import os

import aiohttp

from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.schemas import GenerationParams, Position, StyleAnalysis
from shared.providers.config_loader import ProviderConfig


class VectorizerError(Exception):
    """Vectorizer-specific errors."""

    pass


class VectorizerProvider(AIProvider):
    """Vectorizer.ai provider for professional CMYK TIF vectorization."""

    api_id: str
    api_secret: str
    timeout: int
    base_url: str

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 90,
    ) -> None:
        # Vectorizer.ai uses HTTP Basic Auth with API_ID:API_SECRET
        api_id = api_key or os.getenv("VECTORIZER_API_ID")
        api_secret = os.getenv("VECTORIZER_API_SECRET")

        if not api_id or not api_secret:
            raise ProviderConfigurationError(
                "Missing Vectorizer credentials: set VECTORIZER_API_ID and VECTORIZER_API_SECRET in .env"
            )

        self.api_id = api_id
        self.api_secret = api_secret
        self.timeout = timeout
        self.base_url = (
            base_url or os.getenv("VECTORIZER_BASE_URL") or "https://api.vectorizer.ai/api/v1"
        )

    @classmethod
    def from_config(cls, config: ProviderConfig) -> "VectorizerProvider":
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        """Convert raster image to SVG format using Vectorizer.ai.

        Note: Vectorizer.ai does not support color space selection. The color_space
        parameter is accepted for interface compatibility but ignored.

        Args:
            image: Raster image bytes (PNG, JPEG, etc.)
            color_space: Ignored - kept for AIProvider interface compatibility

        Returns:
            Vectorized image as SVG bytes
        """
        form = aiohttp.FormData()
        form.add_field("image", image, content_type="image/png", filename="input.png")
        form.add_field("output.file_format", "svg")

        try:
            auth = aiohttp.BasicAuth(self.api_id, self.api_secret)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/vectorize",
                    auth=auth,
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    # Handle specific errors
                    if response.status == 401:
                        raise ProviderConfigurationError("Invalid Vectorizer API key")

                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        raise ProviderRateLimitError(
                            f"Rate limit exceeded. Retry after {retry_after}s"
                        )

                    if response.status == 415:
                        raise ValueError("Unsupported image format")

                    if response.status == 413:
                        raise ValueError("Image file too large")

                    response.raise_for_status()

                    # Stream download for large TIF files
                    chunks = []
                    async for chunk in response.content.iter_chunked(8192):
                        chunks.append(chunk)

                    return b"".join(chunks)

        except aiohttp.ServerTimeoutError as e:
            raise ProviderTimeoutError(f"Vectorization timed out after {self.timeout}s") from e

        except aiohttp.ClientError as e:
            raise VectorizerError(f"Network error during vectorization: {e}") from e

    # Unimplemented AIProvider methods
    async def analyze_style(self, image: bytes) -> StyleAnalysis:
        """Not implemented by Vectorizer provider."""
        raise NotImplementedError("Style analysis not supported by Vectorizer.ai")

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        """Not implemented by Vectorizer provider."""
        raise NotImplementedError("Pattern generation not supported by Vectorizer.ai")

    async def upscale_image(self, image: bytes, target_size: int) -> bytes:
        """Not implemented by Vectorizer provider."""
        raise NotImplementedError("Image upscaling not supported by Vectorizer.ai")

    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        """Not implemented by Vectorizer provider."""
        raise NotImplementedError("Mockup compositing not supported by Vectorizer.ai")
