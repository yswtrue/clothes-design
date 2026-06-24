"""Fabric patch segmentation service.

Detects and extracts individual fabric patches from an input image
using computer vision techniques (thresholding, morphology, connected components).

Performance: connected-component search uses np.argwhere() to iterate
only foreground pixels (typically 10-30% of the image), avoiding a
full O(H*W) Python double-loop scan.
"""

import io
from collections import deque

import numpy as np
from PIL import Image, ImageFilter


def _otsu_threshold(gray: np.ndarray) -> int:
    """Compute Otsu's threshold for a grayscale image.

    Finds the threshold that maximizes between-class variance.
    """
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    if total == 0:
        return 0

    sum_total = float(np.arange(256).dot(hist.astype(np.float64)))
    sum_b = 0.0
    w_b = 0.0
    var_max = 0.0
    threshold = 0

    for t in range(256):
        w_b += float(hist[t])
        if w_b == 0 or abs(w_b - total) < 1e-10:
            continue
        w_f = total - w_b
        sum_b += float(t) * float(hist[t])
        sum_f = sum_total - sum_b

        mean_b = sum_b / w_b
        mean_f = sum_f / w_f

        var_between = w_b * w_f * (mean_b - mean_f) ** 2
        if var_between > var_max:
            var_max = var_between
            threshold = t

    return threshold


def _dilate(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Dilate a binary mask by propagating foreground pixels outward.

    Uses iterative 4-neighbor expansion for efficiency.
    """
    result = mask.copy().astype(bool)
    for _ in range(radius):
        dilated = np.zeros_like(result)
        # Shift in all 4 directions
        dilated[1:, :] |= result[:-1, :]  # down
        dilated[:-1, :] |= result[1:, :]  # up
        dilated[:, 1:] |= result[:, :-1]  # right
        dilated[:, :-1] |= result[:, 1:]  # left
        dilated |= result
        result = dilated
    return result.astype(np.uint8)


def _erode(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Erode a binary mask by shrinking foreground pixels inward.

    Uses iterative 4-neighbor contraction for efficiency.
    """
    result = mask.copy().astype(bool)
    for _ in range(radius):
        eroded = np.ones_like(result)
        eroded[1:, :] &= result[:-1, :]  # down
        eroded[:-1, :] &= result[1:, :]  # up
        eroded[:, 1:] &= result[:, :-1]  # right
        eroded[:, :-1] &= result[:, 1:]  # left
        eroded &= result
        result = eroded
    return result.astype(np.uint8)


def _morphological_closing(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Apply morphological closing: dilate then erode.

    Closing fills small holes and joins nearby objects.
    """
    return _erode(_dilate(mask, radius), radius)


def _bfs_component(
    y0: int, x0: int, binary: np.ndarray, visited: np.ndarray
) -> tuple[int, int, int, int, int] | None:
    """BFS from (y0,x0) to find connected component and its bounding box.

    Returns (x1, y1, x2, y2, area) or None if the component was already visited.
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
    """Find 4-connected components using BFS via np.argwhere seed points.

    Only iterates foreground pixels. Returns list of (x1, y1, x2, y2) bboxes
    for components whose area >= min_area.
    """
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
    """Segment the input image into individual fabric patches.

    Args:
        image_bytes: Raw image file bytes (JPEG, PNG, WebP, etc.)

    Returns:
        List of dicts, each containing:
            - image_bytes: PNG-encoded bytes of the cropped patch
            - bbox: (x1, y1, x2, y2) bounding box in original image coords
            - width: patch width in pixels
            - height: patch height in pixels

        Returns empty list if fewer than 2 patches are found.
    """
    # Load image with PIL
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_w, img_h = pil_image.size
    min_area_pixels = max(1, int(img_w * img_h * 0.001))

    # Convert to grayscale numpy array
    gray = np.array(pil_image.convert("L"), dtype=np.uint8)

    # Apply GaussianBlur to reduce noise
    blurred_pil = Image.fromarray(gray, mode="L").filter(ImageFilter.GaussianBlur(radius=3))
    blurred = np.array(blurred_pil, dtype=np.uint8)

    # Otsu's threshold to create binary mask
    threshold = _otsu_threshold(blurred)
    mask = (blurred > threshold).astype(np.uint8)

    # Heuristic: if foreground area > 50%, invert (assume background is majority)
    foreground_ratio = float(mask.sum()) / float(mask.size)
    if foreground_ratio > 0.5:
        mask = 1 - mask

    # Morphological closing: dilate 2px then erode 2px
    mask = _morphological_closing(mask, radius=2)

    # Find connected components → bboxes
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
