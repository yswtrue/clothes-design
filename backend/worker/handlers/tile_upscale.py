"""Tile-based image upscaling to bypass GPU memory limits.

Splits large images into overlapping tiles, upscales each tile via the
AI upscaler, then stitches them back into a single high-resolution image.
"""

import asyncio
import io
import logging
import math
import time
from dataclasses import dataclass, field

from PIL import Image, ImageFilter, ImageStat

from shared.ai.exceptions import ProviderRateLimitError

logger = logging.getLogger(__name__)

# GPU-safe tile size — ESRGAN on Replicate handles up to ~2M pixels per tile
TILE_SIZE = 1024
TILE_PAD = 64  # overlap padding to avoid seam artifacts
# Replicate free tier: 6 requests/min, burst=1 → ~12s between tiles safely
TILE_DELAY_SECONDS = 12.0
# Keep each Replicate request to a single 2x-ish pass. Larger exports are built
# as multiple full-image stages so every stage can decide whether to tile again.
MAX_TILE_TARGET_RATIO = 2.5
# Keep Replicate model outputs under roughly 2M pixels. Real-ESRGAN returns a
# fixed 2x output, so a 704px square input becomes 1408px square (~1.98M px).
MAX_TILE_MODEL_INPUT_SIZE = 704
MIN_TILE_TARGET_SIZE = 1024
MIN_TILE_INPUT_FOR_SINGLE_PASS = math.ceil(MIN_TILE_TARGET_SIZE / MAX_TILE_TARGET_RATIO)
# Rate limit retry
MAX_RATE_LIMIT_RETRIES = 5
STAGE_UPSCALE_FACTOR = 2
UNIFORM_TILE_CHANNEL_DELTA = 8
BLANK_TILE_WHITE_MIN = 235
BLANK_TILE_BLACK_MAX = 10
BLANK_TILE_WHITE_CONTENT_MAX = 248
BLANK_TILE_BLACK_CONTENT_MIN = 7
BLANK_TILE_NOISE_MAX_RATIO = 0.20

UPSCALE_MODE_PROGRESSIVE = "progressive"
UPSCALE_MODE_ONESHOT = "oneshot"


@dataclass
class UpscaleStats:
    """Accumulated statistics for a single tile_upscale run."""

    total_tiles: int = 0
    api_calls: int = 0
    local_calls: int = 0
    start_time: float = field(default_factory=time.monotonic)

    def log_summary(self, logger_obj: logging.Logger, prefix: str = "") -> None:
        elapsed = time.monotonic() - self.start_time
        label = f"{prefix} " if prefix else ""
        logger_obj.info(
            f"{label}Upscale summary: {self.total_tiles} tiles total, "
            f"{self.api_calls} API calls, {self.local_calls} local resizes, "
            f"elapsed {elapsed:.1f}s"
        )


@dataclass
class _TileMeta:
    """Metadata for a single tile in the tiling grid."""

    x: int  # source x in pixels
    y: int  # source y in pixels
    w: int  # actual width of the tile core (without pad)
    h: int  # actual height of the tile core (without pad)
    pad_left: int
    pad_top: int
    pad_right: int
    pad_bottom: int
    scale: int  # upscale factor


def _grid_tiles(img_w: int, img_h: int, tile_size: int, pad: int) -> list[_TileMeta]:
    """Divide the image into a grid of overlapping tiles."""
    tiles: list[_TileMeta] = []
    cols = (img_w + tile_size - 1) // tile_size
    rows = (img_h + tile_size - 1) // tile_size

    for row in range(rows):
        for col in range(cols):
            x = col * tile_size
            y = row * tile_size
            w = min(tile_size, img_w - x)
            h = min(tile_size, img_h - y)

            tiles.append(
                _TileMeta(
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    pad_left=min(pad, x),
                    pad_top=min(pad, y),
                    pad_right=min(pad, img_w - x - w),
                    pad_bottom=min(pad, img_h - y - h),
                    scale=0,  # filled later
                )
            )
    return tiles


async def _upscale_with_retry(
    upscale_fn,
    tile_bytes: bytes,
    tile_target: int,
    tile_idx: int,
    total_tiles: int,
    delay: float,
    tile_label: str,
) -> bytes:
    """Upscale a single tile with rate-limit retry logic."""
    for retry in range(MAX_RATE_LIMIT_RETRIES):
        try:
            if retry == 0:
                logger.info(f"{tile_label} Replicate request start: target {tile_target}px")
            else:
                logger.info(
                    f"{tile_label} Replicate request retry {retry + 1}/{MAX_RATE_LIMIT_RETRIES}: "
                    f"target {tile_target}px"
                )
            result = await upscale_fn(tile_bytes, tile_target)
            logger.info(f"{tile_label} Replicate request complete: {len(result)} bytes")
            return result
        except ProviderRateLimitError:
            if retry == MAX_RATE_LIMIT_RETRIES - 1:
                raise
            wait = delay * (retry + 1)
            logger.warning(
                f"{tile_label} rate limited ({tile_idx + 1}/{total_tiles}), "
                f"retry {retry + 1}/{MAX_RATE_LIMIT_RETRIES} in {wait:.0f}s"
            )
            await asyncio.sleep(wait)
    # This line is unreachable but keeps type checkers happy
    raise ProviderRateLimitError("Max rate-limit retries exceeded")


