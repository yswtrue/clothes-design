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


class VectorizerError(Exception):
    """Vectorizer-specific errors."""

    pass


class VectorizerProvider(AIProvider):
    """Vectorizer.ai provider for professional CMYK TIF vectorization."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 90,
    ) -> None:
        """Initialize Vectorizer provider.

        Args:
            api_key: API key (from env if not provided)
            timeout: Request timeout in seconds (default 90s for slow vectorization)
        """
        self.api_key = api_key or os.getenv("VECTORIZER_API_KEY") or os.getenv("VECTORIZER_KEY")
        if not self.api_key:
            raise ProviderConfigurationError(
                "Missing Vectorizer API key: set VECTORIZER_API_KEY or VECTORIZER_KEY"
            )

        self.timeout = timeout
        self.base_url = "https://api.vectorizer.ai/api/v1"

    async def vectorize(self, image: bytes, color_space: str = "CMYK") -> bytes:
        """Convert raster image to CMYK TIF format using Vectorizer.ai.

        Args:
            image: Raster image bytes (PNG, JPEG, etc.)
            color_space: Color space for output ("CMYK" or "RGB", default "CMYK")

        Returns:
            Vectorized image as TIF bytes

        Raises:
            ValueError: Invalid color_space or unsupported image format
            ProviderConfigurationError: Missing API key
            ProviderTimeoutError: Request timeout
            ProviderRateLimitError: Rate limit exceeded
            VectorizerError: API errors
        """
        # Validate color space
        if color_space not in ("CMYK", "RGB"):
            raise ValueError(f"Color space must be 'CMYK' or 'RGB', got '{color_space}'")

        # Prepare multipart form data
        form = aiohttp.FormData()
        form.add_field("image", image, content_type="image/png", filename="input.png")
        form.add_field("output.format", "tif")
        form.add_field("output.colors", color_space.lower())

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/vectorize",
                    headers={"Authorization": f"Token {self.api_key}"},
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
