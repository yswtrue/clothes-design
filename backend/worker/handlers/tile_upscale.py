"""Tile-based image upscaling to bypass GPU memory limits.

Splits large images into overlapping tiles, upscales each tile via the
AI upscaler, then stitches them back into a single high-resolution image.
"""

import asyncio
import io
import logging
import math
from dataclasses import dataclass

from PIL import Image, ImageFilter

from shared.ai.exceptions import ProviderRateLimitError

logger = logging.getLogger(__name__)

# GPU-safe tile size — ESRGAN on Replicate handles up to ~2M pixels per tile
TILE_SIZE = 1024
TILE_PAD = 64  # overlap padding to avoid seam artifacts
# Replicate free tier: 6 requests/min, burst=1 → ~12s between tiles safely
TILE_DELAY_SECONDS = 12.0
# Keep tiled Replicate requests single-pass. Higher target ratios trigger the
# provider's progressive ESRGAN loop, which feeds 2x intermediate tiles back
# into Replicate and can exceed the model's input pixel limit.
MAX_TILE_TARGET_RATIO = 2.5
# Keep Replicate model outputs under roughly 2M pixels. Real-ESRGAN returns a
# fixed 2x output, so a 704px square input becomes 1408px square (~1.98M px).
MAX_TILE_MODEL_INPUT_SIZE = 704
MIN_TILE_TARGET_SIZE = 1024
MIN_TILE_INPUT_FOR_SINGLE_PASS = math.ceil(MIN_TILE_TARGET_SIZE / MAX_TILE_TARGET_RATIO)
# Rate limit retry
MAX_RATE_LIMIT_RETRIES = 5


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
) -> bytes:
    """Upscale a single tile with rate-limit retry logic."""
    for retry in range(MAX_RATE_LIMIT_RETRIES):
        try:
            return await upscale_fn(tile_bytes, tile_target)
        except ProviderRateLimitError:
            if retry == MAX_RATE_LIMIT_RETRIES - 1:
                raise
            wait = delay * (retry + 1)
            logger.warning(
                f"Tile {tile_idx + 1}/{total_tiles} rate limited, "
                f"retry {retry + 1}/{MAX_RATE_LIMIT_RETRIES} in {wait:.0f}s"
            )
            await asyncio.sleep(wait)
    # This line is unreachable but keeps type checkers happy
    raise ProviderRateLimitError("Max rate-limit retries exceeded")


