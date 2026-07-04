from io import BytesIO

from PIL import Image

from worker.handlers.tile_upscale import (
    MAX_TILE_MODEL_INPUT_SIZE,
    MAX_TILE_TARGET_RATIO,
    MIN_TILE_INPUT_FOR_SINGLE_PASS,
    MIN_TILE_TARGET_SIZE,
    STAGE_UPSCALE_FACTOR,
    tile_upscale,
)


def _png(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color=(24, 48, 96))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _image_size(image_bytes: bytes) -> tuple[int, int]:
    return Image.open(BytesIO(image_bytes)).size


async def test_tile_upscale_keeps_each_model_call_within_single_pass_ratio() -> None:
    requested_targets: list[int] = []
    model_input_sizes: list[tuple[int, int]] = []

    async def fake_upscale(tile_bytes: bytes, tile_target: int) -> bytes:
        requested_targets.append(tile_target)
        tile = Image.open(BytesIO(tile_bytes)).convert("RGB")
        model_input_sizes.append(tile.size)
        ratio = tile_target / max(tile.size)
        upscaled = tile.resize(
            (int(tile.width * ratio), int(tile.height * ratio)),
            Image.Resampling.BICUBIC,
        )
        output = BytesIO()
        upscaled.save(output, format="PNG")
        return output.getvalue()

    result = await tile_upscale(
        _png(512, 512),
        target_size=2048,
        upscale_fn=fake_upscale,
        tile_size=512,
        pad=64,
        delay_between_tiles=0,
    )

    assert _image_size(result) == (2048, 2048)
    assert requested_targets
    assert all(
        target <= int(max(size) * MAX_TILE_TARGET_RATIO)
        for target, size in zip(requested_targets, model_input_sizes, strict=True)
    )


async def test_tile_upscale_runs_repeated_2x_stages_for_8x_target() -> None:
    model_input_sizes: list[tuple[int, int]] = []

    async def fake_upscale(tile_bytes: bytes, tile_target: int) -> bytes:
        tile = Image.open(BytesIO(tile_bytes)).convert("RGB")
        model_input_sizes.append(tile.size)
        ratio = tile_target / max(tile.size)
        upscaled = tile.resize(
            (int(tile.width * ratio), int(tile.height * ratio)),
            Image.Resampling.BICUBIC,
        )
        output = BytesIO()
        upscaled.save(output, format="PNG")
        return output.getvalue()

    result = await tile_upscale(
        _png(512, 512),
        target_size=512 * STAGE_UPSCALE_FACTOR**3,
        upscale_fn=fake_upscale,
        tile_size=512,
        pad=0,
        delay_between_tiles=0,
    )

    assert _image_size(result) == (4096, 4096)
    # 512 -> 4096 is exactly 8x, so the pipeline should be three 2x stages:
    # direct 512 -> 1024, then 2x2 tiles for 1024 -> 2048, then 4x4 tiles for
    # 2048 -> 4096.
    assert len(model_input_sizes) == 1 + 4 + 16
    assert all(max(size) <= MAX_TILE_MODEL_INPUT_SIZE for size in model_input_sizes)


async def test_tile_upscale_caps_large_model_inputs_for_replicate_output_limit() -> None:
    requested_targets: list[int] = []
    model_input_sizes: list[tuple[int, int]] = []

    async def fake_upscale(tile_bytes: bytes, tile_target: int) -> bytes:
        requested_targets.append(tile_target)
        tile = Image.open(BytesIO(tile_bytes)).convert("RGB")
        model_input_sizes.append(tile.size)
        ratio = tile_target / max(tile.size)
        upscaled = tile.resize(
            (int(tile.width * ratio), int(tile.height * ratio)),
            Image.Resampling.BICUBIC,
        )
        output = BytesIO()
        upscaled.save(output, format="PNG")
        return output.getvalue()

    result = await tile_upscale(
        _png(1200, 1200),
        target_size=2400,
        upscale_fn=fake_upscale,
        tile_size=1024,
        pad=64,
        delay_between_tiles=0,
    )

    assert model_input_sizes
    assert _image_size(result) == (2400, 2400)
    assert all(max(size) <= MAX_TILE_MODEL_INPUT_SIZE for size in model_input_sizes)
    assert all(
        target <= int(max(size) * MAX_TILE_TARGET_RATIO)
        for target, size in zip(requested_targets, model_input_sizes, strict=True)
    )


async def test_tile_upscale_expands_small_inputs_for_replicate_target_floor() -> None:
    requested_targets: list[int] = []
    model_input_sizes: list[tuple[int, int]] = []

    async def fake_upscale(tile_bytes: bytes, tile_target: int) -> bytes:
        requested_targets.append(tile_target)
        tile = Image.open(BytesIO(tile_bytes)).convert("RGB")
        model_input_sizes.append(tile.size)
        ratio = tile_target / max(tile.size)
        upscaled = tile.resize(
            (int(tile.width * ratio), int(tile.height * ratio)),
            Image.Resampling.BICUBIC,
        )
        output = BytesIO()
        upscaled.save(output, format="PNG")
        return output.getvalue()

    result = await tile_upscale(
        _png(300, 300),
        target_size=600,
        upscale_fn=fake_upscale,
        tile_size=1024,
        pad=64,
        delay_between_tiles=0,
    )

    assert _image_size(result) == (600, 600)
    small_tile_indexes = [
        index
        for index, size in enumerate(model_input_sizes)
        if max(size) == MIN_TILE_INPUT_FOR_SINGLE_PASS
    ]
    assert small_tile_indexes
    assert all(requested_targets[index] >= MIN_TILE_TARGET_SIZE for index in small_tile_indexes)
    assert all(
        requested_targets[index]
        <= int(MIN_TILE_INPUT_FOR_SINGLE_PASS * MAX_TILE_TARGET_RATIO)
        for index in small_tile_indexes
    )
