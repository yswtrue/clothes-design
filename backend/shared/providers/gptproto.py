"""GPTProto provider for image generation and editing."""

import asyncio
import base64
import json
import logging
import os
from typing import TYPE_CHECKING, Any

import aiohttp

from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.schemas import GenerationParams, Position, StyleAnalysis

if TYPE_CHECKING:
    from shared.providers.config_loader import ProviderConfig

logger = logging.getLogger(__name__)


POLL_INTERVAL_SECONDS = 2
MAX_POLL_ATTEMPTS = 150
GPT_IMAGE_SIZE_MULTIPLE = 16
GPT_IMAGE_MAX_EDGE = 3840
GPT_IMAGE_MAX_ASPECT_RATIO = 3.0
GPT_IMAGE_MIN_PIXELS = 655_360
GPT_IMAGE_MAX_PIXELS = 8_294_400


class GPTProtoProvider(AIProvider):
    DEFAULT_BASE_URL = "https://gptproto.com/api/v3"
    DEFAULT_MODEL = "google/gemini-3.1-flash-image-preview"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 600,
        max_retries: int = 3,
        sync_mode: bool = True,
    ) -> None:
        self.api_key = api_key or os.getenv("GPTPROTO_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError(
                "Missing GPTProto API key. Set GPTPROTO_API_KEY environment variable."
            )

        self.base_url = (
            base_url or os.getenv("GPTPROTO_BASE_URL") or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = model or os.getenv("GPTPROTO_MODEL") or self.DEFAULT_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        self.sync_mode = sync_mode

    @classmethod
    def from_config(cls, config: "ProviderConfig") -> "GPTProtoProvider":
        extra_config = config.config or {}
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model_name,
            sync_mode=extra_config.get("sync_mode", True),
        )

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

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        if params.init_image_b64:
            return await self._generate_img2img(style, params)
        return await self._generate_text2img(style, params)

    def _is_gpt_image_model(self) -> bool:
        return "gpt-image-2" in self.model.lower()

    async def _generate_text2img(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        if self._is_gpt_image_model():
            return await self._generate_gpt_image_text2img(style, params)

        prompt = self._build_prompt(style, params)
        model_path = self.model.replace("google/", "")
        url = f"{self.base_url}/google/{model_path}/text-to-image"

        payload: dict[str, Any] = {
            "prompt": prompt,
            "size": "1K",
            "aspect_ratio": "1:1",
            "output_format": "png",
            "enable_sync_mode": self.sync_mode,
            "enable_base64_output": True,
        }

        return await self._make_request(url, payload)

    async def _generate_img2img(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        if not params.init_image_b64:
            raise ProviderError("init_image_b64 is required for image editing")

        if self._is_gpt_image_model():
            return await self._generate_gpt_image_img2img(style, params)

        prompt = self._build_prompt(style, params)
        model_path = self.model.replace("google/", "")
        url = f"{self.base_url}/google/{model_path}/image-edit"

        image_input = params.init_image_b64
        if not image_input.startswith("http"):
            image_input = f"data:image/png;base64,{params.init_image_b64}"

        payload: dict[str, Any] = {
            "prompt": prompt,
            "images": [image_input],
            "size": "1K",
            "aspect_ratio": "1:1",
            "output_format": "png",
            "enable_sync_mode": self.sync_mode,
            "enable_base64_output": True,
        }

        return await self._make_request(url, payload)

    async def _generate_gpt_image_text2img(
        self, style: StyleAnalysis, params: GenerationParams
    ) -> bytes:
        prompt = self._build_prompt(style, params)
        url = f"{self._openai_base_url()}/images/generations"
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": self._get_gpt_image_size(params.width, params.height),
            "quality": "high",
            "output_format": "png",
            "response_format": "b64_json",
        }

        return await self._make_request(url, payload, bearer_auth=True)

    async def _generate_gpt_image_img2img(
        self, style: StyleAnalysis, params: GenerationParams
    ) -> bytes:
        if not params.init_image_b64:
            raise ProviderError("init_image_b64 is required for image editing")

        prompt = self._build_prompt(style, params)
        url = f"{self._api_v3_base_url()}/openai/gpt-image-2/image-edit"
        payload: dict[str, Any] = {
            "prompt": prompt,
            "n": 1,
            "size": self._get_gpt_image_size(params.width, params.height),
            "quality": "high",
            "response_format": "b64_json",
            "enable_sync_mode": self.sync_mode,
        }
        image_input = params.init_image_b64
        if image_input.startswith(("http://", "https://")):
            payload["images"] = [image_input]
        else:
            payload["base64_images"] = [self._as_data_uri(image_input)]

        return await self._make_request(url, payload)

    def _openai_base_url(self) -> str:
        if self.base_url.endswith("/api/v3"):
            return self.base_url[: -len("/api/v3")] + "/v1"
        return self.base_url

    def _api_v3_base_url(self) -> str:
        if self.base_url.endswith("/v1"):
            return self.base_url[: -len("/v1")] + "/api/v3"
        return self.base_url

    def _as_data_uri(self, image_input: str) -> str:
        if image_input.startswith(("http://", "https://", "data:")):
            return image_input
        return f"data:image/png;base64,{image_input}"

    def _get_gpt_image_size(self, width: int, height: int) -> str:
        normalized_width = self._normalize_gpt_image_dimension(width)
        normalized_height = self._normalize_gpt_image_dimension(height)

        normalized_width, normalized_height = self._fit_gpt_image_aspect_ratio(
            normalized_width, normalized_height
        )
        normalized_width, normalized_height = self._fit_gpt_image_pixel_count(
            normalized_width, normalized_height
        )
        return f"{normalized_width}x{normalized_height}"

    def _normalize_gpt_image_dimension(self, value: int) -> int:
        clamped = min(max(value, GPT_IMAGE_SIZE_MULTIPLE), GPT_IMAGE_MAX_EDGE)
        rounded = round(clamped / GPT_IMAGE_SIZE_MULTIPLE) * GPT_IMAGE_SIZE_MULTIPLE
        return min(max(rounded, GPT_IMAGE_SIZE_MULTIPLE), GPT_IMAGE_MAX_EDGE)

    def _fit_gpt_image_aspect_ratio(self, width: int, height: int) -> tuple[int, int]:
        if width / height > GPT_IMAGE_MAX_ASPECT_RATIO:
            height = self._normalize_gpt_image_dimension(
                int(width / GPT_IMAGE_MAX_ASPECT_RATIO)
            )
        elif height / width > GPT_IMAGE_MAX_ASPECT_RATIO:
            width = self._normalize_gpt_image_dimension(
                int(height / GPT_IMAGE_MAX_ASPECT_RATIO)
            )
        return width, height

    def _fit_gpt_image_pixel_count(self, width: int, height: int) -> tuple[int, int]:
        pixels = width * height
        if GPT_IMAGE_MIN_PIXELS <= pixels <= GPT_IMAGE_MAX_PIXELS:
            return width, height

        scale = (GPT_IMAGE_MIN_PIXELS / pixels) ** 0.5 if pixels < GPT_IMAGE_MIN_PIXELS else (
            GPT_IMAGE_MAX_PIXELS / pixels
        ) ** 0.5
        scaled_width = self._normalize_gpt_image_dimension(int(width * scale))
        scaled_height = self._normalize_gpt_image_dimension(int(height * scale))

        if scaled_width * scaled_height < GPT_IMAGE_MIN_PIXELS:
            if scaled_width <= scaled_height:
                scaled_width += GPT_IMAGE_SIZE_MULTIPLE
            else:
                scaled_height += GPT_IMAGE_SIZE_MULTIPLE

        while scaled_width * scaled_height > GPT_IMAGE_MAX_PIXELS:
            if scaled_width >= scaled_height:
                scaled_width -= GPT_IMAGE_SIZE_MULTIPLE
            else:
                scaled_height -= GPT_IMAGE_SIZE_MULTIPLE

        scaled_width, scaled_height = self._fit_gpt_image_aspect_ratio(
            scaled_width, scaled_height
        )

        return (
            min(scaled_width, GPT_IMAGE_MAX_EDGE),
            min(scaled_height, GPT_IMAGE_MAX_EDGE),
        )

    async def _make_request(
        self, url: str, payload: dict[str, Any], *, bearer_auth: bool = False
    ) -> bytes:
        headers = {
            "Authorization": f"Bearer {self.api_key}" if bearer_auth else self.api_key,
            "Content-Type": "application/json",
        }

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        response_text = await response.text()

                        if response.status == 429:
                            raise ProviderRateLimitError("GPTProto rate limit exceeded")

                        if response.status == 401:
                            raise ProviderConfigurationError(
                                f"Invalid API key: {response_text[:200]}"
                            )

                        if response.status >= 400:
                            raise ProviderError(
                                f"API error {response.status}: {response_text[:500]}"
                            )

                        data = json.loads(response_text)
                        return await self._process_response(session, data, headers)

            except (ProviderRateLimitError, ProviderTimeoutError):
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)

            except TimeoutError as e:
                raise ProviderTimeoutError(f"Request timed out after {self.timeout}s") from e

            except aiohttp.ClientError as e:
                logger.error(f"GPTProto attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"Request failed after {self.max_retries} attempts: {e}"
                    ) from e
                await asyncio.sleep(2**attempt)

        raise ProviderError("Request failed")

    async def _process_response(
        self,
        session: aiohttp.ClientSession,
        data: dict[str, Any],
        headers: dict[str, str],
    ) -> bytes:
        if "data" in data and isinstance(data["data"], dict):
            response_data = data["data"]
            status = response_data.get("status", "")

            if status == "failed":
                error = response_data.get("error", "Unknown error")
                raise ProviderError(f"Generation failed: {error}")

            if status in ("processing", "starting", "pending", "created"):
                return await self._poll_for_result(session, response_data, headers)

            outputs = response_data.get("outputs", [])
            if outputs:
                return await self._extract_image_from_outputs(session, outputs)

            urls = response_data.get("urls", {})
            if isinstance(urls, dict) and urls.get("get"):
                return await self._poll_url(session, urls["get"], headers)

        return await self._extract_image_legacy(session, data)

    async def _poll_for_result(
        self,
        session: aiohttp.ClientSession,
        response_data: dict[str, Any],
        headers: dict[str, str],
    ) -> bytes:
        prediction_id = response_data.get("id")
        urls = response_data.get("urls", {})

        if isinstance(urls, dict) and urls.get("get"):
            poll_url = urls["get"]
        elif prediction_id:
            poll_url = f"{self.base_url}/predictions/{prediction_id}/result"
        else:
            raise ProviderError("No prediction ID or URL found for polling")

        return await self._poll_url(session, poll_url, headers)

    async def _poll_url(
        self,
        session: aiohttp.ClientSession,
        poll_url: str,
        headers: dict[str, str],
    ) -> bytes:
        for _ in range(MAX_POLL_ATTEMPTS):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

            async with session.get(
                poll_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status == 202:
                    continue

                if response.status != 200:
                    response_text = await response.text()
                    raise ProviderError(
                        f"Poll request failed: {response.status} - {response_text[:200]}"
                    )

                data = json.loads(await response.text())

                if "data" in data and isinstance(data["data"], dict):
                    status = data["data"].get("status", "")
                    if status == "failed":
                        error = data["data"].get("error", "Unknown error")
                        raise ProviderError(f"Generation failed: {error}")
                    if status in ("processing", "starting", "pending", "created"):
                        continue

                    outputs = data["data"].get("outputs", [])
                    if outputs:
                        return await self._extract_image_from_outputs(session, outputs)

                return await self._extract_image_legacy(session, data)

        raise ProviderTimeoutError(
            f"Polling timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s"
        )

    async def _extract_image_from_outputs(
        self, session: aiohttp.ClientSession, outputs: list[Any]
    ) -> bytes:
        for output in outputs:
            if isinstance(output, dict):
                if "b64_json" in output:
                    return base64.b64decode(output["b64_json"])
                if "url" in output:
                    return await self._download_image(session, output["url"])
            elif isinstance(output, str):
                if output.startswith("http"):
                    return await self._download_image(session, output)
                if output.startswith("data:"):
                    return self._decode_data_uri(output)
                else:
                    return base64.b64decode(output)

        raise ProviderError("No image found in outputs")

    def _decode_data_uri(self, data_uri: str) -> bytes:
        _, separator, encoded = data_uri.partition(",")
        if not separator:
            raise ProviderError("Invalid data URI image output")
        return base64.b64decode(encoded)

    async def _extract_image_legacy(
        self, session: aiohttp.ClientSession, data: dict[str, Any]
    ) -> bytes:
        if "data" in data and isinstance(data["data"], list) and data["data"]:
            image_data = data["data"][0]
            if isinstance(image_data, dict):
                if "b64_json" in image_data:
                    return base64.b64decode(image_data["b64_json"])
                elif "url" in image_data:
                    return await self._download_image(session, image_data["url"])
            elif isinstance(image_data, str):
                if image_data.startswith("http"):
                    return await self._download_image(session, image_data)
                else:
                    return base64.b64decode(image_data)

        if "image" in data:
            img = data["image"]
            if isinstance(img, str):
                if img.startswith("http"):
                    return await self._download_image(session, img)
                return base64.b64decode(img)

        if "url" in data:
            return await self._download_image(session, data["url"])

        if "b64_json" in data:
            return base64.b64decode(data["b64_json"])

        raise ProviderError(f"Unexpected response format: {json.dumps(data)[:500]}")

    async def _download_image(self, session: aiohttp.ClientSession, url: str) -> bytes:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
            if response.status != 200:
                raise ProviderError(f"Failed to download image: {response.status}")
            return await response.read()

    async def analyze_style(
        self, image: bytes, prompt_override: str | None = None
    ) -> StyleAnalysis:
        raise NotImplementedError("Use GPT4VProvider for style analysis")

    async def upscale_image(self, image: bytes, target_size: int, *, content_type: str = "pattern", sharpen: bool = False) -> bytes:
        raise NotImplementedError("Use ReplicateProvider for upscaling")

    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        raise NotImplementedError("Use VectorizerProvider for vectorization")

    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        raise NotImplementedError("Use MockupsProvider for mockup compositing")


__all__ = ["GPTProtoProvider"]
