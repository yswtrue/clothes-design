"""Topaz Labs Gigapixel provider for professional image upscaling.

Uses the Topaz Image API with async submit/poll/download pattern.
Authentication via X-API-KEY header.
"""

import asyncio
import io
import logging
import os
from typing import Any

import aiohttp

from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.schemas import GenerationParams, Position, StyleAnalysis
from shared.providers.config_loader import ProviderConfig

logger = logging.getLogger(__name__)

TOPAZ_API_BASE = "https://api.topazlabs.com/image/v1"
TOPAZ_DEFAULT_MODEL = "Standard V2"  # best for fabric/print
TOPAZ_POLL_INTERVAL = 3  # seconds
TOPAZ_MAX_WAIT = 300  # seconds


class TopazProvider(AIProvider):
    """Topaz Labs Gigapixel provider.

    Supports professional upscaling with models like Standard V2 (print),
    High Fidelity 2 (photo), and others. No GPU limits — handles any image size.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 300,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("TOPAZ_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError(
                "Missing Topaz API key: set TOPAZ_API_KEY env var"
            )
        self.model = model or TOPAZ_DEFAULT_MODEL
        self.timeout = timeout
        self.max_retries = max_retries

    @classmethod
    def from_config(cls, config: ProviderConfig) -> "TopazProvider":
        return cls(
            api_key=config.api_key,
            model=config.config.get("model") if config.config else None,
        )

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Make an authenticated request to the Topaz API."""
        headers = {"X-API-KEY": self.api_key}
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        timeout = kwargs.pop("timeout", aiohttp.ClientTimeout(total=60))

        url = f"{TOPAZ_API_BASE}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
                **kwargs,
            ) as response:
                if response.status == 429:
                    raise ProviderRateLimitError("Topaz API rate limited")
                if response.status == 401:
                    raise ProviderConfigurationError("Invalid Topaz API key")
                if response.status >= 500:
                    raise ProviderError(f"Topaz server error: {response.status}")
                response.raise_for_status()
                return await response.json()

    async def _submit_enhance(self, image_bytes: bytes, output_width: int) -> str:
        """Submit an async enhance job. Returns process_id."""
        form = aiohttp.FormData()
        form.add_field("model", self.model)
        form.add_field("output_format", "png")
        form.add_field("output_width", str(output_width))
        form.add_field("image", image_bytes, content_type="image/png", filename="input.png")

        for attempt in range(self.max_retries):
            try:
                data = await self._request(
                    "POST",
                    "/enhance/async",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=120),
                )
                process_id = data.get("process_id")
                if not process_id:
                    raise ProviderError(f"No process_id in response: {data}")
                logger.info(f"Topaz enhance submitted: process_id={process_id}")
                return process_id
            except (ProviderRateLimitError, ProviderTimeoutError) as e:
                if attempt == self.max_retries - 1:
                    raise
                wait = 5 * (attempt + 1)
                logger.warning(f"Topaz submit retry {attempt + 1}/{self.max_retries} in {wait}s: {e}")
                await asyncio.sleep(wait)

        raise ProviderError("Failed to submit Topaz enhance job")

    async def _poll_status(self, process_id: str) -> dict[str, Any]:
        """Poll until job completes. Returns final status JSON."""
        start = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > TOPAZ_MAX_WAIT:
                raise ProviderTimeoutError(
                    f"Topaz enhance timed out after {TOPAZ_MAX_WAIT}s (process_id={process_id})"
                )

            data = await self._request("GET", f"/status/{process_id}")
            status = data.get("status", "Unknown")
            logger.debug(f"Topaz status: {status} (process_id={process_id})")

            if status == "Completed":
                return data
            elif status in ("Failed", "Cancelled"):
                error = data.get("error", "Unknown error")
                raise ProviderError(
                    f"Topaz enhance {status}: {error} (process_id={process_id})"
                )

            await asyncio.sleep(TOPAZ_POLL_INTERVAL)

    async def _download_result(self, process_id: str) -> bytes:
        """Download the enhanced image."""
        data = await self._request("GET", f"/download/{process_id}")
        download_url = data.get("url")
        if not download_url:
            raise ProviderError(f"No download URL in response: {data}")

        logger.info(f"Downloading Topaz result: {download_url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                download_url,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                response.raise_for_status()
                return await response.read()

    async def upscale_image(self, image: bytes, target_size: int) -> bytes:
        """Upscale image to target_size using Topaz Gigapixel.

        Args:
            image: Source image bytes
            target_size: Target width/height in pixels

        Returns:
            Upscaled image as PNG bytes
        """
        if not 256 <= target_size <= 32768:
            raise ValueError(f"Target size must be 256-32768, got {target_size}")

        logger.info(f"Topaz upscale: target={target_size}px, model={self.model}")

        process_id = await self._submit_enhance(image, target_size)
        await self._poll_status(process_id)
        result = await self._download_result(process_id)

        logger.info(f"Topaz upscale complete: {len(image)} → {len(result)} bytes")
        return result

    # Stub methods — Topaz is upscale-only
    async def analyze_style(self, image: bytes, prompt_override: str | None = None) -> StyleAnalysis:
        raise NotImplementedError("Style analysis not supported by Topaz provider")

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        raise NotImplementedError("Pattern generation not supported by Topaz provider")

    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        raise NotImplementedError("Vectorization not supported by Topaz provider")

    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        raise NotImplementedError("Mockup compositing not supported by Topaz provider")


__all__ = ["TopazProvider"]
