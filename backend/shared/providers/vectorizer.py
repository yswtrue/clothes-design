"""Vectorizer.ai provider for raster-to-vector conversion with CMYK TIF output."""

import asyncio
import logging

import aiohttp

from config import get_settings
from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
)
from shared.ai.schemas import GenerationParams, Position, StyleAnalysis
from shared.providers.config_loader import ProviderConfig

logger = logging.getLogger(__name__)


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
        timeout: int | None = None,
    ) -> None:
        settings = get_settings().vectorizer

        api_id: str | None = None
        api_secret: str | None = None

        if api_key and ":" in api_key:
            api_id, api_secret = api_key.split(":", 1)
        else:
            api_id = api_key or settings.api_id
            api_secret = settings.api_secret

        if not api_id or not api_secret:
            raise ProviderConfigurationError(
                "Missing Vectorizer credentials. Set api_key as 'api_id:api_secret' in Admin, "
                "or set VECTORIZER_API_ID and VECTORIZER_API_SECRET in .env"
            )

        self.api_id = api_id
        self.api_secret = api_secret
        self.timeout = timeout if timeout is not None else settings.timeout
        self.base_url = base_url or settings.base_url

    @classmethod
    def from_config(cls, config: ProviderConfig) -> "VectorizerProvider":
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def vectorize(
        self,
        image: bytes,
        color_space: str = "rgb",
        *,
        line_fit_tolerance: float = 0.05,
        min_area_px: float = 0.5,
        gap_filler_enabled: bool = True,
        gap_filler_stroke_width: float = 2.0,
        max_retries: int = 3,
    ) -> bytes:
        """Convert raster image to SVG format using Vectorizer.ai.

        Note: Vectorizer.ai does not support color space selection. The color_space
        parameter is accepted for interface compatibility but ignored.

        Args:
            image: Raster image bytes (PNG, JPEG, etc.)
            color_space: Ignored - kept for AIProvider interface compatibility
            line_fit_tolerance: Max distance (px) between curves and approximating lines.
                Lower = smoother curves, less line fragmentation. Default 0.05 (was 0.1).
            min_area_px: Minimum shape area in pixels. Shapes smaller than this are
                discarded. Higher = removes tiny fragments. Default 0.5 (was 0.125).
            gap_filler_enabled: Fill gaps between shapes to prevent white line artifacts.
            gap_filler_stroke_width: Width of gap filler strokes.
            max_retries: Maximum retry attempts for transient network errors.

        Returns:
            Vectorized image as SVG bytes
        """
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                return await self._do_vectorize(
                    image,
                    line_fit_tolerance=line_fit_tolerance,
                    min_area_px=min_area_px,
                    gap_filler_enabled=gap_filler_enabled,
                    gap_filler_stroke_width=gap_filler_stroke_width,
                )
            except (aiohttp.ClientPayloadError, aiohttp.ServerTimeoutError) as e:
                last_error = e
                logger.warning(f"Vectorize attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
            except aiohttp.ClientError as e:
                raise VectorizerError(f"Network error during vectorization: {e}") from e

        raise VectorizerError(
            f"Vectorization failed after {max_retries} attempts: {last_error}"
        ) from last_error

    async def _do_vectorize(
        self,
        image: bytes,
        *,
        line_fit_tolerance: float,
        min_area_px: float,
        gap_filler_enabled: bool,
        gap_filler_stroke_width: float,
    ) -> bytes:
        form = aiohttp.FormData()
        form.add_field("image", image, content_type="image/png", filename="input.png")
        form.add_field("output.file_format", "svg")

        form.add_field("output.curves.line_fit_tolerance", str(line_fit_tolerance))
        form.add_field("processing.shapes.min_area_px", str(min_area_px))
        form.add_field("output.gap_filler.enabled", "true" if gap_filler_enabled else "false")
        form.add_field("output.gap_filler.stroke_width", str(gap_filler_stroke_width))

        form.add_field("output.curves.allowed.quadratic_bezier", "true")
        form.add_field("output.curves.allowed.cubic_bezier", "true")
        form.add_field("output.curves.allowed.circular_arc", "true")
        form.add_field("output.curves.allowed.elliptical_arc", "true")

        auth = aiohttp.BasicAuth(self.api_id, self.api_secret)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/vectorize",
                auth=auth,
                data=form,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                if response.status == 401:
                    raise ProviderConfigurationError("Invalid Vectorizer API key")

                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise ProviderRateLimitError(f"Rate limit exceeded. Retry after {retry_after}s")

                if response.status == 415:
                    raise ValueError("Unsupported image format")

                if response.status == 413:
                    raise ValueError("Image file too large")

                response.raise_for_status()

                chunks = []
                async for chunk in response.content.iter_chunked(8192):
                    chunks.append(chunk)

                return b"".join(chunks)

    # Unimplemented AIProvider methods
    async def analyze_style(
        self, image: bytes, prompt_override: str | None = None
    ) -> StyleAnalysis:
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
