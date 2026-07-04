import asyncio
import base64
import socket
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pytest
from aiohttp import web
from PIL import Image
from replicate.exceptions import ReplicateError

import shared.providers.replicate as replicate_module
from shared.ai.exceptions import ProviderRateLimitError, ProviderTimeoutError
from shared.ai.schemas import GenerationParams, StyleAnalysis
from shared.providers.replicate import (
    ESRGAN_MODEL,
    SDXL_IMG2IMG_MODEL,
    ReplicateProvider,
)


@dataclass
class StubProviderConfig:
    api_key: str
    base_url: str
    model_name: str
    config: dict[str, Any] | None


class StubReplicateClient:
    def __init__(
        self,
        output: Any = b"replicate-output",
        delay: float = 0,
        error: Exception | None = None,
    ) -> None:
        self.output = output
        self.delay = delay
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def async_run(
        self,
        model: str,
        *,
        input: dict[str, Any] | None = None,  # noqa: A002 - matches Replicate SDK signature
        use_file_output: bool = True,
    ) -> Any:
        call_input = input or {}
        image_file = call_input.get("image")
        image_bytes = None
        if image_file is not None and hasattr(image_file, "read"):
            image_bytes = image_file.read()
        if image_file is not None and hasattr(image_file, "seek"):
            image_file.seek(0)

        self.calls.append(
            {
                "model": model,
                "input": call_input,
                "use_file_output": use_file_output,
                "image_bytes": image_bytes,
                "image_closed_during_call": getattr(image_file, "closed", None),
            }
        )

        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.output


class AsyncFileOutput:
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def aread(self) -> bytes:
        return self.data


