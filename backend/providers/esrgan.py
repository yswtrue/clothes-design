"""Real-ESRGAN provider for image upscaling."""

import io
import os

import aiohttp
from PIL import Image

from ai.base import AIProvider
from ai.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from ai.schemas import GenerationParams, Position, StyleAnalysis


class ESRGANProviderError(Exception):
    """Base exception for ESRGAN provider errors."""

    pass


class ESRGANProvider(AIProvider):
    """Real-ESRGAN provider for super-resolution image upscaling.

    Supports upscaling images from 1024px to 12000+px for professional printing.
    Uses streaming upload/download to handle large files efficiently.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        """Initialize ESRGAN provider.

        Args:
            api_key: API key for Real-ESRGAN service (or from env)
            api_url: Base URL for Real-ESRGAN API (or from env)
            timeout: Request timeout in seconds (default: 120s for large images)
            max_retries: Maximum retry attempts for transient failures
        """
        self.api_key = api_key or os.getenv("ESRGAN_API_KEY") or os.getenv("REALESRGAN_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError(
                "Missing ESRGAN API key: set ESRGAN_API_KEY or REALESRGAN_API_KEY"
            )

        self.api_url = api_url or os.getenv("ESRGAN_API_URL", "https://api.replicate.com/v1")
        self.timeout = timeout
        self.max_retries = max_retries

    async def upscale_image(self, image: bytes, target_size: int) -> bytes:  # noqa: C901
        """Upscale image to target size using Real-ESRGAN.

        Args:
            image: Image bytes to upscale
            target_size: Target width/height in pixels (1024-16384)

        Returns:
            Upscaled image as bytes

        Raises:
            ValueError: If target_size is out of range or image is invalid
            ProviderConfigurationError: If API key is missing
            ProviderTimeoutError: If request times out
            ProviderRateLimitError: If rate limit is exceeded
            ESRGANProviderError: For other API errors
        """
        # Validate target size
        if not 1024 <= target_size <= 16384:
            raise ValueError(f"Target size must be 1024-16384, got {target_size}")

        # Get input image dimensions
        try:
            img = Image.open(io.BytesIO(image))
            input_width, input_height = img.size
            input_size = max(input_width, input_height)
        except Exception as e:
            raise ValueError(f"Invalid image format: {e}") from e

        # Calculate scale factor (round to nearest supported scale: 2x, 4x, 8x)
        raw_scale = target_size / input_size
        if raw_scale <= 2.5:
            scale = 2
        elif raw_scale <= 6.0:
            scale = 4
        else:
            scale = 8

        # Prepare streaming upload
        form = aiohttp.FormData()
        form.add_field("image", image, content_type="image/png", filename="input.png")
        form.add_field("scale", str(scale))

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/upscale",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data=form,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        # Handle rate limiting
                        if response.status == 429:
                            retry_after = int(response.headers.get("Retry-After", 2**attempt))
                            raise ProviderRateLimitError(
                                f"Rate limited (attempt {attempt + 1}/{self.max_retries}). "
                                f"Retry after {retry_after}s"
                            )

                        # Handle authentication errors
                        if response.status == 401:
                            raise ProviderConfigurationError("Invalid API key")

                        # Handle file size errors
                        if response.status == 413:
                            raise ValueError("Image too large for upscaling (>50MB)")

                        # Handle server errors (retry on 5xx)
                        if response.status >= 500:
                            if attempt == self.max_retries - 1:
                                raise ESRGANProviderError(f"Server error: {response.status}")
                            continue

                        response.raise_for_status()

                        # Streaming download to handle large files
                        chunks = []
                        async for chunk in response.content.iter_chunked(8192):
                            chunks.append(chunk)

                        return b"".join(chunks)

            except aiohttp.ServerTimeoutError as e:
                raise ProviderTimeoutError(f"Request timed out after {self.timeout}s") from e

            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise ESRGANProviderError(
                        f"Network error after {self.max_retries} attempts: {e}"
                    ) from e
                continue

        raise ESRGANProviderError(f"Failed after {self.max_retries} attempts")

    async def analyze_style(self, image: bytes) -> StyleAnalysis:
        """Not implemented by ESRGAN provider."""
        raise NotImplementedError("Style analysis not supported by ESRGAN provider")

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        """Not implemented by ESRGAN provider."""
        raise NotImplementedError("Pattern generation not supported by ESRGAN provider")

    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        """Not implemented by ESRGAN provider."""
        raise NotImplementedError("Vectorization not supported by ESRGAN provider")

    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        """Not implemented by ESRGAN provider."""
        raise NotImplementedError("Mockup compositing not supported by ESRGAN provider")
