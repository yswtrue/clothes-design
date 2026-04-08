"""Tests for Vectorizer.ai provider."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ai.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from providers.vectorizer import VectorizerError, VectorizerProvider


async def async_chunk_iterator(chunks):
    """Helper to create async iterator from list of chunks."""
    for chunk in chunks:
        yield chunk


@pytest.fixture
def test_image() -> bytes:
    """Minimal valid PNG bytes."""
    png_header = b"\x89PNG\r\n\x1a\n"
    ihdr_chunk = b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    crc = b"\x90wS\xde"
    idat_chunk = b"\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    idat_crc = b"\r\n-\xb4"
    iend_chunk = b"\x00\x00\x00\x00IEND\xae\x42\x60\x82"
    return png_header + ihdr_chunk + crc + idat_chunk + idat_crc + iend_chunk


@pytest.fixture
def mock_tif_response() -> bytes:
    """Mock TIF file bytes (with TIFF magic number)."""
    tiff_header = b"II*\x00"
    return tiff_header + b"\x00" * 100


class TestVectorizerProviderInit:
    """Test VectorizerProvider initialization."""

    def test_init_with_api_key(self) -> None:
        """Test initialization with explicit API key."""
        provider = VectorizerProvider(api_key="test-key-123")
        assert provider.api_key == "test-key-123"
        assert provider.timeout == 90
        assert provider.base_url == "https://api.vectorizer.ai/api/v1"

    def test_init_with_env_var_vectorizer_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with VECTORIZER_API_KEY env var."""
        monkeypatch.setenv("VECTORIZER_API_KEY", "env-key-456")
        provider = VectorizerProvider()
        assert provider.api_key == "env-key-456"

    def test_init_with_env_var_vectorizer_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with VECTORIZER_KEY fallback env var."""
        monkeypatch.delenv("VECTORIZER_API_KEY", raising=False)
        monkeypatch.setenv("VECTORIZER_KEY", "fallback-key-789")
        provider = VectorizerProvider()
        assert provider.api_key == "fallback-key-789"

    def test_init_priority_explicit_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test explicit API key takes priority over environment variables."""
        monkeypatch.setenv("VECTORIZER_API_KEY", "env-key")
        provider = VectorizerProvider(api_key="explicit-key")
        assert provider.api_key == "explicit-key"

    def test_init_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization fails without API key."""
        monkeypatch.delenv("VECTORIZER_API_KEY", raising=False)
        monkeypatch.delenv("VECTORIZER_KEY", raising=False)

        with pytest.raises(ProviderConfigurationError, match="Missing Vectorizer API key"):
            VectorizerProvider()

    def test_init_custom_timeout(self) -> None:
        """Test initialization with custom timeout."""
        provider = VectorizerProvider(api_key="test-key", timeout=120)
        assert provider.timeout == 120


class TestVectorizerProviderVectorize:
    """Test VectorizerProvider.vectorize() method."""

    @pytest.mark.asyncio
    async def test_vectorize_cmyk_success(
        self, test_image: bytes, mock_tif_response: bytes
    ) -> None:
        """Test successful CMYK vectorization."""
        provider = VectorizerProvider(api_key="test-key")

        chunks = [
            mock_tif_response[i : i + 8192] for i in range(0, len(mock_tif_response), 8192)
        ]  # fmt: skip

        mock_content = AsyncMock()
        mock_content.iter_chunked = Mock(return_value=async_chunk_iterator(chunks))

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.raise_for_status = AsyncMock()
        mock_response.content = mock_content
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.vectorize(test_image, "CMYK")

        assert result == mock_tif_response
        assert result.startswith(b"II*\x00")

    @pytest.mark.asyncio
    async def test_vectorize_rgb_success(self, test_image: bytes, mock_tif_response: bytes) -> None:
        """Test successful RGB vectorization."""
        provider = VectorizerProvider(api_key="test-key")

        chunks = [
            mock_tif_response[i : i + 8192] for i in range(0, len(mock_tif_response), 8192)
        ]  # fmt: skip

        mock_content = AsyncMock()
        mock_content.iter_chunked = Mock(return_value=async_chunk_iterator(chunks))

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.raise_for_status = AsyncMock()
        mock_response.content = mock_content
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.vectorize(test_image, "RGB")

        assert result == mock_tif_response

    @pytest.mark.asyncio
    async def test_vectorize_default_color_space(
        self, test_image: bytes, mock_tif_response: bytes
    ) -> None:
        """Test default color space is CMYK."""
        provider = VectorizerProvider(api_key="test-key")

        chunks = [
            mock_tif_response[i : i + 8192] for i in range(0, len(mock_tif_response), 8192)
        ]  # fmt: skip

        mock_content = AsyncMock()
        mock_content.iter_chunked = Mock(return_value=async_chunk_iterator(chunks))

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.raise_for_status = AsyncMock()
        mock_response.content = mock_content
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.vectorize(test_image)

        assert result == mock_tif_response

    @pytest.mark.asyncio
    async def test_vectorize_invalid_color_space(self, test_image: bytes) -> None:
        """Test vectorize raises ValueError for invalid color space."""
        provider = VectorizerProvider(api_key="test-key")

        with pytest.raises(ValueError, match="Color space must be 'CMYK' or 'RGB'"):
            await provider.vectorize(test_image, "LAB")

        with pytest.raises(ValueError, match="Color space must be 'CMYK' or 'RGB'"):
            await provider.vectorize(test_image, "HSV")

    @pytest.mark.asyncio
    async def test_vectorize_invalid_api_key(self, test_image: bytes) -> None:
        """Test vectorize raises ProviderConfigurationError for 401."""
        provider = VectorizerProvider(api_key="invalid-key")

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ProviderConfigurationError, match="Invalid Vectorizer API key"):
                await provider.vectorize(test_image, "CMYK")

    @pytest.mark.asyncio
    async def test_vectorize_rate_limit(self, test_image: bytes) -> None:
        """Test vectorize raises ProviderRateLimitError for 429."""
        provider = VectorizerProvider(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {"Retry-After": "120"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ProviderRateLimitError, match=r"Rate limit exceeded.*120s"):
                await provider.vectorize(test_image, "CMYK")

    @pytest.mark.asyncio
    async def test_vectorize_rate_limit_default_retry(self, test_image: bytes) -> None:
        """Test rate limit with default Retry-After."""
        provider = VectorizerProvider(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ProviderRateLimitError, match=r"Rate limit exceeded.*60s"):
                await provider.vectorize(test_image, "CMYK")

    @pytest.mark.asyncio
    async def test_vectorize_unsupported_format(self, test_image: bytes) -> None:
        """Test vectorize raises ValueError for 415."""
        provider = VectorizerProvider(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.status = 415
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ValueError, match="Unsupported image format"):
                await provider.vectorize(test_image, "CMYK")

    @pytest.mark.asyncio
    async def test_vectorize_file_too_large(self, test_image: bytes) -> None:
        """Test vectorize raises ValueError for 413."""
        provider = VectorizerProvider(api_key="test-key")

        mock_response = AsyncMock()
        mock_response.status = 413
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ValueError, match="Image file too large"):
                await provider.vectorize(test_image, "CMYK")

    @pytest.mark.asyncio
    async def test_vectorize_timeout(self, test_image: bytes) -> None:
        """Test vectorize raises ProviderTimeoutError on timeout."""
        provider = VectorizerProvider(api_key="test-key", timeout=5)

        from aiohttp import ServerTimeoutError

        with patch(
            "aiohttp.ClientSession.post",
            side_effect=ServerTimeoutError("Request timeout"),
        ):
            with pytest.raises(ProviderTimeoutError, match="timed out after 5s"):
                await provider.vectorize(test_image, "CMYK")

    @pytest.mark.asyncio
    async def test_vectorize_network_error(self, test_image: bytes) -> None:
        """Test vectorize raises VectorizerError on network error."""
        provider = VectorizerProvider(api_key="test-key")

        from aiohttp import ClientConnectionError

        with patch(
            "aiohttp.ClientSession.post",
            side_effect=ClientConnectionError("Connection failed"),
        ):
            with pytest.raises(VectorizerError, match="Network error during vectorization"):
                await provider.vectorize(test_image, "CMYK")

    @pytest.mark.asyncio
    async def test_vectorize_large_file_streaming(self, test_image: bytes) -> None:
        """Test vectorize streams large files in chunks."""
        provider = VectorizerProvider(api_key="test-key")

        large_tif = b"II*\x00" + b"\xff" * (5 * 1024 * 1024)
        chunks = [large_tif[i : i + 8192] for i in range(0, len(large_tif), 8192)]

        mock_content = AsyncMock()
        mock_content.iter_chunked = Mock(return_value=async_chunk_iterator(chunks))

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.raise_for_status = AsyncMock()
        mock_response.content = mock_content
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_post = AsyncMock()
        mock_post.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await provider.vectorize(test_image, "CMYK")

        assert len(result) == len(large_tif)
        assert result.startswith(b"II*\x00")


class TestVectorizerProviderUnimplemented:
    """Test unimplemented AIProvider methods."""

    @pytest.mark.asyncio
    async def test_analyze_style_not_implemented(self, test_image: bytes) -> None:
        """Test analyze_style raises NotImplementedError."""
        provider = VectorizerProvider(api_key="test-key")
        with pytest.raises(NotImplementedError, match="Style analysis not supported"):
            await provider.analyze_style(test_image)

    @pytest.mark.asyncio
    async def test_generate_pattern_not_implemented(self) -> None:
        """Test generate_pattern raises NotImplementedError."""
        from ai.schemas import GenerationParams, StyleAnalysis

        provider = VectorizerProvider(api_key="test-key")
        style = StyleAnalysis(
            style_description="test",
            color_palette=["#FF0000"],
            pattern_type="seamless",
            suggested_params={"tiling": "tile", "scale": 1.0},
        )
        params = GenerationParams(
            style="test-style", width=1024, height=1024, tiling="tile", seed=42
        )

        with pytest.raises(NotImplementedError, match="Pattern generation not supported"):
            await provider.generate_pattern(style, params)

    @pytest.mark.asyncio
    async def test_upscale_image_not_implemented(self, test_image: bytes) -> None:
        """Test upscale_image raises NotImplementedError."""
        provider = VectorizerProvider(api_key="test-key")
        with pytest.raises(NotImplementedError, match="Image upscaling not supported"):
            await provider.upscale_image(test_image, 2048)

    @pytest.mark.asyncio
    async def test_composite_mockup_not_implemented(self, test_image: bytes) -> None:
        """Test composite_mockup raises NotImplementedError."""
        from ai.schemas import Position

        provider = VectorizerProvider(api_key="test-key")
        position = Position(x=0, y=0, scale=1.0, rotation=0, opacity=1.0)

        with pytest.raises(NotImplementedError, match="Mockup compositing not supported"):
            await provider.composite_mockup(test_image, test_image, position)
