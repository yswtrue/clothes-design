import pytest

from shared.providers.openai_image import OpenAIImageProvider


@pytest.fixture
def provider() -> OpenAIImageProvider:
    return OpenAIImageProvider(api_key="test-key", model="gpt-image-2")


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (1024, 1024, "1024x1024"),
        (1536, 1024, "1536x1024"),
        (1024, 1536, "1024x1536"),
        (2048, 1152, "2048x1152"),
    ],
)
def test_image_edit_size_uses_pixel_dimensions(
    provider: OpenAIImageProvider, width: int, height: int, expected: str
) -> None:
    assert provider._get_image_edit_size(width, height) == expected


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (1000, 1000, "992x992"),
        (63, 2050, "64x2048"),
    ],
)
def test_image_edit_size_normalizes_to_provider_bounds_and_multiple(
    provider: OpenAIImageProvider, width: int, height: int, expected: str
) -> None:
    assert provider._get_image_edit_size(width, height) == expected


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (1024, 1024, "1:1"),
        (1536, 1024, "3:2"),
        (2048, 1152, "16:9"),
        (1000, 1000, "1:1"),
        (63, 2050, "1:8"),
    ],
)
def test_gptproto_gemini_image_edit_size_uses_supported_aspect_ratio(
    width: int, height: int, expected: str
) -> None:
    provider = OpenAIImageProvider(
        api_key="test-key",
        base_url="https://gptproto.com/v1",
        model="gemini-3-pro-image-preview",
    )

    assert provider._get_image_edit_size(width, height) == expected


def test_gemini_image_edit_size_uses_aspect_ratio_for_custom_base_url() -> None:
    provider = OpenAIImageProvider(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="google/gemini-3-pro-image-preview",
    )

    assert provider._get_image_edit_size(1200, 900) == "4:3"


def test_gpt_image_edit_size_uses_pixel_dimensions_for_gptproto_base_url() -> None:
    provider = OpenAIImageProvider(
        api_key="test-key",
        base_url="https://gptproto.com/v1",
        model="gpt-image-2",
    )

    assert provider._get_image_edit_size(1024, 1024) == "1024x1024"
