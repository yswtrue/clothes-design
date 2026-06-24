"""Fabric patch segmentation service.

Detects and extracts individual fabric patches from an input image
using computer vision techniques (thresholding, morphology, connected components).
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


def _find_connected_components(
    binary: np.ndarray,
    min_area: int,
) -> list[list[tuple[int, int]]]:
    """Find 4-connected components in a binary mask using BFS.

    Returns list of components where each component is a list of (y, x) pixel coordinates.
    Only components with area >= min_area are returned.
    """
    h, w = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    components: list[list[tuple[int, int]]] = []

    for y in range(h):
        for x in range(w):
            if binary[y, x] == 1 and not visited[y, x]:
                component: list[tuple[int, int]] = []
                queue: deque[tuple[int, int]] = deque()
                queue.append((y, x))
                visited[y, x] = True

                while queue:
                    cy, cx = queue.popleft()
                    component.append((cy, cx))

                    # 4-connected neighbors
                    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ny, nx = cy + dy, cx + dx
                        if (
                            0 <= ny < h
                            and 0 <= nx < w
                            and binary[ny, nx] == 1
                            and not visited[ny, nx]
                        ):
                            visited[ny, nx] = True
                            queue.append((ny, nx))

                if len(component) >= min_area:
                    components.append(component)

    return components


def _compute_bbox_with_padding(
    component: list[tuple[int, int]],
    img_h: int,
    img_w: int,
    padding: int = 5,
) -> tuple[int, int, int, int]:
    """Compute bounding box for a component with padding, clamped to image bounds."""
    ys = [p[0] for p in component]
    xs = [p[1] for p in component]
    x1 = max(0, min(xs) - padding)
    y1 = max(0, min(ys) - padding)
    x2 = min(img_w - 1, max(xs) + padding)
    y2 = min(img_h - 1, max(ys) + padding)
    return (x1, y1, x2, y2)


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
    pil_image = Image.open(io.BytesIO(image_bytes))
    pil_image = pil_image.convert("RGB")
    orig_w, orig_h = pil_image.size
    total_pixels = orig_w * orig_h
    min_area_pixels = max(1, int(total_pixels * 0.001))

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

    # Find connected components
    components = _find_connected_components(mask, min_area=min_area_pixels)

    # Require at least 2 patches
    if len(components) < 2:
        return []

    # Extract each patch
    results: list[dict] = []
    for component in components:
        x1, y1, x2, y2 = _compute_bbox_with_padding(component, orig_h, orig_w, padding=5)

        # Crop from original image
        patch = pil_image.crop((x1, y1, x2 + 1, y2 + 1))

        # Save as PNG bytes in memory
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
