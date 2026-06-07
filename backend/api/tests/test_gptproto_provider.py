import base64
from typing import Any

import aiohttp
import pytest

from shared.ai.exceptions import ProviderError
from shared.ai.schemas import GenerationParams, StyleAnalysis
from shared.providers.gptproto import GPTProtoProvider


class RecordingGPTProtoProvider(GPTProtoProvider):
    def __init__(
        self,
        *,
        base_url: str = "https://gptproto.com/api/v3",
        model: str = "gpt-image-2",
    ) -> None:
        super().__init__(
            api_key="test-key",
            base_url=base_url,
            model=model,
        )
        self.requests: list[tuple[str, dict[str, Any], bool]] = []
        self.polled_response: dict[str, Any] | None = None

    async def _make_request(
        self, url: str, payload: dict[str, Any], *, bearer_auth: bool = False
    ) -> bytes:
        self.requests.append((url, payload, bearer_auth))
        return b"image-bytes"

    async def _poll_for_result(
        self,
        session: aiohttp.ClientSession,
        response_data: dict[str, Any],
        headers: dict[str, str],
    ) -> bytes:
        self.polled_response = response_data
        return b"polled-image-bytes"


@pytest.fixture
def style() -> StyleAnalysis:
    return StyleAnalysis(
        style_description="watercolor floral textile",
        color_palette=["#112233", "#445566"],
        pattern_type="seamless",
    )


@pytest.fixture
def provider() -> RecordingGPTProtoProvider:
    return RecordingGPTProtoProvider()


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (1024, 1024, "1024x1024"),
        (1536, 1024, "1536x1024"),
        (2048, 1152, "2048x1152"),
        (3840, 3840, "2880x2880"),
        (512, 512, "816x816"),
        (1000, 1000, "992x992"),
    ],
)
def test_gpt_image_size_uses_valid_pixel_dimensions(
    provider: RecordingGPTProtoProvider, width: int, height: int, expected: str
) -> None:
    assert provider._get_gpt_image_size(width, height) == expected


async def test_gpt_image_text2img_uses_openai_generation_endpoint(
    provider: RecordingGPTProtoProvider, style: StyleAnalysis
) -> None:
    result = await provider.generate_pattern(
        style,
        GenerationParams(style="floral", width=1024, height=1024),
    )

    assert result == b"image-bytes"
    url, payload, bearer_auth = provider.requests[0]
    assert url == "https://gptproto.com/v1/images/generations"
    assert bearer_auth is True
    assert payload["model"] == "gpt-image-2"
    assert payload["size"] == "1024x1024"
    assert payload["quality"] == "high"
    assert payload["output_format"] == "png"
    assert payload["response_format"] == "b64_json"


async def test_gpt_image_text2img_keeps_configured_v1_base_url(style: StyleAnalysis) -> None:
    provider = RecordingGPTProtoProvider(base_url="https://gptproto.com/v1")

    await provider.generate_pattern(
        style,
        GenerationParams(style="floral", width=1024, height=1024),
    )

    url, _, _ = provider.requests[0]
    assert url == "https://gptproto.com/v1/images/generations"


async def test_gpt_image_img2img_uses_gptproto_format_image_edit_endpoint(
    provider: RecordingGPTProtoProvider, style: StyleAnalysis
) -> None:
    result = await provider.generate_pattern(
        style,
        GenerationParams(
            style="floral",
            width=1536,
            height=1024,
            init_image_b64="YWJj",
        ),
    )

    assert result == b"image-bytes"
    url, payload, bearer_auth = provider.requests[0]
    assert url == "https://gptproto.com/api/v3/openai/gpt-image-2/image-edit"
    assert bearer_auth is False
    assert payload["base64_images"] == ["data:image/png;base64,YWJj"]
    assert payload["size"] == "1536x1024"
    assert payload["quality"] == "high"
    assert payload["response_format"] == "b64_json"
    assert payload["enable_sync_mode"] is True


async def test_gpt_image_img2img_sends_url_inputs_as_images(
    provider: RecordingGPTProtoProvider, style: StyleAnalysis
) -> None:
    await provider.generate_pattern(
        style,
        GenerationParams(
            style="floral",
            width=1024,
            height=1024,
            init_image_b64="https://example.com/source.png",
        ),
    )

    _, payload, _ = provider.requests[0]
    assert payload["images"] == ["https://example.com/source.png"]
    assert "base64_images" not in payload


async def test_gpt_image_img2img_converts_v1_base_url_to_gptproto_format_edit(
    style: StyleAnalysis,
) -> None:
    provider = RecordingGPTProtoProvider(base_url="https://gptproto.com/v1")

    await provider.generate_pattern(
        style,
        GenerationParams(style="floral", init_image_b64="YWJj"),
    )

    url, _, _ = provider.requests[0]
    assert url == "https://gptproto.com/api/v3/openai/gpt-image-2/image-edit"


async def test_non_gpt_image_model_still_uses_gemini_route(style: StyleAnalysis) -> None:
    provider = RecordingGPTProtoProvider(model="google/gemini-3.1-flash-image-preview")

    await provider.generate_pattern(
        style,
        GenerationParams(style="floral", width=1024, height=1024),
    )

    url, payload, bearer_auth = provider.requests[0]
    assert url == "https://gptproto.com/api/v3/google/gemini-3.1-flash-image-preview/text-to-image"
    assert bearer_auth is False
    assert payload["size"] == "1K"
    assert payload["aspect_ratio"] == "1:1"


async def test_extract_image_from_outputs_accepts_b64_json(
    provider: RecordingGPTProtoProvider,
) -> None:
    async with aiohttp.ClientSession() as session:
        image = await provider._extract_image_from_outputs(
            session=session,
            outputs=[{"b64_json": base64.b64encode(b"png-bytes").decode()}],
        )

    assert image == b"png-bytes"


async def test_extract_image_from_outputs_accepts_data_uri(
    provider: RecordingGPTProtoProvider,
) -> None:
    data_uri = f"data:image/png;base64,{base64.b64encode(b'png-bytes').decode()}"

    async with aiohttp.ClientSession() as session:
        image = await provider._extract_image_from_outputs(
            session=session,
            outputs=[data_uri],
        )

    assert image == b"png-bytes"


async def test_process_response_extracts_succeeded_prediction_outputs(
    provider: RecordingGPTProtoProvider,
) -> None:
    async with aiohttp.ClientSession() as session:
        image = await provider._process_response(
            session,
            {
                "data": {
                    "status": "succeeded",
                    "outputs": [{"b64_json": base64.b64encode(b"png-bytes").decode()}],
                }
            },
            headers={"Authorization": "test-key"},
        )

    assert image == b"png-bytes"


async def test_process_response_polls_pending_prediction(
    provider: RecordingGPTProtoProvider,
) -> None:
    response_data = {
        "id": "pred-1",
        "status": "processing",
        "urls": {"get": "https://gptproto.com/api/v3/predictions/pred-1/result"},
    }

    async with aiohttp.ClientSession() as session:
        image = await provider._process_response(
            session,
            {"data": response_data},
            headers={"Authorization": "test-key"},
        )

    assert image == b"polled-image-bytes"
    assert provider.polled_response == response_data


async def test_process_response_raises_failed_prediction(
    provider: RecordingGPTProtoProvider,
) -> None:
    async with aiohttp.ClientSession() as session:
        with pytest.raises(ProviderError, match="Generation failed: bad prompt"):
            await provider._process_response(
                session,
                {"data": {"status": "failed", "error": "bad prompt"}},
                headers={"Authorization": "test-key"},
            )
