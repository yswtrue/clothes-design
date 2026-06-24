/**
 * Pure frontend fabric patch segmentation using Canvas API.
 *
 * Extracts irregularly-shaped fabric patches with transparent backgrounds
 * by building a per-pixel component map during BFS and using it as an
 * alpha mask when cropping.
 *
 * Algorithm: RGB color distance from white → threshold → blur →
 * morphological closing → BFS with component ID tracking →
 * extract each patch with alpha mask.
 */

export interface PatchResult {
  index: number;
  blobUrl: string;
  width: number;
  height: number;
}

const WHITE_DIST_THRESHOLD = 35;

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
  return {
    data: ctx.getImageData(0, 0, canvas.width, canvas.height).data,
    width: canvas.width,
    height: canvas.height,
  };
}

/** Binary mask: 1 = non-white fabric, 0 = white background. */
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
    mask[i] = Math.sqrt(dr * dr + dg * dg + db * db) > WHITE_DIST_THRESHOLD ? 1 : 0;
  }

  return mask;
}

/** Box blur to smooth binary mask. */
function blurMask(mask: Uint8Array, width: number, height: number): Uint8Array {
  const result = new Uint8Array(mask);
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const idx = y * width + x;
      const sum =
        mask[idx - width - 1] + mask[idx - width] + mask[idx - width + 1] +
        mask[idx - 1] + mask[idx] + mask[idx + 1] +
        mask[idx + width - 1] + mask[idx + width] + mask[idx + width + 1];
      result[idx] = sum >= 5 ? 1 : 0;
    }
  }
  return result;
}

function dilate(mask: Uint8Array, width: number, height: number, radius: number): Uint8Array {
  let result = new Uint8Array(mask);
  for (let r = 0; r < radius; r++) {
    const next = new Uint8Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = y * width + x;
        if (result[idx]) { next[idx] = 1; continue; }
        const top = y > 0 ? result[idx - width] : 0;
        const bottom = y < height - 1 ? result[idx + width] : 0;
        const left = x > 0 ? result[idx - 1] : 0;
        const right = x < width - 1 ? result[idx + 1] : 0;
        next[idx] = top || bottom || left || right ? 1 : 0;
      }
    }
    result = next;
  }
  return result;
}

function erode(mask: Uint8Array, width: number, height: number, radius: number): Uint8Array {
  let result = new Uint8Array(mask);
  for (let r = 0; r < radius; r++) {
    const next = new Uint8Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = y * width + x;
        if (!result[idx]) { next[idx] = 0; continue; }
        const top = y > 0 ? result[idx - width] : 1;
        const bottom = y < height - 1 ? result[idx + width] : 1;
        const left = x > 0 ? result[idx - 1] : 1;
        const right = x < width - 1 ? result[idx + 1] : 1;
        next[idx] = top && bottom && left && right ? 1 : 0;
      }
    }
    result = next;
  }
  return result;
}

function morphologicalClosing(mask: Uint8Array, w: number, h: number, r: number): Uint8Array {
  return erode(dilate(mask, w, h, r), w, h, r);
}

interface BBox { x1: number; y1: number; x2: number; y2: number; }

interface ComponentResult {
  bboxes: BBox[];
  /** componentMap[i] = component ID (1-based) for foreground, 0 = background */
  componentMap: Int32Array;
}

/**
 * BFS connected components with per-pixel ID tracking.
 *
 * Each foreground pixel gets tagged with its component ID so the
 * extraction step can alpha-mask out pixels from other patches
 * that fall within the same bounding box.
 */
function findComponents(
  mask: Uint8Array,
  width: number,
  height: number,
  minArea: number,
): ComponentResult {
  const visited = new Uint8Array(width * height);
  const componentMap = new Int32Array(width * height);
  const bboxes: BBox[] = [];
  let componentId = 0;

  for (let idx = 0; idx < mask.length; idx++) {
    if (!mask[idx] || visited[idx]) continue;

    componentId++;
    const queue: number[] = [idx];
    visited[idx] = 1;
    componentMap[idx] = componentId;

    let minX = idx % width, maxX = minX;
    let minY = Math.floor(idx / width), maxY = minY;
    let area = 0;
    let head = 0;

    while (head < queue.length) {
      const cur = queue[head++];
      area++;
      const x = cur % width, y = Math.floor(cur / width);
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;

      if (y > 0) { const n = cur - width; if (mask[n] && !visited[n]) { visited[n] = 1; componentMap[n] = componentId; queue.push(n); } }
      if (y < height - 1) { const n = cur + width; if (mask[n] && !visited[n]) { visited[n] = 1; componentMap[n] = componentId; queue.push(n); } }
      if (x > 0) { const n = cur - 1; if (mask[n] && !visited[n]) { visited[n] = 1; componentMap[n] = componentId; queue.push(n); } }
      if (x < width - 1) { const n = cur + 1; if (mask[n] && !visited[n]) { visited[n] = 1; componentMap[n] = componentId; queue.push(n); } }
    }

    if (area >= minArea) bboxes.push({ x1: minX, y1: minY, x2: maxX, y2: maxY });
  }

  return { bboxes, componentMap };
}

/**
 * Extract a single patch with the component map as an alpha mask.
 *
 * Only pixels belonging to this component retain their color;
 * all other pixels within the bounding box become transparent.
 */
function extractPatch(
  img: HTMLImageElement,
  bbox: BBox,
  componentMap: Int32Array,
  componentId: number,
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

  const imageData = ctx.getImageData(0, 0, w, h);
  const pixels = imageData.data;

  for (let py = 0; py < h; py++) {
    for (let px = 0; px < w; px++) {
      const srcIdx = (y1 + py) * imgW + (x1 + px);
      if (componentMap[srcIdx] !== componentId) {
        pixels[(py * w + px) * 4 + 3] = 0; // set alpha to transparent
      }
    }
  }

  ctx.putImageData(imageData, 0, 0);
  return { blobUrl: canvas.toDataURL('image/png'), width: w, height: h };
}

/**
 * Segment irregularly-shaped fabric patches from an image.
 *
 * Each patch is extracted with a transparent background — only the
 * pixels belonging to that specific patch are visible, even if the
 * bounding box overlaps with adjacent patches.
 *
 * Returns empty array if fewer than 2 patches are found.
 */
export async function segmentFabricPatches(file: File): Promise<PatchResult[]> {
  const img = await loadImage(file);
  const { data, width, height } = getImageData(img);

  let mask = buildMask(data, width, height);
  mask = blurMask(mask, width, height);
  mask = morphologicalClosing(mask, width, height, 3);

  const minArea = Math.max(1, Math.floor((width * height) * 0.001));
  const { bboxes, componentMap } = findComponents(mask, width, height, minArea);

  if (bboxes.length < 2) return [];

  return bboxes.map((bbox, i) => {
    const patch = extractPatch(img, bbox, componentMap, i + 1, 5, width, height);
    return { index: i, blobUrl: patch.blobUrl, width: patch.width, height: patch.height };
  });
}
