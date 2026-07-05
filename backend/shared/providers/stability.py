"""Stability AI provider implementation."""

import base64
import logging
import os

import aiohttp

from shared.ai.base import AIProvider
from shared.ai.schemas import GenerationParams, Position, StyleAnalysis

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Base provider error."""

    pass


class ProviderConfigurationError(ProviderError):
    """Provider configuration error."""

    pass


class ProviderTimeoutError(ProviderError):
    """Provider timeout error."""

    pass


class ProviderRateLimitError(ProviderError):
    """Provider rate limit error."""

    pass


class ProviderContentPolicyError(ProviderError):
    """Content policy violation error."""

    pass


class StabilityProvider(AIProvider):
    """Stability AI provider for pattern generation."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        """Initialize Stability AI provider.

        Args:
            api_key: Stability AI API key (falls back to env vars)
            base_url: Base API URL (for testing)
        """
        self.api_key = api_key or os.getenv("STABILITY_API_KEY") or os.getenv("STABILITY_KEY")
        if not self.api_key:
            raise ProviderConfigurationError(
                "Missing Stability API key. Set STABILITY_API_KEY or STABILITY_KEY environment variable."
            )

        self.base_url = base_url or "https://api.stability.ai"
        self.engine_id = "stable-diffusion-xl-1024-v1-0"

    async def analyze_style(self, image: bytes, prompt_override: str | None = None) -> StyleAnalysis:
        raise NotImplementedError(
            "StabilityProvider does not support style analysis. Use GPT4VProvider."
        )

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        """Generate pattern based on style analysis and parameters.

        Args:
            style: StyleAnalysis object from analyze_style
            params: GenerationParams with dimensions and configuration

        Returns:
            Generated pattern as bytes (PNG format)

        Raises:
            ProviderConfigurationError: Missing API key
            ProviderTimeoutError: Request timeout
            ProviderRateLimitError: Rate limit exceeded
            ProviderContentPolicyError: Content policy violation
            ProviderError: Other API errors
        """
        # Build prompt from style analysis
        prompt = self._build_prompt(style, params)

        # Map tiling mode to API parameters
        sampler = self._map_tiling_to_sampler(params.tiling)

        # Prepare request payload
        payload = {
            "text_prompts": [{"text": prompt, "weight": 1.0}],
            "cfg_scale": 7,
            "height": params.height,
            "width": params.width,
            "samples": 1,
            "steps": 30,
            "seed": params.seed,
            "sampler": sampler,
        }

        # Add style preset if pattern type indicates it
        if style.pattern_type == "seamless":
            payload["style_preset"] = "tile-texture"

        url = f"{self.base_url}/v1/generation/{self.engine_id}/text-to-image"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status == 429:
                        raise ProviderRateLimitError("Rate limit exceeded. Please retry later.")

                    if response.status == 400:
                        error_data = await response.json()
                        error_message = error_data.get("message", "Bad request")
                        if "content" in error_message.lower() or "policy" in error_message.lower():
                            raise ProviderContentPolicyError(
                                f"Content policy violation: {error_message}"
                            )
                        raise ProviderError(f"Invalid request: {error_message}")

                    response.raise_for_status()
                    data = await response.json()

                    # Extract base64 image from response
                    if not data.get("artifacts"):
                        raise ProviderError("No artifacts in response")

                    image_b64 = data["artifacts"][0].get("base64")
                    if not image_b64:
                        raise ProviderError("No base64 data in artifact")

                    return base64.b64decode(image_b64)

        except TimeoutError as e:
            logger.error(f"Stability AI timeout: {e}")
            raise ProviderTimeoutError("Request timed out after 60 seconds") from e
        except aiohttp.ClientError as e:
            logger.error(f"Stability AI client error: {e}")
            raise ProviderError(f"HTTP client error: {e}") from e

    async def upscale_image(self, image: bytes, target_size: int, *, content_type: str = "pattern", sharpen: bool = False) -> bytes:
        """Upscale image to target size.

        Note: Stability AI upscaling requires different API endpoint.
        This is a placeholder for Task 13.

        Args:
            image: Image bytes to upscale
            target_size: Target width/height in pixels
            content_type: Content type hint ("line-art" or "pattern")
            sharpen: Whether to apply post-upscale sharpening

        Returns:
            Upscaled image as bytes

        Raises:
            NotImplementedError: Not yet implemented
        """
        raise NotImplementedError("Upscaling will be implemented in Task 13")

    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        """Composite pattern onto template mockup.

        Note: Stability AI doesn't provide compositing.
        This should use image processing library.

        Args:
            pattern: Pattern image bytes
            template: Template/mockup image bytes
            position: Position and transformation parameters

        Returns:
            Composited mockup as bytes

        Raises:
            NotImplementedError: This provider doesn't support compositing
        """
        raise NotImplementedError("StabilityProvider does not support compositing")

    def _build_prompt(self, style: StyleAnalysis, params: GenerationParams) -> str:
        if params.prompt_override:
            return params.prompt_override

        prompt_parts = [style.style_description]

        # Add pattern type context
        if style.pattern_type == "seamless":
            prompt_parts.append("seamless repeating pattern")
        elif style.pattern_type == "standalone":
            prompt_parts.append("standalone design element")

        # Add color information if available
        if style.color_palette:
            colors = ", ".join(style.color_palette[:3])  # Limit to top 3 colors
            prompt_parts.append(f"color palette: {colors}")

        # Add quality boosters
        prompt_parts.append("high quality, detailed, professional")

        return ". ".join(prompt_parts)

    def _map_tiling_to_sampler(self, tiling: str) -> str:
        """Map tiling mode to Stability AI sampler.

        Args:
            tiling: Tiling mode (tile|clamp|reflect|wrap)

        Returns:
            Sampler name for API
        """
        # Stability AI doesn't have direct tiling control
        # Use different samplers to influence generation characteristics
        tiling_map = {
            "tile": "K_DPMPP_2M",  # Good for seamless patterns
            "clamp": "K_EULER",  # Standard sampler
            "reflect": "K_EULER_ANCESTRAL",  # Adds variation
            "wrap": "K_DPM_2",  # Alternative sampler
        }
        return tiling_map.get(tiling, "K_DPMPP_2M")


__all__ = [
    "ProviderConfigurationError",
    "ProviderContentPolicyError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "StabilityProvider",
]
