import base64
import json
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


class GPT4VProviderError(Exception):
    pass


class GPT4VProvider(AIProvider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o",
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GPT4V_API_KEY")
        if not self.api_key:
            raise ProviderConfigurationError("Missing API key: set OPENAI_API_KEY or GPT4V_API_KEY")

        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"

    @classmethod
    def from_config(cls, config: ProviderConfig) -> "GPT4VProvider":
        return cls(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model_name,
        )

    async def analyze_style(self, image: bytes) -> StyleAnalysis:
        image_b64 = base64.b64encode(image).decode("utf-8")

        prompt = """Analyze this clothing design image and provide a detailed style analysis in JSON format.

Return ONLY valid JSON with these exact fields:
{
  "style_description": "A concise natural language description of the design style",
  "color_palette": ["#HEX1", "#HEX2", "#HEX3"],
  "pattern_type": "seamless|standalone|full",
  "suggested_params": {
    "tiling": "tile|clamp|reflect|wrap",
    "scale": 0.5-2.0
  }
}

Pattern types:
- seamless: Repeating pattern with no visible seams (suitable for tiling)
- standalone: Single design element on a background
- full: Full-coverage design that fills the entire area

Extract 3-5 dominant colors as hex codes. Suggest optimal tiling mode and scale."""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.3,
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
                            retry_after = int(response.headers.get("Retry-After", 2**attempt))
                            raise ProviderRateLimitError(
                                f"Rate limited (attempt {attempt + 1}/{self.max_retries}). "
                                f"Retry after {retry_after}s"
                            )

                        if response.status == 401:
                            raise ProviderConfigurationError(
                                f"Invalid API key. Response: {response_text[:200]}"
                            )

                        if response.status >= 400:
                            raise GPT4VProviderError(
                                f"API error {response.status}: {response_text[:500]}"
                            )

                        try:
                            data = json.loads(response_text)
                        except json.JSONDecodeError as e:
                            raise GPT4VProviderError(
                                f"Invalid JSON from API: {response_text[:500]}"
                            ) from e

                        if "error" in data:
                            raise GPT4VProviderError(f"API error: {data['error']}")

                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        if not content:
                            raise GPT4VProviderError(
                                f"Empty response from API. Full response: {response_text[:500]}"
                            )

                        return self._parse_response(content)

            except TimeoutError as e:
                raise ProviderTimeoutError(f"Request timed out after {self.timeout}s") from e

            except aiohttp.ServerTimeoutError as e:
                raise ProviderTimeoutError(f"Request timed out after {self.timeout}s") from e

            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise GPT4VProviderError(
                        f"Network error after {self.max_retries} attempts: {e}"
                    ) from e
                continue

        raise GPT4VProviderError(f"Failed after {self.max_retries} attempts")

    def _parse_response(self, content: str) -> StyleAnalysis:
        original_content = content
        content = content.strip()

        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        if not content:
            raise GPT4VProviderError(
                f"Empty content after parsing. Original: '{original_content[:200]}'"
            )

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise GPT4VProviderError(f"Invalid JSON: {e}. Content: '{content[:300]}'") from e

        try:
            return StyleAnalysis(**parsed)
        except Exception as e:
            raise GPT4VProviderError(f"Invalid StyleAnalysis structure: {e}") from e

    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        raise NotImplementedError("Pattern generation not yet implemented")

    async def upscale_image(self, image: bytes, target_size: int) -> bytes:
        raise NotImplementedError("Image upscaling not yet implemented")

    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        raise NotImplementedError("Vectorization not yet implemented")

    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        raise NotImplementedError("Mockup compositing not yet implemented")