def _image_to_png(img: Image.Image) -> bytes:
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def _resize_longest(img: Image.Image, longest: int) -> Image.Image:
    current_longest = max(img.width, img.height)
    if current_longest == longest:
        return img
    ratio = longest / current_longest
    return img.resize(
        (
            max(1, round(img.width * ratio)),
            max(1, round(img.height * ratio)),
        ),
        Image.Resampling.BICUBIC,
    )


def _is_uniform_image(img: Image.Image) -> bool:
    """Return true when an image is blank, solid, or visually near-solid."""
    rgb_img = img.convert("RGB")
    stat = ImageStat.Stat(rgb_img)
    channel_ranges = [
        channel_max - channel_min <= UNIFORM_TILE_CHANNEL_DELTA
        for channel_min, channel_max in stat.extrema
    ]
    if all(channel_ranges):
        return True

    # Production assets often contain compression/antialiasing noise that is
    # visually blank but not strictly uniform. Treat near-white and near-black
    # tiles as blank only when visibly non-blank pixels are sparse, so faint but
    # structured artwork does not get skipped just because it is close to white
    # or black.
    pixel_count = max(1, rgb_img.width * rgb_img.height)
    if all(channel_min >= BLANK_TILE_WHITE_MIN for channel_min, _ in stat.extrema):
        pixels = rgb_img.tobytes()
        non_blank_pixels = sum(
            1
            for index in range(0, len(pixels), 3)
            if min(pixels[index : index + 3]) < BLANK_TILE_WHITE_CONTENT_MAX
        )
        return non_blank_pixels / pixel_count <= BLANK_TILE_NOISE_MAX_RATIO

    if all(channel_max <= BLANK_TILE_BLACK_MAX for _, channel_max in stat.extrema):
        pixels = rgb_img.tobytes()
        non_blank_pixels = sum(
            1
            for index in range(0, len(pixels), 3)
            if max(pixels[index : index + 3]) > BLANK_TILE_BLACK_CONTENT_MIN
        )
        return non_blank_pixels / pixel_count <= BLANK_TILE_NOISE_MAX_RATIO

    return False


def _prepare_model_input(img: Image.Image, target_size: int) -> tuple[Image.Image, int]:
    """Return model-safe input image and target size for one Replicate call."""
    tile_longest = max(img.width, img.height)
    model_img = img

    if tile_longest > MAX_TILE_MODEL_INPUT_SIZE:
        model_img = _resize_longest(img, MAX_TILE_MODEL_INPUT_SIZE)
    elif tile_longest < MIN_TILE_INPUT_FOR_SINGLE_PASS:
        model_img = _resize_longest(img, MIN_TILE_INPUT_FOR_SINGLE_PASS)

    model_longest = max(model_img.width, model_img.height)
    model_target = max(MIN_TILE_TARGET_SIZE, target_size)
    model_target = min(model_target, int(model_longest * MAX_TILE_TARGET_RATIO))
    return model_img, model_target


async def _upscale_direct_stage(
    img: Image.Image,
    stage_target_size: int,
    stage_index: int,
    total_stages: int,
    upscale_fn,
    delay_between_tiles: float,
    stats: UpscaleStats,
) -> Image.Image:
    """Upscale a stage with one model call when the image is already model-safe."""
    stats.total_tiles += 1
    if _is_uniform_image(img):
        stats.local_calls += 1
        logger.info(
            f"Stage {stage_index}/{total_stages} image 1/1 uniform direct: "
            f"{img.width}x{img.height} -> longest {stage_target_size}px locally"
        )
        return _resize_longest(img, stage_target_size)

    stats.api_calls += 1
    model_img, model_target = _prepare_model_input(img, stage_target_size)
    logger.info(
        f"Stage {stage_index}/{total_stages} image 1/1 direct model: "
        f"{img.width}x{img.height} -> {model_img.width}x{model_img.height} "
        f"-> {model_target}px"
    )
    upscaled_bytes = await _upscale_with_retry(
        upscale_fn,
        _image_to_png(model_img),
        model_target,
        0,
        1,
        delay_between_tiles,
        f"Stage {stage_index}/{total_stages} image 1/1 direct model",
    )
    upscaled = Image.open(io.BytesIO(upscaled_bytes)).convert("RGB")
    return _resize_longest(upscaled, stage_target_size)


