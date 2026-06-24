/**
 * Pure frontend fabric patch segmentation using Canvas API.
 *
 * Algorithm: RGB color distance from white → threshold → morphological
 * closing → BFS connected components → extract each patch as a blob URL.
 */

export interface PatchResult {
  index: number;
  blobUrl: string;
  width: number;
  height: number;
}

const WHITE_DIST_THRESHOLD = 35;

/** Load an image File into an HTMLImageElement. */
function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('Failed to load image'));
      img.src = reader.result as string;
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

/** Get RGBA pixel data from an image drawn onto a canvas. */
function getImageData(img: HTMLImageElement): {
  data: Uint8ClampedArray;
  width: number;
  height: number;
} {
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, 0, 0);
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  return { data: imageData.data, width: canvas.width, height: canvas.height };
}

/**
 * Build a binary mask where 1 = fabric (non-white), 0 = background (white).
 */
function buildMask(
  pixelData: Uint8ClampedArray,
  width: number,
  height: number,
): Uint8Array {
  const total = width * height;
  const mask = new Uint8Array(total);

  for (let i = 0; i < total; i++) {
    const r = pixelData[i * 4];
    const g = pixelData[i * 4 + 1];
    const b = pixelData[i * 4 + 2];
    const dr = r - 255;
    const dg = g - 255;
    const db = b - 255;
    const dist = Math.sqrt(dr * dr + dg * dg + db * db);
    mask[i] = dist > WHITE_DIST_THRESHOLD ? 1 : 0;
  }

  return mask;
}

/** Apply a simple box-blur pass to smooth the binary mask. */
function blurMask(mask: Uint8Array, width: number, height: number): Uint8Array {
  const result = new Uint8Array(mask);
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const idx = y * width + x;
      const sum =
        mask[idx - width - 1] +
        mask[idx - width] +
        mask[idx - width + 1] +
        mask[idx - 1] +
        mask[idx] +
        mask[idx + 1] +
        mask[idx + width - 1] +
        mask[idx + width] +
        mask[idx + width + 1];
      // Majority vote: if 5+ of 9 neighbors are foreground, keep as foreground
      result[idx] = sum >= 5 ? 1 : 0;
    }
  }
  return result;
}

/** Morphological closing: dilate then erode. */
function morphologicalClosing(
  mask: Uint8Array,
  width: number,
  height: number,
  radius: number,
): Uint8Array {
  let result = dilate(mask, width, height, radius);
  result = erode(result, width, height, radius);
  return result;
}

function dilate(
  mask: Uint8Array,
  width: number,
  height: number,
  radius: number,
): Uint8Array {
  let result = new Uint8Array(mask);
  for (let r = 0; r < radius; r++) {
    const next = new Uint8Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = y * width + x;
        if (result[idx]) {
          next[idx] = 1;
        } else {
          // Check 4 neighbors
          const top = y > 0 ? result[idx - width] : 0;
          const bottom = y < height - 1 ? result[idx + width] : 0;
          const left = x > 0 ? result[idx - 1] : 0;
          const right = x < width - 1 ? result[idx + 1] : 0;
          next[idx] = top || bottom || left || right ? 1 : 0;
        }
      }
    }
    result = next;
  }
  return result;
}

function erode(
  mask: Uint8Array,
  width: number,
  height: number,
  radius: number,
): Uint8Array {
  let result = new Uint8Array(mask);
  for (let r = 0; r < radius; r++) {
    const next = new Uint8Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = y * width + x;
        if (!result[idx]) {
          next[idx] = 0;
        } else {
          const top = y > 0 ? result[idx - width] : 1;
          const bottom = y < height - 1 ? result[idx + width] : 1;
          const left = x > 0 ? result[idx - 1] : 1;
          const right = x < width - 1 ? result[idx + 1] : 1;
          next[idx] = top && bottom && left && right ? 1 : 0;
        }
      }
    }
    result = next;
  }
  return result;
}

interface BBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

/** BFS connected components, return bounding boxes for components >= minArea. */
function findComponents(
  mask: Uint8Array,
  width: number,
  height: number,
  minArea: number,
): BBox[] {
  const visited = new Uint8Array(width * height);
  const components: BBox[] = [];

  for (let idx = 0; idx < mask.length; idx++) {
    if (!mask[idx] || visited[idx]) continue;

    // BFS
    const queue: number[] = [idx];
    visited[idx] = 1;

    let minX = idx % width;
    let maxX = minX;
    let minY = Math.floor(idx / width);
    let maxY = minY;
    let area = 0;
    let head = 0;

    while (head < queue.length) {
      const cur = queue[head++];
      area++;

      const x = cur % width;
      const y = Math.floor(cur / width);
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;

      // 4-connected neighbors
      const neighbors: [number, number][] = [];
      if (y > 0) neighbors.push([-width, 0]);
      if (y < height - 1) neighbors.push([width, 0]);
      if (x > 0) neighbors.push([-1, 0]);
      if (x < width - 1) neighbors.push([1, 0]);

      for (const [offset] of neighbors) {
        const nidx = cur + offset;
        if (mask[nidx] && !visited[nidx]) {
          visited[nidx] = 1;
          queue.push(nidx);
        }
      }
    }

    if (area >= minArea) {
      components.push({ x1: minX, y1: minY, x2: maxX, y2: maxY });
    }
  }

  return components;
}

/** Extract a patch from the source image as a blob URL. */
function extractPatch(
  img: HTMLImageElement,
  bbox: BBox,
  padding: number,
  imgW: number,
  imgH: number,
): { blobUrl: string; width: number; height: number } {
  const x1 = Math.max(0, bbox.x1 - padding);
  const y1 = Math.max(0, bbox.y1 - padding);
  const x2 = Math.min(imgW - 1, bbox.x2 + padding);
  const y2 = Math.min(imgH - 1, bbox.y2 + padding);
  const w = x2 - x1 + 1;
  const h = y2 - y1 + 1;

  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(img, x1, y1, w, h, 0, 0, w, h);

  return { blobUrl: canvas.toDataURL('image/png'), width: w, height: h };
}

/**
 * Segment fabric patches from an uploaded image file.
 *
 * Returns an array of patch results with blob URLs for immediate display.
 * Returns empty array if fewer than 2 patches are found.
 */
export async function segmentFabricPatches(
  file: File,
): Promise<PatchResult[]> {
  const img = await loadImage(file);
  const { data, width, height } = getImageData(img);

  // 1. Build binary mask: non-white pixels = fabric
  let mask = buildMask(data, width, height);

  // 2. Smooth to reduce fabric texture noise
  mask = blurMask(mask, width, height);

  // 3. Morphological closing to fill holes within patches
  mask = morphologicalClosing(mask, width, height, 3);

  // 4. Find connected components
  const minArea = Math.max(1, Math.floor((width * height) * 0.001));
  const bboxes = findComponents(mask, width, height, minArea);

  if (bboxes.length < 2) {
    return [];
  }

  // 5. Extract each patch as a blob URL
  return bboxes.map((bbox, i) => {
    const patch = extractPatch(img, bbox, 5, width, height);
    return {
      index: i,
      blobUrl: patch.blobUrl,
      width: patch.width,
      height: patch.height,
    };
  });
}
