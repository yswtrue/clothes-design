"""Tests for Stability AI provider."""

import base64
from unittest.mock import AsyncMock, patch

import pytest

from ai.schemas import GenerationParams, StyleAnalysis
from providers.stability import (
    ProviderConfigurationError,
    ProviderContentPolicyError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StabilityProvider,
)


@pytest.fixture
def sample_style() -> StyleAnalysis:
    return StyleAnalysis(
        style_description="Geometric minimalist pattern with clean lines",
        color_palette=["#FF6B6B", "#4ECDC4", "#FFFFFF"],
        pattern_type="seamless",
        suggested_params={"tiling": "tile", "scale": 1.0},
    )


@pytest.fixture
def sample_params() -> GenerationParams:
    return GenerationParams(
        style="geometric_minimal",
        tiling="tile",
        width=512,
        height=512,
        seed=42,
    )


@pytest.fixture
def mock_response_data() -> dict:
    fake_image = b"\x89PNG\r\n\x1a\n"
    return {
        "artifacts": [
            {"base64": base64.b64encode(fake_image).decode("utf-8"), "finishReason": "SUCCESS"}
        ]
    }


class TestStabilityProviderInit:
    def test_init_with_explicit_key(self) -> None:
        provider = StabilityProvider(api_key="test-key-123")
        assert provider.api_key == "test-key-123"
        assert provider.base_url == "https://api.stability.ai"

    def test_init_with_env_stability_api_key(self, monkeypatch) -> None:
        monkeypatch.setenv("STABILITY_API_KEY", "env-key-123")
        provider = StabilityProvider()
        assert provider.api_key == "env-key-123"

    def test_init_with_env_stability_key(self, monkeypatch) -> None:
        monkeypatch.delenv("STABILITY_API_KEY", raising=False)
        monkeypatch.setenv("STABILITY_KEY", "fallback-key-123")
        provider = StabilityProvider()
        assert provider.api_key == "fallback-key-123"

    def test_init_without_key_raises_error(self, monkeypatch) -> None:
        monkeypatch.delenv("STABILITY_API_KEY", raising=False)
        monkeypatch.delenv("STABILITY_KEY", raising=False)
        with pytest.raises(ProviderConfigurationError, match="Missing Stability API key"):
            StabilityProvider()

    def test_init_with_custom_base_url(self) -> None:
        provider = StabilityProvider(api_key="test-key", base_url="https://custom.api")
        assert provider.base_url == "https://custom.api"


