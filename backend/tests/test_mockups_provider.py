"""Tests for Dynamic Mockups provider."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from ai.schemas import Position
from providers.mockups import (
    MockupsProvider,
    MockupsProviderError,
    ProviderConfigurationError,
    ProviderInvalidTemplateError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)


@pytest.fixture
def mock_env_api_key(monkeypatch):
    """Set MOCKUPS_API_KEY environment variable."""
    monkeypatch.setenv("MOCKUPS_API_KEY", "test-api-key-12345")


@pytest.fixture
def provider(mock_env_api_key):
    """Create MockupsProvider instance."""
    return MockupsProvider(base_url="https://api.test-mockups.com")


@pytest.fixture
def sample_pattern():
    """Sample pattern image bytes."""
    return b"fake-pattern-image-data"


@pytest.fixture
def sample_template():
    """Sample template image bytes."""
    return b"fake-template-image-data"


@pytest.fixture
def default_position():
    """Default position parameters."""
    return Position(x=100, y=150, scale=1.5, rotation=45, opacity=0.9)


class TestMockupsProviderInitialization:
    """Test MockupsProvider initialization."""

    def test_init_with_explicit_api_key(self):
        provider = MockupsProvider(api_key="explicit-key", base_url="https://test.com")
        assert provider.api_key == "explicit-key"
        assert provider.base_url == "https://test.com"
        assert provider.timeout == 60

    def test_init_with_env_mockups_api_key(self, monkeypatch):
        monkeypatch.setenv("MOCKUPS_API_KEY", "env-mockups-key")
        provider = MockupsProvider()
        assert provider.api_key == "env-mockups-key"

    def test_init_with_env_dynamic_mockups_key(self, monkeypatch):
        monkeypatch.delenv("MOCKUPS_API_KEY", raising=False)
        monkeypatch.setenv("DYNAMIC_MOCKUPS_KEY", "env-dynamic-key")
        provider = MockupsProvider()
        assert provider.api_key == "env-dynamic-key"

    def test_init_missing_api_key_raises_error(self, monkeypatch):
        monkeypatch.delenv("MOCKUPS_API_KEY", raising=False)
        monkeypatch.delenv("DYNAMIC_MOCKUPS_KEY", raising=False)

        with pytest.raises(
            ProviderConfigurationError,
            match="Missing Mockups API key",
        ):
            MockupsProvider()

    def test_init_custom_timeout(self, mock_env_api_key):
        provider = MockupsProvider(timeout=120)
        assert provider.timeout == 120


class TestPositionValidation:
    """Test Position schema validation."""

    def test_position_validates_scale_min(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="greater_than_equal"):
            Position(x=0, y=0, scale=0.05, rotation=0, opacity=1.0)

    def test_position_validates_scale_max(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="less_than_equal"):
            Position(x=0, y=0, scale=15.0, rotation=0, opacity=1.0)

    def test_position_validates_rotation_max(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="less_than_equal"):
            Position(x=0, y=0, scale=1.0, rotation=400, opacity=1.0)

    def test_position_validates_opacity_max(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="less_than_equal"):
            Position(x=0, y=0, scale=1.0, rotation=0, opacity=1.5)


class TestCompositeMockup:
    """Test composite_mockup method."""

    @pytest.mark.asyncio
    async def test_composite_with_user_template_success(
        self, provider, sample_pattern, sample_template, default_position
    ):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"composited-mockup-image")

        with patch("providers.mockups.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session.post = MagicMock(return_value=mock_post)
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            result = await provider.composite_mockup(
                pattern=sample_pattern,
                template=sample_template,
                position=default_position,
            )

            assert result == b"composited-mockup-image"

            mock_session.post.assert_called_once()
            call_args = mock_session.post.call_args
            assert call_args[0][0] == "https://api.test-mockups.com/v1/composite"
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-api-key-12345"

    @pytest.mark.asyncio
    async def test_composite_with_built_in_template_success(
        self, provider, sample_pattern, sample_template, default_position
    ):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"composited-mockup-with-builtin")

        with patch("providers.mockups.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session.post = MagicMock(return_value=mock_post)
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            result = await provider.composite_mockup(
                pattern=sample_pattern,
                template=sample_template,
                position=default_position,
                template_id="tshirt-front-white",
            )

            assert result == b"composited-mockup-with-builtin"

    def test_position_validates_scale_min(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="greater_than_equal"):
            Position(x=0, y=0, scale=0.05, rotation=0, opacity=1.0)

    def test_position_validates_scale_max(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="less_than_equal"):
            Position(x=0, y=0, scale=15.0, rotation=0, opacity=1.0)

    def test_position_validates_rotation_max(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="less_than_equal"):
            Position(x=0, y=0, scale=1.0, rotation=400, opacity=1.0)

    def test_position_validates_opacity_max(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="less_than_equal"):
            Position(x=0, y=0, scale=1.0, rotation=0, opacity=1.5)

    @pytest.mark.asyncio
    async def test_composite_handles_rate_limit_error(
        self, provider, sample_pattern, sample_template, default_position
    ):
        mock_response = AsyncMock()
        mock_response.status = 429

        with patch("providers.mockups.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session.post = MagicMock(return_value=mock_post)
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            with pytest.raises(ProviderRateLimitError, match="Rate limit exceeded"):
                await provider.composite_mockup(
                    pattern=sample_pattern,
                    template=sample_template,
                    position=default_position,
                )

    @pytest.mark.asyncio
    async def test_composite_handles_invalid_template_error(
        self, provider, sample_pattern, sample_template, default_position
    ):
        mock_response = AsyncMock()
        mock_response.status = 422
        mock_response.text = AsyncMock(return_value="Invalid template format")

        with patch("providers.mockups.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session.post = MagicMock(return_value=mock_post)
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            with pytest.raises(
                ProviderInvalidTemplateError,
                match="Invalid template or position parameters",
            ):
                await provider.composite_mockup(
                    pattern=sample_pattern,
                    template=sample_template,
                    position=default_position,
                )

    @pytest.mark.asyncio
    async def test_composite_handles_invalid_api_key(
        self, provider, sample_pattern, sample_template, default_position
    ):
        mock_response = AsyncMock()
        mock_response.status = 401

        with patch("providers.mockups.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_post = AsyncMock()
            mock_post.__aenter__.return_value = mock_response
            mock_session.post = MagicMock(return_value=mock_post)
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            with pytest.raises(ProviderConfigurationError, match="Invalid API key"):
                await provider.composite_mockup(
                    pattern=sample_pattern,
                    template=sample_template,
                    position=default_position,
                )

    @pytest.mark.asyncio
    async def test_composite_handles_timeout(
        self, provider, sample_pattern, sample_template, default_position
    ):
        with patch("providers.mockups.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            mock_session.post = MagicMock(side_effect=TimeoutError("Connection timed out"))

            with pytest.raises(ProviderTimeoutError, match="Request timed out after 60 seconds"):
                await provider.composite_mockup(
                    pattern=sample_pattern,
                    template=sample_template,
                    position=default_position,
                )

    @pytest.mark.asyncio
    async def test_composite_handles_client_error(
        self, provider, sample_pattern, sample_template, default_position
    ):
        with patch("providers.mockups.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session
            mock_session.post = MagicMock(side_effect=aiohttp.ClientError("Connection failed"))

            with pytest.raises(MockupsProviderError, match="HTTP client error"):
                await provider.composite_mockup(
                    pattern=sample_pattern,
                    template=sample_template,
                    position=default_position,
                )


class TestUnsupportedOperations:
    """Test unsupported AIProvider methods."""

    @pytest.mark.asyncio
    async def test_analyze_style_not_implemented(self, provider):
        with pytest.raises(NotImplementedError, match="does not support style analysis"):
            await provider.analyze_style(b"image-data")

    @pytest.mark.asyncio
    async def test_generate_pattern_not_implemented(self, provider):
        from ai.schemas import GenerationParams, StyleAnalysis

        style = StyleAnalysis(
            style_description="test",
            color_palette=["#FF0000"],
            pattern_type="seamless",
        )
        params = GenerationParams(style="test", width=512, height=512)

        with pytest.raises(NotImplementedError, match="does not support pattern generation"):
            await provider.generate_pattern(style, params)

    @pytest.mark.asyncio
    async def test_upscale_image_not_implemented(self, provider):
        with pytest.raises(NotImplementedError, match="does not support upscaling"):
            await provider.upscale_image(b"image-data", 1024)

    @pytest.mark.asyncio
    async def test_vectorize_not_implemented(self, provider):
        with pytest.raises(NotImplementedError, match="does not support vectorization"):
            await provider.vectorize(b"image-data", "rgb")
