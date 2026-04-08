import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from ai.schemas import StyleAnalysis
from providers.gpt4v import GPT4VProvider, GPT4VProviderError

MINIMAL_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEB"
    "AQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwABmQ/9k="
)


def create_mock_session(mock_response):
    mock_post = AsyncMock()
    mock_post.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post.__aexit__ = AsyncMock(return_value=None)

    mock_session_instance = AsyncMock()
    mock_session_instance.post = MagicMock(return_value=mock_post)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")


@pytest.fixture
def valid_response():
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "style_description": "Modern geometric pattern with clean lines",
                            "color_palette": ["#FF5733", "#33FF57", "#3357FF"],
                            "pattern_type": "seamless",
                            "suggested_params": {"tiling": "reflect", "scale": 1.2},
                        }
                    )
                }
            }
        ]
    }


@pytest.mark.asyncio
async def test_provider_initialization_with_env(mock_env):
    provider = GPT4VProvider()
    assert provider.api_key == "test-key-12345"
    assert provider.model == "gpt-4o"
    assert provider.timeout == 30
    assert provider.max_retries == 3


@pytest.mark.asyncio
async def test_provider_initialization_with_explicit_key():
    provider = GPT4VProvider(api_key="explicit-key")
    assert provider.api_key == "explicit-key"


@pytest.mark.asyncio
async def test_provider_initialization_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GPT4V_API_KEY", raising=False)

    with pytest.raises(ProviderConfigurationError, match="Missing API key"):
        GPT4VProvider()


@pytest.mark.asyncio
async def test_analyze_style_success(mock_env, valid_response):
    provider = GPT4VProvider()

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=valid_response)
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {}

    mock_session = create_mock_session(mock_response)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        result = await provider.analyze_style(MINIMAL_JPEG)

        assert isinstance(result, StyleAnalysis)
        assert result.style_description == "Modern geometric pattern with clean lines"
        assert result.color_palette == ["#FF5733", "#33FF57", "#3357FF"]
        assert result.pattern_type == "seamless"
        assert result.suggested_params == {"tiling": "reflect", "scale": 1.2}


@pytest.mark.asyncio
async def test_analyze_style_with_markdown_json(mock_env):
    provider = GPT4VProvider()

    markdown_response = {
        "choices": [
            {
                "message": {
                    "content": """```json
{
  "style_description": "Floral design",
  "color_palette": ["#AABBCC"],
  "pattern_type": "standalone",
  "suggested_params": {}
}
```"""
                }
            }
        ]
    }

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=markdown_response)
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {}

    mock_session = create_mock_session(mock_response)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        result = await provider.analyze_style(MINIMAL_JPEG)
        assert result.style_description == "Floral design"
        assert result.pattern_type == "standalone"


@pytest.mark.asyncio
async def test_analyze_style_rate_limited(mock_env):
    provider = GPT4VProvider(max_retries=1)

    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.headers = {"Retry-After": "5"}

    mock_session = create_mock_session(mock_response)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ProviderRateLimitError, match="Rate limited"):
            await provider.analyze_style(MINIMAL_JPEG)


@pytest.mark.asyncio
async def test_analyze_style_invalid_api_key(mock_env):
    provider = GPT4VProvider()

    mock_response = AsyncMock()
    mock_response.status = 401

    mock_session = create_mock_session(mock_response)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ProviderConfigurationError, match="Invalid API key"):
            await provider.analyze_style(MINIMAL_JPEG)


@pytest.mark.asyncio
async def test_analyze_style_server_error(mock_env):
    provider = GPT4VProvider(max_retries=1)

    mock_response = AsyncMock()
    mock_response.status = 503

    mock_session = create_mock_session(mock_response)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(GPT4VProviderError, match="Server error: 503"):
            await provider.analyze_style(MINIMAL_JPEG)


@pytest.mark.asyncio
async def test_analyze_style_empty_response(mock_env):
    provider = GPT4VProvider()

    empty_response = {"choices": [{"message": {"content": ""}}]}

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=empty_response)
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {}

    mock_session = create_mock_session(mock_response)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(GPT4VProviderError, match="Empty response from API"):
            await provider.analyze_style(MINIMAL_JPEG)


@pytest.mark.asyncio
async def test_analyze_style_invalid_json_response(mock_env):
    provider = GPT4VProvider()

    invalid_json_response = {"choices": [{"message": {"content": "not valid json"}}]}

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=invalid_json_response)
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {}

    mock_session = create_mock_session(mock_response)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(GPT4VProviderError, match="Invalid JSON in response"):
            await provider.analyze_style(MINIMAL_JPEG)


@pytest.mark.asyncio
async def test_analyze_style_invalid_schema(mock_env):
    provider = GPT4VProvider()

    invalid_schema_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "style_description": "Test",
                            "color_palette": ["#FF0000"],
                            "pattern_type": "invalid_type",
                        }
                    )
                }
            }
        ]
    }

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=invalid_schema_response)
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {}

    mock_session = create_mock_session(mock_response)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(GPT4VProviderError, match="Invalid StyleAnalysis structure"):
            await provider.analyze_style(MINIMAL_JPEG)


@pytest.mark.asyncio
async def test_analyze_style_network_error_with_retry(mock_env):
    import aiohttp

    provider = GPT4VProvider(max_retries=2)

    mock_session_instance = AsyncMock()
    mock_session_instance.post = MagicMock(side_effect=aiohttp.ClientError("Network error"))

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(GPT4VProviderError, match="Network error after 2 attempts"):
            await provider.analyze_style(MINIMAL_JPEG)


@pytest.mark.asyncio
async def test_analyze_style_timeout(mock_env):
    import aiohttp

    provider = GPT4VProvider(timeout=1)

    mock_session_instance = AsyncMock()
    mock_session_instance.post = MagicMock(side_effect=aiohttp.ServerTimeoutError())

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.gpt4v.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ProviderTimeoutError, match="Request timed out after 1s"):
            await provider.analyze_style(MINIMAL_JPEG)



@pytest.mark.asyncio
async def test_unimplemented_methods(mock_env):
    provider = GPT4VProvider()

    from ai.schemas import GenerationParams, Position

    with pytest.raises(NotImplementedError, match="Pattern generation"):
        await provider.generate_pattern(
            StyleAnalysis(
                style_description="test",
                color_palette=[],
                pattern_type="seamless",
                suggested_params={},
            ),
            GenerationParams(style="test"),
        )

    with pytest.raises(NotImplementedError, match="Image upscaling"):
        await provider.upscale_image(b"image", 1024)

    with pytest.raises(NotImplementedError, match="Vectorization"):
        await provider.vectorize(b"image")

    with pytest.raises(NotImplementedError, match="Mockup compositing"):
        await provider.composite_mockup(b"pattern", b"template", Position())


@pytest.mark.asyncio
async def test_parse_response_with_code_fence(mock_env):
    provider = GPT4VProvider()

    content = """```
{
  "style_description": "Test",
  "color_palette": ["#FFFFFF"],
  "pattern_type": "full",
  "suggested_params": {}
}
```"""

    result = provider._parse_response(content)
    assert result.style_description == "Test"
    assert result.pattern_type == "full"