class TestGeneratePattern:
    @pytest.mark.asyncio
    async def test_generate_success(
        self, sample_style: StyleAnalysis, sample_params: GenerationParams, mock_response_data: dict
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await provider.generate_pattern(sample_style, sample_params)

            assert isinstance(result, bytes)
            assert result.startswith(b"\x89PNG")

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "Authorization" in call_args.kwargs["headers"]
            assert call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"

            payload = call_args.kwargs["json"]
            assert payload["width"] == 512
            assert payload["height"] == 512
            assert payload["seed"] == 42
            assert payload["sampler"] == "K_DPMPP_2M"

    @pytest.mark.asyncio
    async def test_generate_with_different_tiling_modes(
        self, sample_style: StyleAnalysis, mock_response_data: dict
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        tiling_modes = {
            "tile": "K_DPMPP_2M",
            "clamp": "K_EULER",
            "reflect": "K_EULER_ANCESTRAL",
            "wrap": "K_DPM_2",
        }

        for tiling, expected_sampler in tiling_modes.items():
            params = GenerationParams(style="test", tiling=tiling, width=512, height=512, seed=42)

            with patch("aiohttp.ClientSession.post") as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value=mock_response_data)
                mock_response.raise_for_status = AsyncMock()
                mock_post.return_value.__aenter__.return_value = mock_response

                await provider.generate_pattern(sample_style, params)

                payload = mock_post.call_args.kwargs["json"]
                assert payload["sampler"] == expected_sampler

    @pytest.mark.asyncio
    async def test_generate_with_size_boundaries(
        self, sample_style: StyleAnalysis, mock_response_data: dict
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        sizes = [(64, 64), (512, 512), (1024, 1024), (2048, 2048)]

        for width, height in sizes:
            params = GenerationParams(style="test", width=width, height=height, seed=42)

            with patch("aiohttp.ClientSession.post") as mock_post:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value=mock_response_data)
                mock_response.raise_for_status = AsyncMock()
                mock_post.return_value.__aenter__.return_value = mock_response

                await provider.generate_pattern(sample_style, params)

                payload = mock_post.call_args.kwargs["json"]
                assert payload["width"] == width
                assert payload["height"] == height

    @pytest.mark.asyncio
    async def test_generate_rate_limit_error(
        self, sample_style: StyleAnalysis, sample_params: GenerationParams
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ProviderRateLimitError, match="Rate limit exceeded"):
                await provider.generate_pattern(sample_style, sample_params)

    @pytest.mark.asyncio
    async def test_generate_content_policy_error(
        self, sample_style: StyleAnalysis, sample_params: GenerationParams
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.json = AsyncMock(
                return_value={"message": "Content policy violation detected"}
            )
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ProviderContentPolicyError, match="Content policy violation"):
                await provider.generate_pattern(sample_style, sample_params)

    @pytest.mark.asyncio
    async def test_generate_timeout_error(
        self, sample_style: StyleAnalysis, sample_params: GenerationParams
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        with patch("aiohttp.ClientSession.post") as mock_post:

            mock_post.side_effect = TimeoutError("Timeout")

            with pytest.raises(ProviderTimeoutError, match="timed out"):
                await provider.generate_pattern(sample_style, sample_params)

    @pytest.mark.asyncio
    async def test_generate_no_artifacts_error(
        self, sample_style: StyleAnalysis, sample_params: GenerationParams
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"artifacts": []})
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ProviderError, match="No artifacts"):
                await provider.generate_pattern(sample_style, sample_params)

    @pytest.mark.asyncio
    async def test_generate_no_base64_error(
        self, sample_style: StyleAnalysis, sample_params: GenerationParams
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={"artifacts": [{"finishReason": "SUCCESS"}]}
            )
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(ProviderError, match="No base64 data"):
                await provider.generate_pattern(sample_style, sample_params)

    @pytest.mark.asyncio
    async def test_prompt_building_with_seamless_pattern(self, mock_response_data: dict) -> None:
        provider = StabilityProvider(api_key="test-key")

        style = StyleAnalysis(
            style_description="Floral design",
            color_palette=["#FF0000", "#00FF00", "#0000FF"],
            pattern_type="seamless",
            suggested_params={},
        )
        params = GenerationParams(style="floral", width=512, height=512, seed=42)

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value.__aenter__.return_value = mock_response

            await provider.generate_pattern(style, params)

            payload = mock_post.call_args.kwargs["json"]
            prompt = payload["text_prompts"][0]["text"]
            assert "Floral design" in prompt
            assert "seamless" in prompt
            assert "#FF0000" in prompt or "FF0000" in prompt

    @pytest.mark.asyncio
    async def test_seed_reproducibility(
        self, sample_style: StyleAnalysis, mock_response_data: dict
    ) -> None:
        provider = StabilityProvider(api_key="test-key")

        params = GenerationParams(style="test", width=512, height=512, seed=12345)

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_response.raise_for_status = AsyncMock()
            mock_post.return_value.__aenter__.return_value = mock_response

            await provider.generate_pattern(sample_style, params)

            payload = mock_post.call_args.kwargs["json"]
            assert payload["seed"] == 12345


class TestNotImplementedMethods:
    @pytest.mark.asyncio
    async def test_analyze_style_not_implemented(self) -> None:
        provider = StabilityProvider(api_key="test-key")
        with pytest.raises(NotImplementedError, match="does not support style analysis"):
            await provider.analyze_style(b"fake-image")

    @pytest.mark.asyncio
    async def test_upscale_not_implemented(self) -> None:
        provider = StabilityProvider(api_key="test-key")
        with pytest.raises(NotImplementedError, match="Task 13"):
            await provider.upscale_image(b"fake-image", 1024)

    @pytest.mark.asyncio
    async def test_vectorize_not_implemented(self) -> None:
        provider = StabilityProvider(api_key="test-key")
        with pytest.raises(NotImplementedError, match="does not support vectorization"):
            await provider.vectorize(b"fake-image")

    @pytest.mark.asyncio
    async def test_composite_not_implemented(self) -> None:
        provider = StabilityProvider(api_key="test-key")
        from ai.schemas import Position

        position = Position(x=0, y=0, scale=1.0, rotation=0, opacity=1.0)
        with pytest.raises(NotImplementedError, match="does not support compositing"):
            await provider.composite_mockup(b"pattern", b"template", position)