async def _upscale_tiled_stage(
    img: Image.Image,
    stage_target_size: int,
    stage_index: int,
    total_stages: int,
    upscale_fn,
    tile_size: int,
    pad: int,
    delay_between_tiles: float,
    stats: UpscaleStats,
) -> Image.Image:
    """Upscale one stage by tiling the current image, then stitching it."""
    src_w, src_h = img.size
    src_longest = max(src_w, src_h)
    stage_ratio = stage_target_size / src_longest
    canvas_w = max(1, round(src_w * stage_ratio))
    canvas_h = max(1, round(src_h * stage_ratio))
    canvas = Image.new("RGB", (canvas_w, canvas_h))

    effective_tile_size = min(tile_size, max(1, MAX_TILE_MODEL_INPUT_SIZE - (pad * 2)))
    tiles = _grid_tiles(src_w, src_h, effective_tile_size, pad)
    stats.total_tiles += len(tiles)
    logger.info(
        f"Stage {stage_index}/{total_stages} tiled: "
        f"{src_w}x{src_h} -> {canvas_w}x{canvas_h} "
        f"({len(tiles)} images, core={effective_tile_size}px)"
    )

    for idx, t in enumerate(tiles):
        crop_left = t.x - t.pad_left
        crop_top = t.y - t.pad_top
        crop_right = t.x + t.w + t.pad_right
        crop_bottom = t.y + t.h + t.pad_bottom
        tile_img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
        tile_core = img.crop((t.x, t.y, t.x + t.w, t.y + t.h))

        tile_stage_target = max(1, round(max(tile_img.width, tile_img.height) * stage_ratio))
        used_model = False
        if _is_uniform_image(tile_core) or _is_uniform_image(tile_img):
            stats.local_calls += 1
            if idx % 10 == 0 or idx == len(tiles) - 1:
                logger.info(
                    f"Stage {stage_index}/{total_stages} image {idx + 1}/{len(tiles)} uniform tile "
                    f"[{t.y // effective_tile_size},{t.x // effective_tile_size}] "
                    f"{tile_img.width}x{tile_img.height} -> {tile_stage_target}px locally"
                )
            upscaled_tile = _resize_longest(tile_img, tile_stage_target)
        else:
            stats.api_calls += 1
            model_tile_img, tile_target = _prepare_model_input(tile_img, tile_stage_target)
            tile_label = (
                f"Stage {stage_index}/{total_stages} image {idx + 1}/{len(tiles)} "
                f"[{t.y // effective_tile_size},{t.x // effective_tile_size}]"
            )

            if idx % 10 == 0 or idx == len(tiles) - 1:
                logger.info(
                    f"{tile_label} model tile "
                    f"{tile_img.width}x{tile_img.height} -> "
                    f"{model_tile_img.width}x{model_tile_img.height} -> {tile_target}px"
                )

            upscaled_bytes = await _upscale_with_retry(
                upscale_fn,
                _image_to_png(model_tile_img),
                tile_target,
                idx,
                len(tiles),
                delay_between_tiles,
                tile_label,
            )
            upscaled_tile = Image.open(io.BytesIO(upscaled_bytes)).convert("RGB")
            used_model = True

        actual_ratio_w = upscaled_tile.width / tile_img.width
        actual_ratio_h = upscaled_tile.height / tile_img.height
        inner_left = int(t.pad_left * actual_ratio_w)
        inner_top = int(t.pad_top * actual_ratio_h)
        inner_right = min(int(inner_left + t.w * actual_ratio_w), upscaled_tile.width)
        inner_bottom = min(int(inner_top + t.h * actual_ratio_h), upscaled_tile.height)
        inner = upscaled_tile.crop((inner_left, inner_top, inner_right, inner_bottom))

        paste_x = round(t.x * stage_ratio)
        paste_y = round(t.y * stage_ratio)
        target_w = max(1, round((t.x + t.w) * stage_ratio) - paste_x)
        target_h = max(1, round((t.y + t.h) * stage_ratio) - paste_y)
        inner = inner.resize((target_w, target_h), Image.Resampling.BICUBIC)
        canvas.paste(inner, (paste_x, paste_y))

        if used_model and idx < len(tiles) - 1:
            await asyncio.sleep(delay_between_tiles)

    return canvas


