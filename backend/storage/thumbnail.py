"""Thumbnail generation for uploaded images."""

import io
from pathlib import Path

from PIL import Image


class ThumbnailGenerator:
    """Generate optimized thumbnails for images."""

    MAX_SIZE = (400, 400)
    QUALITY = 85
    FORMAT = "JPEG"

    @classmethod
    async def generate(cls, image_data: bytes, original_filename: str) -> tuple[bytes, str]:
        """Generate a thumbnail from image data.

        Args:
            image_data: Original image bytes
            original_filename: Original filename for naming the thumbnail

        Returns:
            Tuple of (thumbnail_bytes, thumbnail_filename)
        """
        # Open image from bytes
        img = Image.open(io.BytesIO(image_data))

        # Convert RGBA to RGB if necessary (for JPEG compatibility)
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background

        # Resize maintaining aspect ratio
        img.thumbnail(cls.MAX_SIZE, Image.Resampling.LANCZOS)

        # Save to bytes
        output = io.BytesIO()
        img.save(output, format=cls.FORMAT, quality=cls.QUALITY, optimize=True)
        thumbnail_bytes = output.getvalue()

        # Generate thumbnail filename
        stem = Path(original_filename).stem
        thumbnail_filename = f"{stem}_thumb.jpg"

        return thumbnail_bytes, thumbnail_filename
