"""Fabric patch segmentation service.

Detects colored fabric patches on a white/light background using
RGB color distance from white, then extracts each patch via connected
component analysis.

Performance: connected-component search uses np.argwhere() to iterate
only foreground pixels (typically 10-30% of the image).
"""

import io
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

# Pixels whose RGB Euclidean distance from pure white (255,255,255)
# exceeds this threshold are considered foreground (fabric).
WHITE_DIST_THRESHOLD = 35


def _dilate(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Dilate a binary mask by propagating foreground pixels outward."""
    result = mask.copy().astype(bool)
    for _ in range(radius):
        dilated = np.zeros_like(result)
        dilated[1:, :] |= result[:-1, :]
        dilated[:-1, :] |= result[1:, :]
        dilated[:, 1:] |= result[:, :-1]
        dilated[:, :-1] |= result[:, 1:]
        dilated |= result
        result = dilated
    return result.astype(np.uint8)


def _erode(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Erode a binary mask by shrinking foreground pixels inward."""
    result = mask.copy().astype(bool)
    for _ in range(radius):
        eroded = np.ones_like(result)
        eroded[1:, :] &= result[:-1, :]
        eroded[:-1, :] &= result[1:, :]
        eroded[:, 1:] &= result[:, :-1]
        eroded[:, :-1] &= result[:, 1:]
        eroded &= result
        result = eroded
    return result.astype(np.uint8)


def _morphological_closing(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Apply morphological closing: dilate then erode."""
    return _erode(_dilate(mask, radius), radius)


def _morphological_opening(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Apply morphological opening: erode then dilate (removes small noise)."""
    return _dilate(_erode(mask, radius), radius)


def _bfs_component(
    y0: int, x0: int, binary: np.ndarray, visited: np.ndarray
) -> tuple[int, int, int, int, int] | None:
    """BFS from (y0,x0) to find a connected component and its bounding box.

    Returns (x1, y1, x2, y2, area) or None if already visited.
    """
    if visited[y0, x0]:
        return None

    h, w = binary.shape
    queue: deque[tuple[int, int]] = deque()
    queue.append((y0, x0))
    visited[y0, x0] = True

    min_x = max_x = x0
    min_y = max_y = y0
    area = 0

    while queue:
        y, x = queue.popleft()
        area += 1

        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)

        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and binary[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    return (min_x, min_y, max_x, max_y, area)


def _find_connected_components(
    binary: np.ndarray,
    min_area: int,
) -> list[tuple[int, int, int, int]]:
    """Find 4-connected components via BFS on np.argwhere seed points."""
    visited = np.zeros_like(binary, dtype=bool)
    components: list[tuple[int, int, int, int]] = []

    fg_coords: np.ndarray = np.argwhere(binary == 1)

    for cy, cx in fg_coords:
        result = _bfs_component(int(cy), int(cx), binary, visited)
        if result is None:
            continue
        x1, y1, x2, y2, area = result
        if area >= min_area:
            components.append((x1, y1, x2, y2))

    return components


def _apply_padding(
    x1: int, y1: int, x2: int, y2: int, pad: int, w: int, h: int
) -> tuple[int, int, int, int]:
    """Add padding to bbox, clamped to image boundaries."""
    return (
        max(0, x1 - pad),
        max(0, y1 - pad),
        min(w - 1, x2 + pad),
        min(h - 1, y2 + pad),
    )


def segment_fabric_patches(image_bytes: bytes) -> list[dict]:
    """Segment colored fabric patches from a white-background image.

    Uses RGB color distance from pure white (255,255,255) instead of
    grayscale Otsu, so light-colored fabrics are correctly separated
    from the white background.

    Returns empty list if fewer than 2 patches are found.
    """
    # Load image
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_w, img_h = pil_image.size
    min_area_pixels = max(1, int(img_w * img_h * 0.001))

    # Convert to float numpy array for distance calculation
    img_np = np.array(pil_image, dtype=np.float32)

    # Euclidean distance from pure white in RGB space
    # White = (255,255,255), any deviation means color
    dist = np.sqrt(np.sum((img_np - 255.0) ** 2, axis=2))

    # Blur the distance map to reduce fabric texture noise
    dist_uint8 = np.clip(dist, 0, 255).astype(np.uint8)
    dist_pil = Image.fromarray(dist_uint8, mode="L")
    dist_blurred = np.array(
        dist_pil.filter(ImageFilter.GaussianBlur(radius=3)), dtype=np.float32
    )

    # Threshold: pixels far enough from white are fabric
    mask = (dist_blurred > WHITE_DIST_THRESHOLD).astype(np.uint8)

    # Morphological opening to remove small noise (fabric lint, dust)
    mask = _morphological_opening(mask, radius=1)
    # Morphological closing to fill small holes within fabric patches
    mask = _morphological_closing(mask, radius=3)

    # Find connected components
    bboxes = _find_connected_components(mask, min_area=min_area_pixels)

    if len(bboxes) < 2:
        return []

    # Extract each patch from the original image
    results: list[dict] = []
    for x1, y1, x2, y2 in bboxes:
        x1, y1, x2, y2 = _apply_padding(x1, y1, x2, y2, pad=5, w=img_w, h=img_h)

        patch = pil_image.crop((x1, y1, x2 + 1, y2 + 1))

        buf = io.BytesIO()
        patch.save(buf, format="PNG")
        patch_bytes = buf.getvalue()

        results.append(
            {
                "image_bytes": patch_bytes,
                "bbox": (x1, y1, x2, y2),
                "width": x2 - x1 + 1,
                "height": y2 - y1 + 1,
            }
        )

    return results
