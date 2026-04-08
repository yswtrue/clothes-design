"""Tests for ESRGAN provider."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from PIL import Image

from ai.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from providers.esrgan import ESRGANProvider, ESRGANProviderError


def create_test_image(width: int = 512, height: int = 512) -> bytes:
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class MockResponse:
    def __init__(self, status, headers=None, iter_chunked_func=None):
        self.status = status
        self.headers = headers or {}
        self._iter_chunked_func = iter_chunked_func

    def raise_for_status(self):
        pass

    async def iter_chunked(self, chunk_size):
        if self._iter_chunked_func:
            async for chunk in self._iter_chunked_func(chunk_size):
                yield chunk

    @property
    def content(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.fixture
def esrgan_provider():
    return ESRGANProvider(api_key="test-key", api_url="https://test-api.com/v1")


@pytest.mark.asyncio
async def test_missing_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ProviderConfigurationError, match="Missing ESRGAN API key"):
            ESRGANProvider()


@pytest.mark.asyncio
async def test_api_key_from_env_esrgan():
    with patch.dict("os.environ", {"ESRGAN_API_KEY": "env-key"}):
        provider = ESRGANProvider()
        assert provider.api_key == "env-key"


@pytest.mark.asyncio
async def test_api_key_from_env_realesrgan():
    with patch.dict("os.environ", {"REALESRGAN_API_KEY": "real-env-key"}):
        provider = ESRGANProvider()
        assert provider.api_key == "real-env-key"


@pytest.mark.asyncio
async def test_upscale_target_size_too_small(esrgan_provider):
    image = create_test_image()
    with pytest.raises(ValueError, match="Target size must be 1024-16384"):
        await esrgan_provider.upscale_image(image, target_size=512)


@pytest.mark.asyncio
async def test_upscale_target_size_too_large(esrgan_provider):
    image = create_test_image()
    with pytest.raises(ValueError, match="Target size must be 1024-16384"):
        await esrgan_provider.upscale_image(image, target_size=20000)


@pytest.mark.asyncio
async def test_upscale_invalid_image_format(esrgan_provider):
    invalid_image = b"not an image"
    with pytest.raises(ValueError, match="Invalid image format"):
        await esrgan_provider.upscale_image(invalid_image, target_size=2048)


@pytest.mark.asyncio
async def test_upscale_success_2x_scale(esrgan_provider):
    input_image = create_test_image(1024, 1024)
    output_image = create_test_image(2048, 2048)

    async def mock_iter_chunked(chunk_size):
        yield output_image

    mock_response = MockResponse(status=200, iter_chunked_func=mock_iter_chunked)
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        result = await esrgan_provider.upscale_image(input_image, target_size=2048)

        assert result == output_image


@pytest.mark.asyncio
async def test_upscale_success_4x_scale(esrgan_provider):
    input_image = create_test_image(1024, 1024)
    output_image = create_test_image(4096, 4096)

    async def mock_iter_chunked(chunk_size):
        yield output_image

    mock_response = MockResponse(status=200, iter_chunked_func=mock_iter_chunked)
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        result = await esrgan_provider.upscale_image(input_image, target_size=4096)

        assert result == output_image


@pytest.mark.asyncio
async def test_upscale_success_8x_scale(esrgan_provider):
    input_image = create_test_image(1024, 1024)
    output_image = create_test_image(8192, 8192)

    async def mock_iter_chunked(chunk_size):
        yield output_image

    mock_response = MockResponse(status=200, iter_chunked_func=mock_iter_chunked)
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        result = await esrgan_provider.upscale_image(input_image, target_size=12000)

        assert result == output_image


@pytest.mark.asyncio
async def test_upscale_streaming_large_file(esrgan_provider):
    input_image = create_test_image(2048, 2048)
    chunk1 = b"chunk1" * 1000
    chunk2 = b"chunk2" * 1000
    chunk3 = b"chunk3" * 1000

    async def mock_iter_chunked(chunk_size):
        yield chunk1
        yield chunk2
        yield chunk3

    mock_response = MockResponse(status=200, iter_chunked_func=mock_iter_chunked)
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        result = await esrgan_provider.upscale_image(input_image, target_size=8192)

        # Should concatenate all chunks
        assert result == chunk1 + chunk2 + chunk3


@pytest.mark.asyncio
async def test_upscale_rate_limit_error(esrgan_provider):
    input_image = create_test_image()

    mock_response = MockResponse(status=429, headers={"Retry-After": "5"})
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ProviderRateLimitError, match="Rate limited"):
            await esrgan_provider.upscale_image(input_image, target_size=2048)


@pytest.mark.asyncio
async def test_upscale_auth_error(esrgan_provider):
    input_image = create_test_image()

    mock_response = MockResponse(status=401)
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ProviderConfigurationError, match="Invalid API key"):
            await esrgan_provider.upscale_image(input_image, target_size=2048)


@pytest.mark.asyncio
async def test_upscale_file_too_large_error(esrgan_provider):
    input_image = create_test_image()

    mock_response = MockResponse(status=413)
    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ValueError, match="Image too large for upscaling"):
            await esrgan_provider.upscale_image(input_image, target_size=2048)


@pytest.mark.asyncio
async def test_upscale_server_error_with_retry(esrgan_provider):
    input_image = create_test_image()

    mock_response = MockResponse(status=500)

    call_count = 0

    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_response

    mock_session = MagicMock()
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ESRGANProviderError, match="Server error: 500"):
            await esrgan_provider.upscale_image(input_image, target_size=2048)

        # Should retry 3 times
        assert call_count == 3


@pytest.mark.asyncio
async def test_upscale_network_error_with_retry(esrgan_provider):
    input_image = create_test_image()

    call_count = 0

    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise aiohttp.ClientError("Network error")

    mock_session = AsyncMock()
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ESRGANProviderError, match="Network error after 3 attempts"):
            await esrgan_provider.upscale_image(input_image, target_size=2048)

        assert call_count == 3


@pytest.mark.asyncio
async def test_upscale_timeout_error(esrgan_provider):
    input_image = create_test_image()

    def mock_post(*args, **kwargs):
        raise aiohttp.ServerTimeoutError("Timeout")

    mock_session = AsyncMock()
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("providers.esrgan.aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(ProviderTimeoutError, match="Request timed out after 120s"):
            await esrgan_provider.upscale_image(input_image, target_size=2048)


@pytest.mark.asyncio
async def test_analyze_style_not_implemented(esrgan_provider):
    with pytest.raises(NotImplementedError, match="Style analysis not supported"):
        await esrgan_provider.analyze_style(b"image")


@pytest.mark.asyncio
async def test_generate_pattern_not_implemented(esrgan_provider):
    from ai.schemas import GenerationParams, StyleAnalysis

    style = StyleAnalysis(
        style_description="test",
        color_palette=["#FF0000"],
        pattern_type="seamless",
        suggested_params={"tiling": "tile", "scale": 1.0},
    )
    params = GenerationParams(style="test", width=1024, height=1024)

    with pytest.raises(NotImplementedError, match="Pattern generation not supported"):
        await esrgan_provider.generate_pattern(style, params)


@pytest.mark.asyncio
async def test_vectorize_not_implemented(esrgan_provider):
    with pytest.raises(NotImplementedError, match="Vectorization not supported"):
        await esrgan_provider.vectorize(b"image")


@pytest.mark.asyncio
async def test_composite_mockup_not_implemented(esrgan_provider):
    from ai.schemas import Position

    position = Position(x=0, y=0, width=100, height=100)

    with pytest.raises(NotImplementedError, match="Mockup compositing not supported"):
        await esrgan_provider.composite_mockup(b"pattern", b"template", position)
