from io import BytesIO

from PIL import Image

from worker.handlers.tile_upscale import (
    MAX_TILE_MODEL_INPUT_SIZE,
    MAX_TILE_TARGET_RATIO,
    MIN_TILE_INPUT_FOR_SINGLE_PASS,
    MIN_TILE_TARGET_SIZE,
    tile_upscale,
)


def _png(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color=(24, 48, 96))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


async def test_tile_upscale_caps_tile_target_to_single_model_pass() -> None:
    requested_targets: list[int] = []

    async def fake_upscale(tile_bytes: bytes, tile_target: int) -> bytes:
        requested_targets.append(tile_target)
        tile = Image.open(BytesIO(tile_bytes)).convert("RGB")
        ratio = tile_target / max(tile.size)
        upscaled = tile.resize(
            (int(tile.width * ratio), int(tile.height * ratio)),
            Image.Resampling.BICUBIC,
        )
        output = BytesIO()
        upscaled.save(output, format="PNG")
        return output.getvalue()

    await tile_upscale(
        _png(512, 512),
        target_size=2048,
        upscale_fn=fake_upscale,
        tile_size=512,
        pad=64,
        delay_between_tiles=0,
    )

    assert requested_targets == [int(512 * MAX_TILE_TARGET_RATIO)]


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

    await tile_upscale(
        _png(1200, 1200),
        target_size=2400,
        upscale_fn=fake_upscale,
        tile_size=1024,
        pad=64,
        delay_between_tiles=0,
    )

    assert model_input_sizes
    assert all(max(size) <= MAX_TILE_MODEL_INPUT_SIZE for size in model_input_sizes)
    assert any(max(size) == MAX_TILE_MODEL_INPUT_SIZE for size in model_input_sizes)
    assert all(
        target <= int(MAX_TILE_MODEL_INPUT_SIZE * MAX_TILE_TARGET_RATIO)
        for target in requested_targets
    )


async def test_tile_upscale_expands_small_edge_tiles_for_replicate_target_floor() -> None:
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

    await tile_upscale(
        _png(1100, 1100),
        target_size=2200,
        upscale_fn=fake_upscale,
        tile_size=1024,
        pad=64,
        delay_between_tiles=0,
    )

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
