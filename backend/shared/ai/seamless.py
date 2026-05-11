"""Seamless tiling post-processing for pattern generation.

Converts regular images to seamless tileable patterns using offset blending.
"""

import io
import logging
from enum import Enum

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class BlendMode(str, Enum):
    """Blending mode for seamless conversion."""

    LINEAR = "linear"  # Simple linear gradient blend
    COSINE = "cosine"  # Smoother cosine interpolation
    SIGMOID = "sigmoid"  # S-curve for sharper center transition


def make_seamless(
    image_bytes: bytes,
    blend_width: float = 0.25,
    blend_mode: BlendMode = BlendMode.COSINE,
) -> bytes:
    """Convert an image to seamless tileable pattern.

    Uses the offset blending technique:
    1. Offset image by half width and height (swap quadrants)
    2. Blend the seams in the center with gradient masks
    3. Result tiles seamlessly in both X and Y directions

    Args:
        image_bytes: Input image as bytes (PNG/JPEG)
        blend_width: Width of blend zone as fraction of image size (0.1-0.5)
        blend_mode: Blending interpolation mode

    Returns:
        Seamless tileable image as PNG bytes
    """
    # Load image
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    width, height = img.size
    arr = np.array(img, dtype=np.float32)

    logger.info(f"Making seamless: {width}x{height}, blend_width={blend_width}, mode={blend_mode}")

    # Clamp blend width
    blend_width = max(0.1, min(0.5, blend_width))

    # Step 1: Offset the image by half (swap quadrants)
    offset_arr = _offset_image(arr, width // 2, height // 2)

    # Step 2: Create blend masks for horizontal and vertical seams
    h_mask = _create_blend_mask(width, blend_width, blend_mode)
    v_mask = _create_blend_mask(height, blend_width, blend_mode)

    # Step 3: Blend original and offset images
    # Horizontal blend (fixes left-right seam)
    h_blend = _blend_horizontal(arr, offset_arr, h_mask)

    # Vertical blend on the h_blend result (fixes top-bottom seam)
    result = _blend_vertical(h_blend, _offset_image(h_blend, 0, height // 2), v_mask)

    # Final offset to restore original content positioning
    result = _offset_image(result, width // 2, height // 2)

    # Convert back to image
    result_img = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), mode="RGBA")

    # Convert to RGB if no alpha needed, then to PNG bytes
    if not _has_transparency(result_img):
        result_img = result_img.convert("RGB")

    output = io.BytesIO()
    result_img.save(output, format="PNG", optimize=True)
    output.seek(0)

    logger.info(f"Seamless conversion complete: {len(output.getvalue())} bytes")
    return output.getvalue()


def _offset_image(arr: np.ndarray, offset_x: int, offset_y: int) -> np.ndarray:
    """Offset image array by rolling pixels."""
    result = np.roll(arr, offset_x, axis=1)  # Horizontal
    result = np.roll(result, offset_y, axis=0)  # Vertical
    return result


def _create_blend_mask(size: int, blend_width: float, mode: BlendMode) -> np.ndarray:
    """Create 1D gradient mask for blending.

    The mask has value 0 at the center, 1 at the edges, with a gradient
    in the blend zone.
    """
    blend_pixels = int(size * blend_width)
    center = size // 2

    mask = np.ones(size, dtype=np.float32)

    # Create gradient in the blend zone around center
    for i in range(blend_pixels):
        # Distance from center, normalized to 0-1
        t = i / blend_pixels

        if mode == BlendMode.LINEAR:
            blend_value = t
        elif mode == BlendMode.COSINE:
            blend_value = (1 - np.cos(t * np.pi)) / 2
        elif mode == BlendMode.SIGMOID:
            # Sigmoid-like curve
            blend_value = 1 / (1 + np.exp(-10 * (t - 0.5)))
        else:
            blend_value = t

        # Apply symmetrically around center
        left_idx = center - blend_pixels + i
        right_idx = center + blend_pixels - 1 - i

        if 0 <= left_idx < size:
            mask[left_idx] = blend_value
        if 0 <= right_idx < size:
            mask[right_idx] = blend_value

    # Center region should be 0 (use offset image)
    half_blend = blend_pixels // 2
    mask[max(0, center - half_blend) : min(size, center + half_blend)] = 0

    return mask


def _blend_horizontal(
    original: np.ndarray, offset: np.ndarray, mask: np.ndarray
) -> np.ndarray:
    """Blend two images horizontally using mask."""
    # Expand mask to match image dimensions (H, W, C)
    mask_expanded = mask[np.newaxis, :, np.newaxis]  # (1, W, 1)
    mask_expanded = np.broadcast_to(mask_expanded, original.shape)

    return original * mask_expanded + offset * (1 - mask_expanded)


def _blend_vertical(
    original: np.ndarray, offset: np.ndarray, mask: np.ndarray
) -> np.ndarray:
    """Blend two images vertically using mask."""
    # Expand mask to match image dimensions (H, W, C)
    mask_expanded = mask[:, np.newaxis, np.newaxis]  # (H, 1, 1)
    mask_expanded = np.broadcast_to(mask_expanded, original.shape)

    return original * mask_expanded + offset * (1 - mask_expanded)


def _has_transparency(img: Image.Image) -> bool:
    """Check if image has meaningful transparency."""
    if img.mode != "RGBA":
        return False

    alpha = np.array(img)[:, :, 3]
    return np.any(alpha < 255)


def verify_seamless(image_bytes: bytes, tolerance: float = 5.0) -> dict:
    """Verify if an image is seamless tileable.

    Compares edge pixels to detect discontinuities.

    Args:
        image_bytes: Image to verify
        tolerance: Maximum allowed average pixel difference (0-255)

    Returns:
        Dict with verification results
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    arr = np.array(img, dtype=np.float32)

    # Compare left edge with right edge
    left_edge = arr[:, 0, :3]
    right_edge = arr[:, -1, :3]
    h_diff = np.mean(np.abs(left_edge - right_edge))

    # Compare top edge with bottom edge
    top_edge = arr[0, :, :3]
    bottom_edge = arr[-1, :, :3]
    v_diff = np.mean(np.abs(top_edge - bottom_edge))

    is_seamless = h_diff <= tolerance and v_diff <= tolerance

    return {
        "is_seamless": is_seamless,
        "horizontal_diff": float(h_diff),
        "vertical_diff": float(v_diff),
        "tolerance": tolerance,
    }


__all__ = ["BlendMode", "make_seamless", "verify_seamless"]