def make_png(width: int = 64, height: int = 64) -> bytes:
    image = Image.new("RGB", (width, height), color=(10, 20, 30))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def test_run_prediction_uses_official_sdk_client(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ReplicateProvider(
        api_token="test-key",
        base_url="https://replicate.example/v1",
        timeout=1,
    )
    client = StubReplicateClient(output=AsyncFileOutput(b"image-bytes"))
    monkeypatch.setattr(provider, "_client", client)

    output = await provider._run_prediction("owner/model:version", {"prompt": "hello"})
    image_bytes = await provider._replicate_output_to_bytes(output)

    assert image_bytes == b"image-bytes"
    assert client.calls == [
        {
            "model": "owner/model:version",
            "input": {"prompt": "hello"},
            "use_file_output": True,
            "image_bytes": None,
            "image_closed_during_call": None,
        }
    ]


async def test_run_prediction_uses_wall_clock_overall_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ReplicateProvider(
        api_token="test-key",
        base_url="https://replicate.example/v1",
        timeout=1,
    )
    client = StubReplicateClient(delay=2)
    monkeypatch.setattr(provider, "_client", client)

    started = time.monotonic()
    with pytest.raises(ProviderTimeoutError):
        await provider._run_prediction("test/model:version", {})
    elapsed = time.monotonic() - started

    assert len(client.calls) == 1
    assert elapsed < 1.5


async def test_run_prediction_maps_rate_limit_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ReplicateProvider(
        api_token="test-key",
        base_url="https://replicate.example/v1",
        timeout=1,
    )
    client = StubReplicateClient(error=ReplicateError(status=429, detail="too many requests"))
    monkeypatch.setattr(provider, "_client", client)

    with pytest.raises(ProviderRateLimitError):
        await provider._run_prediction("test/model:version", {})


async def test_upscale_image_passes_file_input_to_official_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ReplicateProvider(
        api_token="test-key",
        base_url="https://replicate.example/v1",
        timeout=1,
    )
    client = StubReplicateClient(output=AsyncFileOutput(make_png(width=1200, height=1200)))
    monkeypatch.setattr(provider, "_client", client)

    image_bytes = make_png(width=512, height=512)
    upscaled = await provider.upscale_image(image_bytes, target_size=1200)

    assert Image.open(BytesIO(upscaled)).size == (1200, 1200)
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == ESRGAN_MODEL
    assert call["input"]["scale"] == 2
    assert call["input"]["face_enhance"] is False
    assert call["image_bytes"] == image_bytes
    assert call["image_closed_during_call"] is False
    assert not isinstance(call["input"]["image"], str)


async def test_line_art_upscale_uses_stable_esrgan_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ReplicateProvider(
        api_token="test-key",
        base_url="https://replicate.example/v1",
        timeout=1,
    )
    client = StubReplicateClient(output=AsyncFileOutput(make_png(width=1200, height=1200)))
    monkeypatch.setattr(provider, "_client", client)

    image_bytes = make_png(width=512, height=512)
    upscaled = await provider.upscale_image(
        image_bytes,
        target_size=1200,
        content_type="line-art",
    )

    assert Image.open(BytesIO(upscaled)).size == (1200, 1200)
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == ESRGAN_MODEL
    assert "image" in call["input"]
    assert "img" not in call["input"]
    assert call["image_bytes"] == image_bytes


async def test_img2img_passes_decoded_file_input_to_official_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ReplicateProvider(
        api_token="test-key",
        base_url="https://replicate.example/v1",
        timeout=1,
    )
    client = StubReplicateClient(output=[AsyncFileOutput(b"generated-bytes")])
    monkeypatch.setattr(provider, "_client", client)
    image_bytes = make_png()

    generated = await provider.generate_pattern(
        StyleAnalysis(
            style_description="minimal geometric",
            color_palette=["#000000"],
            pattern_type="seamless",
        ),
        GenerationParams(
            style="test",
            init_image_b64="data:image/png;base64,"
            + base64.b64encode(image_bytes).decode("utf-8"),
        ),
    )

    assert generated == b"generated-bytes"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == SDXL_IMG2IMG_MODEL
    assert call["image_bytes"] == image_bytes
    assert not isinstance(call["input"]["image"], str)


async def test_download_image_uses_provider_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(replicate_module, "IMAGE_DOWNLOAD_TIMEOUT", 0.01)

    download_count = 0

    async def download_image(request: web.Request) -> web.Response:
        nonlocal download_count
        download_count += 1
        await asyncio.sleep(0.05)
        return web.Response(body=b"image-bytes", content_type="image/png")

    app = web.Application()
    app.router.add_get("/upscaled.png", download_image)

    runner = web.AppRunner(app)
    await runner.setup()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(128)
    site = web.SockSite(runner, server_socket)
    await site.start()

    try:
        host, port = server_socket.getsockname()[:2]
        provider = ReplicateProvider(
            api_token="test-key",
            base_url="https://replicate.example/v1",
            timeout=1,
        )

        image_bytes = await provider._download_image(f"http://{host}:{port}/upscaled.png")
    finally:
        await runner.cleanup()

    assert image_bytes == b"image-bytes"
    assert download_count == 1


def test_from_config_uses_timeout_and_retry_settings() -> None:
    provider = ReplicateProvider.from_config(
        StubProviderConfig(
            api_key="test-key",
            base_url="https://replicate.example/v1",
            model_name="flux",
            config={"timeout": "300", "max_retries": "5"},
        )
    )

    assert provider.timeout == 300
    assert provider.max_retries == 5


def test_from_config_ignores_blank_model_name() -> None:
    provider = ReplicateProvider.from_config(
        StubProviderConfig(
            api_key="test-key",
            base_url="https://replicate.example/v1/",
            model_name=" ",
            config=None,
        )
    )

    assert provider.generation_model == replicate_module.FLUX_MODEL
    assert provider.base_url == "https://replicate.example/v1"
    assert provider.sdk_base_url == "https://replicate.example"


def test_sdk_base_url_strips_legacy_v1_suffix() -> None:
    provider = ReplicateProvider(
        api_token="test-key",
        base_url="https://api.replicate.com/v1/",
    )

    assert provider.base_url == "https://api.replicate.com/v1"
    assert provider.sdk_base_url == "https://api.replicate.com"
    assert provider._client.__dict__["_base_url"] == "https://api.replicate.com"
