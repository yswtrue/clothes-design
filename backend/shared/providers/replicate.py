"""Unified Replicate provider for image generation and upscaling."""

from __future__ import annotations

import asyncio
import base64
import binascii
import io
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, BinaryIO, Protocol, runtime_checkable

import aiohttp
import httpx
from PIL import Image
from replicate.client import Client
from replicate.exceptions import ModelError, ReplicateError, ReplicateException

from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.schemas import GenerationParams, Position, StyleAnalysis


class ProviderConfigData(Protocol):
    api_key: str
    base_url: str
    model_name: str
    config: dict[str, Any] | None


@runtime_checkable
class AsyncReadable(Protocol):
    async def aread(self) -> bytes | bytearray: ...


@runtime_checkable
class SyncReadable(Protocol):
    def read(self) -> bytes | bytearray: ...

logger = logging.getLogger(__name__)

SDXL_MODEL = "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc"
FLUX_MODEL = "black-forest-labs/flux-schnell"
ESRGAN_MODEL = (
    "nightmareai/real-esrgan:f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa"
)
SWINIR_MODEL = (
    "jingyunliang/swinir:660d922d33153019e8c263a3bba265de882e7f4f70396546b6c9c8f9d47a021a"
)
UPSCALE_MODEL = SWINIR_MODEL  # better texture preservation; ESRGAN_MODEL for GAN upscale
SDXL_IMG2IMG_MODEL = (
    "stability-ai/sdxl:7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc"
)
REPLICATE_REQUEST_TIMEOUT = 30
IMAGE_DOWNLOAD_TIMEOUT = 300


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

        self.base_url = (
            base_url or os.getenv("REPLICATE_BASE_URL") or "https://api.replicate.com/v1"
        ).strip().rstrip("/")
        self.sdk_base_url = self._sdk_base_url(self.base_url)
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = Client(
            api_token=self.api_token,
            base_url=self.sdk_base_url,
            timeout=httpx.Timeout(
                connect=REPLICATE_REQUEST_TIMEOUT,
                read=float(self.timeout),
                write=float(max(REPLICATE_REQUEST_TIMEOUT, self.timeout)),
                pool=REPLICATE_REQUEST_TIMEOUT,
            ),
        )

        self.generation_model = FLUX_MODEL if generation_model == "flux" else SDXL_MODEL

    @classmethod
    def from_config(cls, config: ProviderConfigData) -> ReplicateProvider:
        generation_model = "flux"
        timeout = 120
        max_retries = 3
        if config.config and "generation_model" in config.config:
            generation_model = str(config.config["generation_model"]).strip()
        elif config.model_name.strip():
            generation_model = config.model_name.strip()

        if config.config and "timeout" in config.config:
            timeout = int(config.config["timeout"])
        if config.config and "max_retries" in config.config:
            max_retries = int(config.config["max_retries"])

        return cls(
            api_token=config.api_key,
            base_url=config.base_url,
            generation_model=generation_model,
            timeout=timeout,
            max_retries=max_retries,
        )

    def _sdk_base_url(self, base_url: str) -> str:
        """Convert legacy `/v1` API base URLs into SDK root URLs.

        The Replicate SDK appends `/v1/...` paths internally. Existing database
        configuration for the old manual HTTP client may already include `/v1`,
        so passing it through unchanged produces invalid `/v1/v1/...` requests.
        """
        if base_url.endswith("/v1"):
            return base_url.removesuffix("/v1")
        return base_url

    async def _run_prediction(
        self,
        model: str,
        input_data: dict[str, Any],
    ) -> Any:
        """Run a Replicate model with the official Python SDK and wait for output."""
        try:
            return await asyncio.wait_for(
                self._client.async_run(
                    model,
                    input=input_data,
                    use_file_output=True,
                ),
                timeout=self.timeout,
            )
        except TimeoutError as e:
            raise ProviderTimeoutError(f"Prediction timed out after {self.timeout}s") from e
        except ModelError as e:
            prediction = e.prediction
            raise ProviderError(
                f"Prediction failed: {prediction.error or 'Unknown Replicate model error'}"
            ) from e
        except ReplicateError as e:
            if e.status == 401:
                raise ProviderConfigurationError("Invalid Replicate API token") from e
            if e.status == 429:
                raise ProviderRateLimitError("Replicate rate limit exceeded") from e
            detail = e.detail or e.title or str(e)
            raise ProviderError(f"Replicate API error: {detail}") from e
        except ReplicateException as e:
            raise ProviderError(f"Replicate SDK error: {e}") from e

    async def _download_image(self, url: str) -> bytes:
        """Download image from URL."""
        download_timeout = max(IMAGE_DOWNLOAD_TIMEOUT, self.timeout)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=download_timeout),
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise ProviderError(f"Image download failed: {error_text}")
                    return await response.read()
            except TimeoutError as e:
                raise ProviderTimeoutError(
                    f"Image download timed out after {download_timeout}s"
                ) from e

    async def _replicate_output_to_bytes(self, output: Any) -> bytes:
        item = await self._first_replicate_output(output)

        if isinstance(item, bytes | bytearray):
            return bytes(item)
        if isinstance(item, str):
            return await self._download_image(item)

        if isinstance(item, AsyncReadable):
            data = await item.aread()
            return self._coerce_output_bytes(data)

        if isinstance(item, SyncReadable):
            data = await asyncio.to_thread(item.read)
            return self._coerce_output_bytes(data)

        raise ProviderError(f"Unexpected Replicate output format: {type(item).__name__}")

    async def _first_replicate_output(self, output: Any) -> Any:
        if isinstance(output, list | tuple):
            if not output:
                raise ProviderError("Replicate returned no output")
            return output[0]

        if hasattr(output, "__aiter__") and not hasattr(output, "aread"):
            async for item in output:
                return item
            raise ProviderError("Replicate returned no output")

        return output

    def _coerce_output_bytes(self, data: Any) -> bytes:
        if isinstance(data, bytes | bytearray):
            return bytes(data)
        raise ProviderError(f"Unexpected Replicate file output type: {type(data).__name__}")

    @contextmanager
    def _image_file_input(self, image: bytes) -> Iterator[BinaryIO]:
        suffix = self._image_file_suffix(image)
        temp = NamedTemporaryFile(suffix=suffix, delete=False)
        temp_path = Path(temp.name)
        try:
            temp.write(image)
            temp.close()
            with temp_path.open("rb") as image_file:
                yield image_file
        finally:
            temp.close()
            temp_path.unlink(missing_ok=True)

    def _image_file_suffix(self, image: bytes) -> str:
        with Image.open(io.BytesIO(image)) as img:
            img_format = (img.format or "PNG").lower()
        if img_format == "jpeg":
            return ".jpg"
        return f".{img_format}"

    def _decode_init_image(self, image_b64: str) -> bytes:
        encoded = image_b64.split(",", maxsplit=1)[-1]
        try:
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ProviderError("Invalid base64 init image for Replicate img2img") from e

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        """Generate pattern using SDXL or Flux on Replicate."""
        if params.init_image_b64:
            return await self._generate_img2img(style, params)

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
                output = await self._run_prediction(self.generation_model, input_data)
                image_bytes = await self._replicate_output_to_bytes(output)

                logger.info(
                    f"Pattern generated: {params.width}x{params.height}, seed={params.seed}"
                )
                return image_bytes

            except (ProviderTimeoutError, ProviderRateLimitError):
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.error(f"Generation attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"Generation failed after {self.max_retries} attempts: {e}"
                    ) from e
                await asyncio.sleep(2**attempt)

        raise ProviderError("Generation failed")

    async def upscale_image(self, image: bytes, target_size: int) -> bytes:
        """Upscale image using SwinIR or Real-ESRGAN on Replicate."""
        if not 1024 <= target_size <= 16384:
            raise ValueError(f"Target size must be 1024-16384, got {target_size}")

        img = Image.open(io.BytesIO(image))
        input_width, input_height = img.size
        input_size = max(input_width, input_height)

        raw_scale = target_size / input_size

        for attempt in range(self.max_retries):
            try:
                with self._image_file_input(image) as image_file:
                    if "swinir" in UPSCALE_MODEL.lower():
                        task_type = (
                            "Real-World Image Super-Resolution-Large"
                            if raw_scale > 2.0
                            else "Real-World Image Super-Resolution-Medium"
                        )
                        output = await self._run_prediction(
                            UPSCALE_MODEL,
                            {"image": image_file, "task_type": task_type},
                        )
                    else:
                        if raw_scale <= 2.5:
                            scale = 2
                        elif raw_scale <= 6.0:
                            scale = 4
                        else:
                            scale = 8
                        output = await self._run_prediction(
                            UPSCALE_MODEL,
                            {"image": image_file, "scale": scale, "face_enhance": False},
                        )

                upscaled_bytes = await self._replicate_output_to_bytes(output)

                # Resize to target if AI output is smaller than target
                upscaled_img = Image.open(io.BytesIO(upscaled_bytes))
                longest = max(upscaled_img.width, upscaled_img.height)
                if longest < target_size:
                    ratio = target_size / longest
                    new_w = int(upscaled_img.width * ratio)
                    new_h = int(upscaled_img.height * ratio)
                    upscaled_img = upscaled_img.resize((new_w, new_h), Image.LANCZOS)
                    buf = io.BytesIO()
                    upscaled_img.save(buf, format="PNG")
                    upscaled_bytes = buf.getvalue()

                logger.info(f"Image upscaled: {input_size}px -> {target_size}px")
                return upscaled_bytes

            except ProviderRateLimitError:
                if attempt == self.max_retries - 1:
                    raise
                wait = 15 * (attempt + 1)  # 15s, 30s, 45s — rate limit window is 60s
                logger.warning(
                    f"Rate limited on upscale attempt {attempt + 1}/{self.max_retries}, "
                    f"waiting {wait}s..."
                )
                await asyncio.sleep(wait)
            except ProviderTimeoutError:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.error(f"Upscale attempt {attempt + 1} failed: {e}", exc_info=True)
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"Upscaling failed after {self.max_retries} attempts: {e}"
                    ) from e
                await asyncio.sleep(2**attempt)

        raise ProviderError("Upscaling failed")

    def _build_prompt(self, style: StyleAnalysis, params: GenerationParams) -> str:
        if params.prompt_override:
            return params.prompt_override

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

    def _build_fabric_prompt(self, style: StyleAnalysis, params: GenerationParams) -> str:
        if params.prompt_override:
            return params.prompt_override

        base_prompt = self._build_prompt(style, params)
        fabric_context = (
            "Based on this fabric photo, create a new fabric pattern design that captures "
            "the essence, texture, and style of the original material. "
            "Generate a clean, production-ready textile pattern."
        )
        return f"{fabric_context} Style requirements: {base_prompt}"

    async def _generate_img2img(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        """Generate pattern using SDXL img2img on Replicate."""
        prompt = self._build_fabric_prompt(style, params)

        if params.init_image_b64 is None:
            raise ProviderError("Missing init image for Replicate img2img")
        init_image = self._decode_init_image(params.init_image_b64)

        input_data = {
            "prompt": prompt,
            "negative_prompt": "blurry, low quality, distorted, watermark, text, unrealistic",
            "prompt_strength": params.strength,
            "num_outputs": 1,
            "scheduler": "K_EULER",
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "seed": params.seed,
        }

        for attempt in range(self.max_retries):
            try:
                with self._image_file_input(init_image) as image_file:
                    output = await self._run_prediction(
                        SDXL_IMG2IMG_MODEL,
                        {**input_data, "image": image_file},
                    )
                image_bytes = await self._replicate_output_to_bytes(output)

                logger.info(
                    f"img2img generated: model={SDXL_IMG2IMG_MODEL}, "
                    f"strength={params.strength}, seed={params.seed}"
                )
                return image_bytes

            except (ProviderTimeoutError, ProviderRateLimitError):
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)
            except Exception as e:
                logger.error(f"img2img attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"img2img failed after {self.max_retries} attempts: {e}"
                    ) from e
                await asyncio.sleep(2**attempt)

        raise ProviderError("img2img generation failed")

    async def analyze_style(
        self, image: bytes, prompt_override: str | None = None
    ) -> StyleAnalysis:
        raise NotImplementedError("Use GPT4VProvider for style analysis")

    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        """Not supported - use VectorizerProvider."""
        raise NotImplementedError("Use VectorizerProvider for vectorization")

    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        """Not supported - use MockupsProvider."""
        raise NotImplementedError("Use MockupsProvider for mockup compositing")


__all__ = ["ReplicateProvider"]