async def _upscale_stage(
    img: Image.Image,
    stage_target_size: int,
    stage_index: int,
    total_stages: int,
    upscale_fn,
    tile_size: int,
    pad: int,
    delay_between_tiles: float,
    stats: UpscaleStats,
) -> Image.Image:
    """Run one <=2x stage, deciding whether this stage needs tiling."""
    if max(img.width, img.height) <= MAX_TILE_MODEL_INPUT_SIZE:
        logger.info(
            f"Stage {stage_index}/{total_stages} direct: "
            f"{img.width}x{img.height} -> longest {stage_target_size}px"
        )
        return await _upscale_direct_stage(
            img,
            stage_target_size,
            stage_index,
            total_stages,
            upscale_fn,
            delay_between_tiles,
            stats,
        )

    return await _upscale_tiled_stage(
        img,
        stage_target_size,
        stage_index,
        total_stages,
        upscale_fn,
        tile_size,
        pad,
        delay_between_tiles,
        stats,
    )


async def tile_upscale(
    img_bytes: bytes,
    target_size: int,
    upscale_fn,
    tile_size: int = TILE_SIZE,
    pad: int = TILE_PAD,
    delay_between_tiles: float = TILE_DELAY_SECONDS,
    sharpen: bool = False,
    mode: str = UPSCALE_MODE_PROGRESSIVE,
) -> bytes:
    """Upscale an image via tiled processing.

    Splits the image into overlapping tiles, upscales each tile individually,
    then stitches them together. Handles images of any size without hitting
    GPU memory limits.

    Args:
        img_bytes: Source image bytes
        target_size: Desired output resolution (longest side)
        upscale_fn: Async fn(tile_bytes, tile_target) -> upscaled_bytes
        tile_size: Size of each tile in pixels (source resolution)
        pad: Overlap padding around each tile to avoid seams
        delay_between_tiles: Seconds to wait between tiles (for rate limiting)
        sharpen: Apply post-upscale sharpening to the final stitched canvas
        mode: "progressive" splits into 2x stages (2x -> 4x -> 8x ...);
            "oneshot" runs a single stage directly to the target size.

    Returns:
        Upscaled stitched image as PNG bytes
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    src_w, src_h = img.size

    src_longest = max(src_w, src_h)

    current = img
    current_longest = src_longest
    if mode == UPSCALE_MODE_ONESHOT:
        stage_targets: list[int] = [target_size] if target_size > src_longest else []
    else:
        stage_targets = []
        planned_longest = src_longest
        while planned_longest < target_size:
            planned_longest = min(target_size, planned_longest * STAGE_UPSCALE_FACTOR)
            stage_targets.append(planned_longest)

    total_stages = len(stage_targets)
    logger.info(
        f"Tile upscale ({mode}): {src_w}x{src_h} -> longest {target_size}px "
        f"in {total_stages} stage(s)"
    )

    stats = UpscaleStats()
    for stage_index, stage_target_size in enumerate(stage_targets, start=1):
        logger.info(
            f"Upscale stage {stage_index}/{total_stages}: {current.width}x{current.height} "
            f"-> longest {stage_target_size}px"
        )
        current = await _upscale_stage(
            current,
            stage_target_size,
            stage_index,
            total_stages,
            upscale_fn,
            tile_size,
            pad,
            delay_between_tiles,
            stats,
        )
        current_longest = max(current.width, current.height)

    if current_longest != target_size:
        before = current.size
        current = _resize_longest(current, target_size)
        logger.info(f"Final resize: {before[0]}x{before[1]} -> {current.width}x{current.height}")

    # Apply post-upscale sharpen if requested
    if sharpen:
        current = current.filter(ImageFilter.SHARPEN)

    output = io.BytesIO()
    current.save(output, format="PNG")
    result = output.getvalue()
    logger.info(f"Tile upscale complete: {len(img_bytes)} -> {len(result)} bytes")
    stats.log_summary(logger)
    return result


__all__ = [
    "BLANK_TILE_BLACK_CONTENT_MIN",
    "BLANK_TILE_BLACK_MAX",
    "BLANK_TILE_NOISE_MAX_RATIO",
    "BLANK_TILE_WHITE_CONTENT_MAX",
    "BLANK_TILE_WHITE_MIN",
    "MAX_TILE_MODEL_INPUT_SIZE",
    "MAX_TILE_TARGET_RATIO",
    "MIN_TILE_INPUT_FOR_SINGLE_PASS",
    "MIN_TILE_TARGET_SIZE",
    "STAGE_UPSCALE_FACTOR",
    "TILE_SIZE",
    "UNIFORM_TILE_CHANNEL_DELTA",
    "UPSCALE_MODE_ONESHOT",
    "UPSCALE_MODE_PROGRESSIVE",
    "UpscaleStats",
    "tile_upscale",
]
