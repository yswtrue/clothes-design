import asyncio
import base64
import json
import logging
import os
import re

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


class OpenAIImageProvider(AIProvider):
    CHAT_IMAGE_MODELS = {"gpt-4o-image", "gpt-4o-image-vip", "gpt-image-1"}
    GPT_IMAGE_MODELS = {"gpt-image-1", "gpt-image-2", "gpt-image-3"}

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "dall-e-3",
        timeout: int = 300,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError(
                "Missing API key: set OPENAI_API_KEY or provide api_key"
            )

        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = (
            base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        )
        self.base_url = self.base_url.rstrip("/")

    @classmethod
    def from_config(cls, config: ProviderConfig) -> "OpenAIImageProvider":
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model_name or "dall-e-3",
        )

    def _is_chat_model(self) -> bool:
        model_lower = self.model.lower()
        return any(chat_model in model_lower for chat_model in self.CHAT_IMAGE_MODELS)

    def _is_gpt_image_model(self) -> bool:
        model_lower = self.model.lower()
        return any(gpt_model in model_lower for gpt_model in self.GPT_IMAGE_MODELS)

    async def generate_pattern(
        self, style: StyleAnalysis, params: GenerationParams
    ) -> bytes:
        if params.init_image_b64:
            return await self._generate_img2img(style, params)
        
        prompt = self._build_prompt(style, params)

        if self._is_chat_model():
            return await self._generate_via_chat(prompt, params)
        else:
            return await self._generate_via_images_api(prompt, params)

    async def _generate_via_images_api(
        self, prompt: str, params: GenerationParams
    ) -> bytes:
        size = self._get_dalle_size(params.width, params.height)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }

        if "dall-e-3" in self.model.lower():
            payload["quality"] = "standard"
            payload["style"] = "natural"

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/images/generations",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        response_text = await response.text()

                        if response.status == 429:
                            raise ProviderRateLimitError("OpenAI rate limit exceeded")

                        if response.status == 401:
                            raise ProviderConfigurationError(
                                f"Invalid API key: {response_text[:200]}"
                            )

                        if response.status == 402:
                            raise ProviderError(
                                f"Insufficient credits: {response_text[:200]}"
                            )

                        if response.status >= 400:
                            raise ProviderError(
                                f"API error {response.status}: {response_text[:500]}"
                            )

                        data = json.loads(response_text)
                        b64_data = data["data"][0]["b64_json"]
                        image_bytes = base64.b64decode(b64_data)

                        logger.info(
                            f"Image generated via DALL-E: {size}, model={self.model}"
                        )
                        return image_bytes

            except (ProviderRateLimitError, ProviderTimeoutError):
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)

            except TimeoutError as e:
                raise ProviderTimeoutError(
                    f"Request timed out after {self.timeout}s"
                ) from e

            except aiohttp.ClientError as e:
                logger.error(f"Generation attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"Generation failed after {self.max_retries} attempts: {e}"
                    ) from e
                await asyncio.sleep(2**attempt)

        raise ProviderError("Generation failed")

    async def _generate_via_chat(self, prompt: str, params: GenerationParams) -> bytes:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Generate an image: {prompt}",
                }
            ],
            "max_tokens": 1000,
        }

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        response_text = await response.text()

                        if response.status == 429:
                            raise ProviderRateLimitError("OpenAI rate limit exceeded")

                        if response.status == 401:
                            raise ProviderConfigurationError(
                                f"Invalid API key: {response_text[:200]}"
                            )

                        if response.status == 402:
                            raise ProviderError(
                                f"Insufficient credits: {response_text[:200]}"
                            )

                        if response.status >= 400:
                            raise ProviderError(
                                f"API error {response.status}: {response_text[:500]}"
                            )

                        data = json.loads(response_text)
                        content = (
                            data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )

                        if not content:
                            raise ProviderError(
                                f"Empty response from API: {response_text[:500]}"
                            )

                        image_url = self._extract_image_url(content)
                        if not image_url:
                            raise ProviderError(
                                f"No image URL found in response: {content[:500]}"
                            )

                        image_bytes = await self._download_image(session, image_url)

                        logger.info(
                            f"Image generated via chat model: model={self.model}"
                        )
                        return image_bytes

            except (ProviderRateLimitError, ProviderTimeoutError):
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)

            except TimeoutError as e:
                raise ProviderTimeoutError(
                    f"Request timed out after {self.timeout}s"
                ) from e

            except aiohttp.ClientError as e:
                logger.error(f"Generation attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"Generation failed after {self.max_retries} attempts: {e}"
                    ) from e
                await asyncio.sleep(2**attempt)

        raise ProviderError("Generation failed")

    def _extract_image_url(self, content: str) -> str | None:
        # Markdown: ![...](url)
        md_match = re.search(r"!\[.*?\]\((https?://[^\s\)]+)\)", content)
        if md_match:
            return md_match.group(1)

        # URL with image extension
        url_match = re.search(r"(https?://[^\s\"\'\)]+\.(?:png|jpg|jpeg|webp))", content)
        if url_match:
            return url_match.group(1)

        # Any URL (some APIs return URLs without extension)
        url_match = re.search(r"(https?://[^\s\"\'\)]+)", content)
        if url_match:
            return url_match.group(1)

        return None

    async def _download_image(
        self, session: aiohttp.ClientSession, url: str
    ) -> bytes:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            if response.status != 200:
                raise ProviderError(
                    f"Failed to download image: {response.status}"
                )
            return await response.read()

    def _get_dalle_size(self, width: int, height: int) -> str:
        aspect = width / height if height > 0 else 1.0

        if "dall-e-3" in self.model.lower():
            if aspect > 1.3:
                return "1792x1024"
            elif aspect < 0.77:
                return "1024x1792"
            else:
                return "1024x1024"
        else:
            return "1024x1024"

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        from math import gcd
        
        if width <= 0 or height <= 0:
            return "1:1"
        
        divisor = gcd(width, height)
        w_ratio = width // divisor
        h_ratio = height // divisor
        
        valid_ratios = [
            "1:1", "1:4", "1:8", "2:3", "3:2", "3:4", 
            "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9"
        ]
        
        exact_ratio = f"{w_ratio}:{h_ratio}"
        if exact_ratio in valid_ratios:
            return exact_ratio
        
        aspect = width / height
        ratio_values = {
            "1:1": 1.0, "1:4": 0.25, "1:8": 0.125, "2:3": 0.667, "3:2": 1.5,
            "3:4": 0.75, "4:1": 4.0, "4:3": 1.333, "4:5": 0.8, "5:4": 1.25,
            "8:1": 8.0, "9:16": 0.5625, "16:9": 1.778, "21:9": 2.333
        }
        
        closest = min(valid_ratios, key=lambda r: abs(ratio_values[r] - aspect))
        return closest

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

    async def _generate_img2img(
        self, style: StyleAnalysis, params: GenerationParams
    ) -> bytes:
        return await self._generate_via_images_edit_api(style, params)

    async def _generate_via_images_edit_api(
        self, style: StyleAnalysis, params: GenerationParams
    ) -> bytes:
        if not params.init_image_b64:
            raise ProviderError("init_image_b64 is required for image editing")

        prompt = self._build_fabric_prompt(style, params)
        image_bytes = base64.b64decode(params.init_image_b64)
        url = f"{self.base_url}/images/edits"
        size = self._get_aspect_ratio(params.width, params.height)

        logger.info(
            f"images/edits request: url={url}, model={self.model}, "
            f"size={size}, image_size={len(image_bytes)}, prompt_length={len(prompt)}"
        )

        for attempt in range(self.max_retries):
            form = aiohttp.FormData()
            form.add_field("model", self.model)
            form.add_field("prompt", prompt)
            form.add_field("image", image_bytes, filename="image.png", content_type="image/png")
            form.add_field("n", "1")
            form.add_field("size", size)

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        data=form,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        response_text = await response.text()

                        logger.info(
                            f"images/edits response: status={response.status}, "
                            f"body_length={len(response_text)}, "
                            f"body_preview={response_text[:500]}"
                        )

                        if response.status == 429:
                            raise ProviderRateLimitError("OpenAI rate limit exceeded")

                        if response.status == 401:
                            raise ProviderConfigurationError(f"Invalid API key: {response_text[:200]}")

                        if response.status >= 400:
                            logger.error(
                                f"images/edits API error: status={response.status}, "
                                f"url={url}, model={self.model}, response={response_text}"
                            )
                            raise ProviderError(f"API error {response.status}: {response_text[:500]}")

                        data = json.loads(response_text)
                        if "data" in data and data["data"]:
                            if "b64_json" in data["data"][0]:
                                logger.info("images/edits success: got b64_json response")
                                return base64.b64decode(data["data"][0]["b64_json"])
                            elif "url" in data["data"][0]:
                                logger.info(f"images/edits success: downloading from URL")
                                return await self._download_image(session, data["data"][0]["url"])

                        logger.error(f"images/edits unexpected format: {response_text}")
                        raise ProviderError(f"Unexpected response format: {response_text[:500]}")

            except (ProviderRateLimitError, ProviderTimeoutError, ProviderError, ProviderConfigurationError):
                logger.error(f"images/edits attempt {attempt + 1} failed with provider error", exc_info=True)
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)

            except TimeoutError as e:
                logger.error(f"images/edits attempt {attempt + 1} timed out after {self.timeout}s")
                raise ProviderTimeoutError(f"Request timed out after {self.timeout}s") from e

            except aiohttp.ClientError as e:
                logger.error(
                    f"images/edits attempt {attempt + 1} network error: {type(e).__name__}: {e}",
                    exc_info=True
                )
                if attempt == self.max_retries - 1:
                    raise ProviderError(f"Images edit failed after {self.max_retries} attempts: {e}") from e
                await asyncio.sleep(2**attempt)

            except Exception as e:
                logger.error(
                    f"images/edits attempt {attempt + 1} unexpected error: {type(e).__name__}: {e}",
                    exc_info=True
                )
                if attempt == self.max_retries - 1:
                    raise ProviderError(f"Images edit failed: {e}") from e
                await asyncio.sleep(2**attempt)

        raise ProviderError("Images edit failed")

    async def _generate_img2img_via_chat(
        self, style: StyleAnalysis, params: GenerationParams
    ) -> bytes:
        prompt = self._build_fabric_prompt(style, params)
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{params.init_image_b64}",
                            },
                        },
                        {
                            "type": "text",
                            "text": f"Generate a new image: {prompt}",
                        },
                    ],
                }
            ],
            "max_tokens": 1000,
        }

        logger.info(f"img2img request: url={url}, model={self.model}, base_url={self.base_url}")

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        response_text = await response.text()
                        
                        logger.info(
                            f"img2img response: status={response.status}, "
                            f"body_length={len(response_text)}, "
                            f"body_preview={response_text[:500]}"
                        )

                        if response.status == 429:
                            raise ProviderRateLimitError("OpenAI rate limit exceeded")

                        if response.status == 401:
                            raise ProviderConfigurationError(
                                f"Invalid API key: {response_text[:200]}"
                            )

                        if response.status >= 400:
                            logger.error(
                                f"img2img API error: status={response.status}, "
                                f"url={url}, model={self.model}, "
                                f"response={response_text}"
                            )
                            raise ProviderError(
                                f"API error {response.status}: {response_text[:500]}"
                            )

                        data = json.loads(response_text)
                        content = (
                            data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )

                        if not content:
                            logger.error(f"img2img empty content: response={response_text}")
                            raise ProviderError(
                                f"Empty response from API: {response_text[:500]}"
                            )

                        image_url = self._extract_image_url(content)
                        if not image_url:
                            logger.error(f"img2img no image URL: content={content}")
                            raise ProviderError(
                                f"No image URL found in response: {content[:500]}"
                            )

                        image_bytes = await self._download_image(session, image_url)

                        logger.info(
                            f"img2img generated via chat model: model={self.model}"
                        )
                        return image_bytes

            except (ProviderRateLimitError, ProviderTimeoutError, ProviderError, ProviderConfigurationError):
                logger.error(f"img2img attempt {attempt + 1} failed with provider error", exc_info=True)
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)

            except TimeoutError as e:
                logger.error(f"img2img attempt {attempt + 1} timed out after {self.timeout}s")
                raise ProviderTimeoutError(
                    f"Request timed out after {self.timeout}s"
                ) from e

            except aiohttp.ClientError as e:
                logger.error(
                    f"img2img attempt {attempt + 1} network error: {type(e).__name__}: {e}",
                    exc_info=True
                )
                if attempt == self.max_retries - 1:
                    raise ProviderError(
                        f"img2img failed after {self.max_retries} attempts: {e}"
                    ) from e
                await asyncio.sleep(2**attempt)
            
            except Exception as e:
                logger.error(
                    f"img2img attempt {attempt + 1} unexpected error: {type(e).__name__}: {e}",
                    exc_info=True
                )
                if attempt == self.max_retries - 1:
                    raise ProviderError(f"img2img failed: {e}") from e
                await asyncio.sleep(2**attempt)

        raise ProviderError("img2img generation failed")

    async def analyze_style(self, image: bytes, prompt_override: str | None = None) -> StyleAnalysis:
        raise NotImplementedError("Use GPT4VProvider for style analysis")

    async def upscale_image(self, image: bytes, target_size: int) -> bytes:
        raise NotImplementedError("Use ReplicateProvider for upscaling")

    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        raise NotImplementedError("Use VectorizerProvider for vectorization")

    async def composite_mockup(
        self, pattern: bytes, template: bytes, position: Position
    ) -> bytes:
        raise NotImplementedError("Use MockupsProvider for mockup compositing")


__all__ = ["OpenAIImageProvider"]
