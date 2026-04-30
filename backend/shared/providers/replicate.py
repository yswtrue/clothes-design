"""Unified Replicate provider for image generation and upscaling."""

import asyncio
import base64
import io
import logging
import os
from typing import Any

import aiohttp
from PIL import Image

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

SDXL_MODEL = "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc"
FLUX_MODEL = "black-forest-labs/flux-schnell"
ESRGAN_MODEL = "nightmareai/real-esrgan:f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa"


class ReplicateProvider(AIProvider):
    """Unified Replicate provider for image generation and upscaling.
    
    Supports:
    - Image generation via SDXL or Flux models
    - Image upscaling via Real-ESRGAN
    """

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        generation_model: str = "flux",
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        self.api_token = api_token or os.getenv("REPLICATE_API_TOKEN")
        if not self.api_token:
            raise ProviderConfigurationError(
                "Missing Replicate API token. Set REPLICATE_API_TOKEN environment variable."
            )

        self.base_url = base_url or os.getenv("REPLICATE_BASE_URL") or "https://api.replicate.com/v1"
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.generation_model = FLUX_MODEL if generation_model == "flux" else SDXL_MODEL

    @classmethod
    def from_config(cls, config: ProviderConfig) -> "ReplicateProvider":
        generation_model = "flux"
        if config.config and "generation_model" in config.config:
            generation_model = config.config["generation_model"]
        elif config.model_name:
            generation_model = config.model_name
            
        return cls(
            api_token=config.api_key,
            base_url=config.base_url,
            generation_model=generation_model,
        )

    async def _run_prediction(
        self,
        model: str,
        input_data: dict[str, Any],
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        """Run a prediction on Replicate and wait for result."""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/predictions",
                headers=headers,
                json={"version": model.split(":")[-1] if ":" in model else model, "input": input_data},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 401:
                    raise ProviderConfigurationError("Invalid Replicate API token")
                if response.status == 429:
                    raise ProviderRateLimitError("Replicate rate limit exceeded")
                if response.status >= 400:
                    error_text = await response.text()
                    raise ProviderError(f"Replicate API error: {error_text}")
                
                prediction = await response.json()

            prediction_id = prediction["id"]
            get_url = f"{self.base_url}/predictions/{prediction_id}"
            
            elapsed = 0.0
            while elapsed < self.timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                async with session.get(
                    get_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    result = await response.json()
                    status = result.get("status")
                    
                    if status == "succeeded":
                        return result
                    elif status == "failed":
                        error = result.get("error", "Unknown error")
                        raise ProviderError(f"Prediction failed: {error}")
                    elif status == "canceled":
                        raise ProviderError("Prediction was canceled")

            raise ProviderTimeoutError(f"Prediction timed out after {self.timeout}s")

    async def _download_image(self, url: str) -> bytes:
        """Download image from URL."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                return await response.read()

    async def _upload_image_data_uri(self, image: bytes) -> str:
        """Convert image bytes to data URI for Replicate input."""
        img = Image.open(io.BytesIO(image))
        img_format = img.format or "PNG"
        b64 = base64.b64encode(image).decode("utf-8")
        mime = f"image/{img_format.lower()}"
        return f"data:{mime};base64,{b64}"

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        """Generate pattern using SDXL or Flux on Replicate."""
        prompt = self._build_prompt(style, params)
        
        if "flux" in self.generation_model.lower():
            input_data = {
                "prompt": prompt,
                "num_outputs": 1,
                "aspect_ratio": "1:1",
                "output_format": "png",
                "output_quality": 90,
            }
        else:
            input_data = {
                "prompt": prompt,
                "negative_prompt": "blurry, low quality, distorted, watermark, text",
                "width": min(params.width, 1024),
                "height": min(params.height, 1024),
                "num_outputs": 1,
                "scheduler": "K_EULER",
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "seed": params.seed,
            }

        for attempt in range(self.max_retries):
            try:
                result = await self._run_prediction(self.generation_model, input_data)
                output = result.get("output")
                
                if isinstance(output, list) and output:
                    image_url = output[0]
                elif isinstance(output, str):
                    image_url = output
                else:
                    raise ProviderError(f"Unexpected output format: {output}")
                
                image_bytes = await self._download_image(image_url)
                
                logger.info(
                    f"Pattern generated: {params.width}x{params.height}, seed={params.seed}"
                )
                return image_bytes
                
            except (ProviderTimeoutError, ProviderRateLimitError):
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Generation attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise ProviderError(f"Generation failed after {self.max_retries} attempts: {e}")
                await asyncio.sleep(2 ** attempt)

        raise ProviderError("Generation failed")

    async def upscale_image(self, image: bytes, target_size: int) -> bytes:
        """Upscale image using Real-ESRGAN on Replicate."""
        if not 1024 <= target_size <= 16384:
            raise ValueError(f"Target size must be 1024-16384, got {target_size}")

        img = Image.open(io.BytesIO(image))
        input_width, input_height = img.size
        input_size = max(input_width, input_height)

        raw_scale = target_size / input_size
        if raw_scale <= 2.5:
            scale = 2
        elif raw_scale <= 6.0:
            scale = 4
        else:
            scale = 4
            
        image_uri = await self._upload_image_data_uri(image)
        
        input_data = {
            "image": image_uri,
            "scale": scale,
            "face_enhance": False,
        }

        for attempt in range(self.max_retries):
            try:
                result = await self._run_prediction(ESRGAN_MODEL, input_data)
                output = result.get("output")
                
                if isinstance(output, str):
                    image_url = output
                else:
                    raise ProviderError(f"Unexpected output format: {output}")
                
                upscaled_bytes = await self._download_image(image_url)
                
                logger.info(f"Image upscaled: {input_size}px -> {target_size}px (scale={scale})")
                return upscaled_bytes
                
            except (ProviderTimeoutError, ProviderRateLimitError):
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Upscale attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise ProviderError(f"Upscaling failed after {self.max_retries} attempts: {e}")
                await asyncio.sleep(2 ** attempt)

        raise ProviderError("Upscaling failed")

    def _build_prompt(self, style: StyleAnalysis, params: GenerationParams) -> str:
        """Build text prompt from style analysis."""
        prompt_parts = [style.style_description]

        if style.pattern_type == "seamless":
            prompt_parts.append("seamless repeating pattern, tileable texture")
        elif style.pattern_type == "standalone":
            prompt_parts.append("standalone design element, centered composition")

        if style.color_palette:
            colors = ", ".join(style.color_palette[:3])
            prompt_parts.append(f"color palette: {colors}")

        prompt_parts.append("high quality, detailed, professional textile design")

        return ". ".join(prompt_parts)

    async def analyze_style(self, image: bytes) -> StyleAnalysis:
        """Not supported - use GPT4VProvider for style analysis."""
        raise NotImplementedError("Use GPT4VProvider for style analysis")

    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        """Not supported - use VectorizerProvider."""
        raise NotImplementedError("Use VectorizerProvider for vectorization")

    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        """Not supported - use MockupsProvider."""
        raise NotImplementedError("Use MockupsProvider for mockup compositing")


__all__ = ["ReplicateProvider"]