async def tile_upscale(
    img_bytes: bytes,
    target_size: int,
    upscale_fn,
    tile_size: int = TILE_SIZE,
    pad: int = TILE_PAD,
    delay_between_tiles: float = TILE_DELAY_SECONDS,
    sharpen: bool = False,
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

    Returns:
        Upscaled stitched image as PNG bytes
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    src_w, src_h = img.size

    # Calculate required scale to reach target
    src_longest = max(src_w, src_h)
    scale = max(2, round(target_size / src_longest / 2) * 2)  # round to nearest even
    scale = min(scale, 8)  # max ESRGAN scale is 8x

    # Pre-allocate canvas for stitched result
    canvas_w = src_w * scale
    canvas_h = src_h * scale
    canvas = Image.new("RGB", (canvas_w, canvas_h))

    # Build tile grid
    tiles = _grid_tiles(src_w, src_h, tile_size, pad)
    # Request only a single model pass per tile. The final canvas still reaches
    # the requested resolution through deterministic stitching + resize below.
    tile_target_ratio = MAX_TILE_TARGET_RATIO

    logger.info(
        f"Tile upscale: {src_w}x{src_h} -> {canvas_w}x{canvas_h} "
        f"({len(tiles)} tiles, {scale}x)"
    )

    for idx, t in enumerate(tiles):
        t.scale = scale

        # Crop tile region with padding
        crop_left = t.x - t.pad_left
        crop_top = t.y - t.pad_top
        crop_right = t.x + t.w + t.pad_right
        crop_bottom = t.y + t.h + t.pad_bottom
        tile_img = img.crop((crop_left, crop_top, crop_right, crop_bottom))

        # Determine model input and target for this tile. Replicate rejects
        # target_size below 1024, while targets above 2.5x input trigger provider
        # multi-pass. The Real-ESRGAN Cog image can also fail while uploading
        # oversized 2x outputs, so large padded tiles are downscaled locally
        # before the model call; final canvas quality is restored by stitching
        # and deterministic resize below.
        tile_longest = max(tile_img.width, tile_img.height)
        model_tile_img = tile_img
        if tile_longest > MAX_TILE_MODEL_INPUT_SIZE:
            input_ratio = MAX_TILE_MODEL_INPUT_SIZE / tile_longest
            model_tile_img = tile_img.resize(
                (
                    max(1, math.ceil(tile_img.width * input_ratio)),
                    max(1, math.ceil(tile_img.height * input_ratio)),
                ),
                Image.Resampling.BICUBIC,
            )
        elif tile_longest < MIN_TILE_INPUT_FOR_SINGLE_PASS:
            input_ratio = MIN_TILE_INPUT_FOR_SINGLE_PASS / tile_longest
            model_tile_img = tile_img.resize(
                (
                    max(1, math.ceil(tile_img.width * input_ratio)),
                    max(1, math.ceil(tile_img.height * input_ratio)),
                ),
                Image.Resampling.BICUBIC,
            )
        model_tile_longest = max(model_tile_img.width, model_tile_img.height)
        tile_target = max(
            MIN_TILE_TARGET_SIZE,
            int(model_tile_longest * tile_target_ratio),
        )

        # Convert to bytes and upscale
        buf = io.BytesIO()
        model_tile_img.save(buf, format="PNG")
        tile_bytes = buf.getvalue()

        if idx % 10 == 0 or idx == len(tiles) - 1:
            logger.info(
                f"Tile {idx + 1}/{len(tiles)} [{t.y // tile_size},{t.x // tile_size}] "
                f"{tile_img.width}x{tile_img.height} -> "
                f"{model_tile_img.width}x{model_tile_img.height} -> {tile_target}px"
            )

        upscaled_bytes = await _upscale_with_retry(
            upscale_fn, tile_bytes, tile_target,
            idx, len(tiles), delay_between_tiles,
        )
        upscaled_tile = Image.open(io.BytesIO(upscaled_bytes))

        # Compute actual scale ratio (ESRGAN may not match our planned scale)
        actual_ratio_w = upscaled_tile.width / tile_img.width
        actual_ratio_h = upscaled_tile.height / tile_img.height

        # Crop out padding using the actual upscale ratio
        inner_left = int(t.pad_left * actual_ratio_w)
        inner_top = int(t.pad_top * actual_ratio_h)
        inner_right = int(inner_left + t.w * actual_ratio_w)
        inner_bottom = int(inner_top + t.h * actual_ratio_h)
        inner_right = min(inner_right, upscaled_tile.width)
        inner_bottom = min(inner_bottom, upscaled_tile.height)
        inner = upscaled_tile.crop((inner_left, inner_top, inner_right, inner_bottom))

        # Resize inner region to target dimensions for consistent stitching
        target_w = t.w * scale
        target_h = t.h * scale
        inner = inner.resize((target_w, target_h), Image.Resampling.BICUBIC)

        paste_x = t.x * scale
        paste_y = t.y * scale
        canvas.paste(inner, (paste_x, paste_y))

        # Rate-limit delay between tiles
        if idx < len(tiles) - 1:
            await asyncio.sleep(delay_between_tiles)

    # Final resize if canvas doesn't match target exactly
    canvas_longest = max(canvas_w, canvas_h)
    if canvas_longest != target_size:
        ratio = target_size / canvas_longest
        final_w = int(canvas_w * ratio)
        final_h = int(canvas_h * ratio)
        canvas = canvas.resize((final_w, final_h), Image.Resampling.BICUBIC)
        logger.info(f"Final resize: {canvas_w}x{canvas_h} -> {final_w}x{final_h}")

    # Apply post-upscale sharpen if requested
    if sharpen:
        canvas = canvas.filter(ImageFilter.SHARPEN)

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    result = output.getvalue()
    logger.info(f"Tile upscale complete: {len(img_bytes)} -> {len(result)} bytes")
    return result


__all__ = [
    "MAX_TILE_MODEL_INPUT_SIZE",
    "MAX_TILE_TARGET_RATIO",
    "MIN_TILE_INPUT_FOR_SINGLE_PASS",
    "MIN_TILE_TARGET_SIZE",
    "TILE_SIZE",
    "tile_upscale",
]
