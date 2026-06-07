"""Image format conversion with ICC color management for print-ready output."""

import io
import logging
import os
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageCms

logger = logging.getLogger(__name__)

ColorSpace = Literal["RGB", "CMYK"]

DEFAULT_CMYK_PROFILE_PATH = Path(__file__).resolve().parents[2] / "USWebCoatedSWOP.icc"
SRGB_PROFILE_PATH = os.getenv("ICC_SRGB_PROFILE")
CMYK_PROFILE_PATH = os.getenv("ICC_CMYK_PROFILE") or str(DEFAULT_CMYK_PROFILE_PATH)

_profile_cache: dict[str, Any] = {}


def _get_srgb_profile() -> Any:
    if "srgb" not in _profile_cache:
        if SRGB_PROFILE_PATH and Path(SRGB_PROFILE_PATH).exists():
            _profile_cache["srgb"] = ImageCms.getOpenProfile(SRGB_PROFILE_PATH)
            logger.debug(f"Loaded sRGB profile from {SRGB_PROFILE_PATH}")
        else:
            _profile_cache["srgb"] = ImageCms.createProfile("sRGB")
            logger.debug("Using built-in sRGB profile")
    return _profile_cache["srgb"]


def _get_cmyk_profile() -> Any | None:
    if "cmyk" not in _profile_cache:
        if CMYK_PROFILE_PATH and Path(CMYK_PROFILE_PATH).exists():
            _profile_cache["cmyk"] = ImageCms.getOpenProfile(CMYK_PROFILE_PATH)
            logger.debug(f"Loaded CMYK profile from {CMYK_PROFILE_PATH}")
        else:
            _profile_cache["cmyk"] = None
            if CMYK_PROFILE_PATH:
                logger.warning(
                    f"CMYK profile not found at {CMYK_PROFILE_PATH}, "
                    "falling back to naive conversion"
                )
    return _profile_cache["cmyk"]


def _convert_rgb_to_cmyk_with_profile(
    img: Image.Image,
    rendering_intent: ImageCms.Intent = ImageCms.Intent.RELATIVE_COLORIMETRIC,
) -> Image.Image:
    """Convert RGB to CMYK using ICC profiles.

    Rendering intents: PERCEPTUAL (photos), RELATIVE_COLORIMETRIC (graphics),
    SATURATION (business graphics), ABSOLUTE_COLORIMETRIC (proofing).
    """
    srgb_profile = _get_srgb_profile()
    cmyk_profile = _get_cmyk_profile()

    if cmyk_profile is None:
        logger.warning("No CMYK ICC profile configured, using naive RGB→CMYK conversion")
        return img.convert("CMYK")

    embedded_profile = img.info.get("icc_profile")
    if embedded_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(io.BytesIO(embedded_profile))
            logger.debug("Using embedded ICC profile from source image")
        except Exception as e:
            logger.warning(f"Failed to read embedded ICC profile: {e}, using sRGB")
            source_profile = srgb_profile
    else:
        source_profile = srgb_profile

    try:
        transform = ImageCms.buildTransform(
            source_profile,
            cmyk_profile,
            "RGB",
            "CMYK",
            renderingIntent=rendering_intent,
        )
        cmyk_img = ImageCms.applyTransform(img, transform)
        if cmyk_img is None:
            raise ValueError("applyTransform returned None")

        cmyk_profile_bytes = cmyk_profile.tobytes()
        cmyk_img.info["icc_profile"] = cmyk_profile_bytes

        logger.debug("Successfully converted RGB→CMYK with ICC profiles")
        return cmyk_img

    except Exception as e:
        logger.error(f"ICC profile conversion failed: {e}, falling back to naive conversion")
        return img.convert("CMYK")


def png_to_tif(
    png_bytes: bytes,
    color_space: ColorSpace = "CMYK",
    compression: str = "tiff_lzw",
    dpi: int = 300,
    use_icc_profile: bool = True,
) -> bytes:
    """Convert PNG to TIF with optional ICC-managed CMYK conversion.

    Set ICC_CMYK_PROFILE env var to a .icc file path (e.g., USWebCoatedSWOP.icc)
    for proper color management. Without it, falls back to naive conversion.
    """
    img = Image.open(io.BytesIO(png_bytes))
    embedded_icc = img.info.get("icc_profile")

    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode == "LA":
        background = Image.new("L", img.size, 255)
        background.paste(img, mask=img.split()[1])
        img = background.convert("RGB")
    elif img.mode == "P":
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode == "L":
        img = img.convert("RGB")

    if embedded_icc and "icc_profile" not in img.info:
        img.info["icc_profile"] = embedded_icc

    # For RGB output without ICC profile, embed sRGB to ensure consistent color
    if color_space == "RGB" and "icc_profile" not in img.info:
        srgb_profile = _get_srgb_profile()
        img.info["icc_profile"] = ImageCms.ImageCmsProfile(srgb_profile).tobytes()
        logger.debug("Embedded sRGB profile for RGB TIF output")

    if color_space == "CMYK":
        if use_icc_profile:
            img = _convert_rgb_to_cmyk_with_profile(img)
        else:
            img = img.convert("CMYK")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    output = io.BytesIO()
    save_kwargs: dict[str, Any] = {
        "format": "TIFF",
        "compression": compression,
        "dpi": (dpi, dpi),
    }

    if "icc_profile" in img.info:
        save_kwargs["icc_profile"] = img.info["icc_profile"]

    img.save(output, **save_kwargs)
    return output.getvalue()


def get_image_info(image_bytes: bytes) -> dict:
    """Get image metadata.

    Args:
        image_bytes: Image data as bytes.

    Returns:
        Dictionary with image info:
        - format: Image format (PNG, JPEG, etc.)
        - mode: Color mode (RGB, RGBA, CMYK, etc.)
        - size: Tuple of (width, height)
        - width: Image width in pixels
        - height: Image height in pixels
    """
    img = Image.open(io.BytesIO(image_bytes))
    return {
        "format": img.format,
        "mode": img.mode,
        "size": img.size,
        "width": img.size[0],
        "height": img.size[1],
    }


__all__ = ["png_to_tif", "get_image_info", "ColorSpace"]
