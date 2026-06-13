'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import type { ChangeEvent } from 'react';
import Image from 'next/image';
import { renderDxfPreview } from '@/lib/dxf';
import type { DxfRenderedRegion } from '@/lib/dxf';
import { apiRequest } from '@/lib/api';
import { fetchHistory } from '@/lib/history';
import {
  createModelPreview,
  createPrjTemplatePreview,
  fetchDxfTemplateFile,
  fetchPrjTemplateDetail,
  pollModelPreviewTask,
} from '@/lib/prjTemplates';
import type { GeneratedDesign, MaterialWithDesigns } from '@/types/history';
import type { PrjTemplateDetail, Template } from '@/types/preview';

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

type PageState = 'loading' | 'idle' | 'error';
type ModalState = 'idle' | 'loading' | 'generating' | 'error';
type CanvasState = 'idle' | 'rendering' | 'ready' | 'error';
type DxfFileState = 'idle' | 'loading' | 'ready' | 'error';
type ModelPreviewState = 'idle' | 'generating' | 'ready' | 'error';
type BitmapSourceKind = 'dxf' | 'preview' | 'upload';

type CanvasPoint = [number, number];
type CanvasRectangle = [number, number, number, number];
type CanvasRegion = Record<string, unknown>;

interface DrawableRegion {
  id: string;
  label: string;
  region: CanvasRegion;
}

type RegionShape =
  | {
      id: string;
      label: string;
      kind: 'polygon';
      points: CanvasPoint[];
    }
  | {
      id: string;
      label: string;
      kind: 'rectangle';
      rectangle: CanvasRectangle;
    };

interface RegionPatternAssignment {
  regionId: string;
  patternUrl: string;
}

interface BitmapSource {
  id: string;
  kind: BitmapSourceKind;
  label: string;
  url: string;
  regions?: CanvasRegion[];
}

const HISTORY_PAGE_SIZE = 6;
const MIN_PREVIEW_ZOOM = 0.5;
const MAX_PREVIEW_ZOOM = 3;
const PREVIEW_ZOOM_STEP = 0.25;
const MODEL_PREVIEW_PROMPT =
  'Generate a realistic front-facing fashion model try-on image from this filled garment preview. Use a clean straight-on studio catalog pose, front view only, with the model standing naturally and facing the camera. Preserve the garment silhouette, print placement, artwork colors, and textile pattern identity. The cloth and printed pattern must wrap around the body and deform naturally with torso shape, shoulders, arms, folds, wrinkles, drape, and fabric tension; do not keep the artwork flat or pasted on. Do not use side view, back view, or three-quarter view.';

function designImageUrl(design: GeneratedDesign): string | null {
  return design.thumbnail_url || design.upscaled_url || design.image_url;
}

function isDesignSelectable(design: GeneratedDesign): boolean {
  return ['completed', 'exported'].includes(design.status) && Boolean(designImageUrl(design));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function regionsFromPayload(payload: unknown): CanvasRegion[] {
  if (Array.isArray(payload)) {
    return payload.filter(isRecord);
  }
  if (!isRecord(payload)) {
    return [];
  }

  for (const key of ['regions', 'areas', 'pieces']) {
    const value = payload[key];
    if (Array.isArray(value)) {
      return value.filter(isRecord);
    }
  }

  return [payload];
}

async function renderDxfBlobToBitmapSource(
  blob: Blob,
  id: string,
  label: string
): Promise<BitmapSource> {
  const text = await blob.text();
  const preview = renderDxfPreview(text);
  return {
    id,
    kind: 'dxf',
    label,
    url: preview.dataUrl,
    regions: preview.regions.map(dxfRegionToCanvasRegion),
  };
}

function dxfRegionToCanvasRegion(region: DxfRenderedRegion): CanvasRegion {
  return {
    name: region.label,
    points: region.points,
  };
}

function rectangleFromRegion(region: CanvasRegion, canvasWidth: number, canvasHeight: number): CanvasRectangle | null {
  const x = asNumber(region.x);
  const y = asNumber(region.y);
  const width = asNumber(region.width ?? region.w);
  const height = asNumber(region.height ?? region.h);

  if (x === null || y === null || width === null || height === null || width <= 0 || height <= 0) {
    return null;
  }

  const left = Math.max(0, Math.min(x, canvasWidth));
  const top = Math.max(0, Math.min(y, canvasHeight));
  const right = Math.max(left, Math.min(x + width, canvasWidth));
  const bottom = Math.max(top, Math.min(y + height, canvasHeight));
  return right > left && bottom > top ? [left, top, right, bottom] : null;
}

function pointFromPayload(payload: unknown): CanvasPoint | null {
  if (isRecord(payload)) {
    const x = asNumber(payload.x);
    const y = asNumber(payload.y);
    return x !== null && y !== null ? [x, y] : null;
  }
  if (Array.isArray(payload) && payload.length >= 2) {
    const x = asNumber(payload[0]);
    const y = asNumber(payload[1]);
    return x !== null && y !== null ? [x, y] : null;
  }
  return null;
}

function polygonFromRegion(region: CanvasRegion, canvasWidth: number, canvasHeight: number): CanvasPoint[] {
  const rawPoints = region.points ?? region.polygon;
  if (!Array.isArray(rawPoints)) {
    return [];
  }

  const points = rawPoints
    .map(pointFromPayload)
    .filter((point): point is CanvasPoint => point !== null)
    .map(([x, y]) => [Math.max(0, Math.min(x, canvasWidth)), Math.max(0, Math.min(y, canvasHeight))] as CanvasPoint);

  return points.length >= 3 ? points : [];
}

function getDrawableRegions(regionsPayload: unknown, canvasWidth: number, canvasHeight: number): DrawableRegion[] {
  const regions = regionsFromPayload(regionsPayload);
  const drawableRegions = regions.length > 0
    ? regions
    : [{ x: 0, y: 0, width: canvasWidth, height: canvasHeight }];

  return drawableRegions.map((region, index) => ({
    id: `region-${index}`,
    label: typeof region.name === 'string' && region.name.trim().length > 0
      ? region.name.trim()
      : `区域 ${index + 1}`,
    region,
  }));
}

function buildRegionShapes(regionsPayload: unknown, canvasWidth: number, canvasHeight: number): RegionShape[] {
  const shapes: RegionShape[] = [];

  for (const item of getDrawableRegions(regionsPayload, canvasWidth, canvasHeight)) {
    const polygon = polygonFromRegion(item.region, canvasWidth, canvasHeight);
    if (polygon.length > 0) {
      shapes.push({ id: item.id, label: item.label, kind: 'polygon', points: polygon });
      continue;
    }

    const rectangle = rectangleFromRegion(item.region, canvasWidth, canvasHeight);
    if (rectangle) {
      shapes.push({ id: item.id, label: item.label, kind: 'rectangle', rectangle });
    }
  }

  return shapes;
}

function canvasSafeImageUrl(src: string): string {
  if (src.startsWith('data:') || src.startsWith('blob:')) {
    return src;
  }

  if (src.startsWith('/')) {
    return src;
  }

  try {
    const url = new URL(src);
    if (typeof window !== 'undefined' && url.origin === window.location.origin) {
      return src;
    }
    return `/api/image-proxy?url=${encodeURIComponent(src)}`;
  } catch {
    return src;
  }
}

function loadCanvasImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new window.Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('图片加载失败'));
    image.src = canvasSafeImageUrl(src);
  });
}

function drawTiledPattern(
  context: CanvasRenderingContext2D,
  patternImage: HTMLImageElement,
  canvasWidth: number,
  canvasHeight: number
) {
  let patternWidth = patternImage.naturalWidth;
  let patternHeight = patternImage.naturalHeight;

  if (patternWidth > canvasWidth || patternHeight > canvasHeight) {
    const scale = Math.min(canvasWidth / patternWidth, canvasHeight / patternHeight);
    patternWidth = Math.max(1, Math.floor(patternWidth * scale));
    patternHeight = Math.max(1, Math.floor(patternHeight * scale));
  }

  for (let y = 0; y < canvasHeight; y += patternHeight) {
    for (let x = 0; x < canvasWidth; x += patternWidth) {
      context.drawImage(patternImage, x, y, patternWidth, patternHeight);
    }
  }
}

async function renderTemplatePreviewInBrowser(
  templateUrl: string,
  assignments: RegionPatternAssignment[],
  regionsPayload: unknown
): Promise<string> {
  const templateImage = await loadCanvasImage(templateUrl);
  const patternEntries = await Promise.all(
    assignments.map(async (assignment) => [assignment.regionId, await loadCanvasImage(assignment.patternUrl)] as const)
  );
  const patternImages = new Map(patternEntries);

  const canvas = document.createElement('canvas');
  canvas.width = templateImage.naturalWidth;
  canvas.height = templateImage.naturalHeight;

  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('浏览器不支持 Canvas 渲染');
  }

  context.drawImage(templateImage, 0, 0, canvas.width, canvas.height);
  const drawableRegions = getDrawableRegions(regionsPayload, canvas.width, canvas.height);

  for (const item of drawableRegions) {
    const patternImage = patternImages.get(item.id);
    if (!patternImage) {
      continue;
    }
    context.save();
    context.beginPath();
    const polygon = polygonFromRegion(item.region, canvas.width, canvas.height);
    if (polygon.length > 0) {
      context.moveTo(polygon[0][0], polygon[0][1]);
      for (const [x, y] of polygon.slice(1)) {
        context.lineTo(x, y);
      }
      context.closePath();
    } else {
      const rectangle = rectangleFromRegion(item.region, canvas.width, canvas.height);
      if (!rectangle) {
        context.restore();
        continue;
      }
      const [left, top, right, bottom] = rectangle;
      context.rect(left, top, right - left, bottom - top);
    }
    context.clip();
    drawTiledPattern(context, patternImage, canvas.width, canvas.height);
    context.restore();
  }

  return canvas.toDataURL('image/png');
}

async function imageUrlToPngDataUrl(sourceUrl: string): Promise<string> {
  if (sourceUrl.startsWith('data:image/png;')) {
    return sourceUrl;
  }

  const image = await loadCanvasImage(sourceUrl);
  const canvas = document.createElement('canvas');
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;

  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('浏览器不支持 Canvas 导出');
  }

  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/png');
}

export default function TemplatesTab() {
  const dxfFileInputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<PageState>('loading');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [selectedTemplateDetail, setSelectedTemplateDetail] = useState<PrjTemplateDetail | null>(null);
  const [modalState, setModalState] = useState<ModalState>('idle');
  const [modalError, setModalError] = useState<string | null>(null);
  const [historyMaterials, setHistoryMaterials] = useState<MaterialWithDesigns[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPages, setHistoryPages] = useState(0);
  const [selectedDesignId, setSelectedDesignId] = useState<number | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [canvasState, setCanvasState] = useState<CanvasState>('idle');
  const [canvasError, setCanvasError] = useState<string | null>(null);
  const [dxfFileState, setDxfFileState] = useState<DxfFileState>('idle');
  const [dxfFileError, setDxfFileError] = useState<string | null>(null);
  const [dxfBitmapSources, setDxfBitmapSources] = useState<BitmapSource[]>([]);
  const [selectedBitmapSourceId, setSelectedBitmapSourceId] = useState<string | null>(null);
  const [localDxfFileName, setLocalDxfFileName] = useState<string | null>(null);
  const [uploadedBitmapSource, setUploadedBitmapSource] = useState<BitmapSource | null>(null);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [regionDesignIds, setRegionDesignIds] = useState<Record<string, number>>({});
  const [selectedBitmapSize, setSelectedBitmapSize] = useState<{ width: number; height: number } | null>(null);
  const [previewZoom, setPreviewZoom] = useState(1);
  const [modelPreviewState, setModelPreviewState] = useState<ModelPreviewState>('idle');
  const [modelPreviewError, setModelPreviewError] = useState<string | null>(null);
  const [modelPreviewUrl, setModelPreviewUrl] = useState<string | null>(null);

  const bitmapSources = useMemo(() => {
    const sources: BitmapSource[] = [];
    const templatePreviewUrl = selectedTemplateDetail?.preview_url ?? selectedTemplate?.preview_url ?? null;
    if (templatePreviewUrl) {
      sources.push({
        id: 'template-preview',
        kind: 'preview',
        label: '模板预览图',
        url: templatePreviewUrl,
      });
    }

    sources.push(...dxfBitmapSources);

    if (uploadedBitmapSource) {
      sources.push(uploadedBitmapSource);
    }

    return sources;
  }, [dxfBitmapSources, selectedTemplate, selectedTemplateDetail, uploadedBitmapSource]);

  const selectedBitmapSource = useMemo(() => {
    if (!selectedBitmapSourceId) {
      return bitmapSources[0] ?? null;
    }

    return bitmapSources.find((source) => source.id === selectedBitmapSourceId) ?? bitmapSources[0] ?? null;
  }, [bitmapSources, selectedBitmapSourceId]);

  const activeRegionPayload = useMemo(() => {
    const templateRegions = selectedTemplateDetail?.regions;
    if (regionsFromPayload(templateRegions).length > 0) {
      return templateRegions;
    }

    return selectedBitmapSource?.regions ?? templateRegions;
  }, [selectedBitmapSource?.regions, selectedTemplateDetail?.regions]);

  const regionShapes = useMemo(() => {
    if (!selectedBitmapSize) {
      return [];
    }

    return buildRegionShapes(
      activeRegionPayload,
      selectedBitmapSize.width,
      selectedBitmapSize.height
    );
  }, [activeRegionPayload, selectedBitmapSize]);

  const selectedRegion = useMemo(() => {
    if (!selectedRegionId) {
      return null;
    }

    return regionShapes.find((region) => region.id === selectedRegionId) ?? null;
  }, [regionShapes, selectedRegionId]);

  const regionAssignments = useMemo(() => {
    return Object.entries(regionDesignIds).flatMap(([regionId, designId]) => {
      for (const material of historyMaterials) {
        const design = material.designs.find((item) => item.id === designId);
        const patternUrl = design ? designImageUrl(design) : null;
        if (patternUrl) {
          return [{ regionId, patternUrl } satisfies RegionPatternAssignment];
        }
      }

      return [];
    });
  }, [historyMaterials, regionDesignIds]);

  const fallbackDesignId = useMemo(() => {
    if (selectedDesignId !== null) {
      return selectedDesignId;
    }

    const assignedDesignIds = Object.values(regionDesignIds);
    return assignedDesignIds.length > 0 ? assignedDesignIds[0] : null;
  }, [regionDesignIds, selectedDesignId]);

  const currentPreviewSourceUrl = previewUrl ?? selectedBitmapSource?.url ?? null;

  useEffect(() => {
    async function loadTemplates() {
      setState('loading');
      setError(null);

      try {
        const data = await apiRequest<PaginatedResponse<Template>>('/api/prj-templates');
        setTemplates(data.items);
        setState('idle');
      } catch (err) {
        console.error('获取模板时出错:', err);
        setError(err instanceof Error ? err.message : '获取模板失败');
        setState('error');
      }
    }

    loadTemplates();
  }, []);

  useEffect(() => {
    if (!selectedTemplate) {
      return;
    }

    let cancelled = false;

    async function loadHistory() {
      setModalState('loading');
      setModalError(null);

      try {
        const response = await fetchHistory(historyPage, HISTORY_PAGE_SIZE);
        if (!cancelled) {
          setHistoryMaterials(response.items);
          setHistoryPages(response.pages);
          setModalState('idle');
        }
      } catch (err) {
        if (!cancelled) {
          setModalError(err instanceof Error ? err.message : '加载设计历史失败');
          setModalState('error');
        }
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [selectedTemplate, historyPage]);

  useEffect(() => {
    if (!selectedTemplate) {
      return;
    }

    let cancelled = false;
    const templateId = selectedTemplate.id;

    async function loadTemplateDetail() {
      try {
        const detail = await fetchPrjTemplateDetail(templateId);
        if (!cancelled) {
          setSelectedTemplateDetail(detail);
        }
      } catch (err) {
        if (!cancelled) {
          setSelectedTemplateDetail(null);
          setCanvasError(err instanceof Error ? err.message : '加载模板区域失败');
        }
      }
    }

    loadTemplateDetail();

    return () => {
      cancelled = true;
    };
  }, [selectedTemplate]);

  useEffect(() => {
    if (localDxfFileName) {
      return;
    }

    const dxfPath = selectedTemplateDetail?.dxf_path ?? selectedTemplateDetail?.prj_path;
    if (typeof dxfPath !== 'string' || dxfPath.length === 0) {
      return;
    }

    let cancelled = false;
    const dxfUrl = dxfPath;

    async function loadDxfFile() {
      setDxfFileState('loading');
      setDxfFileError(null);
      setDxfBitmapSources([]);

      try {
        const dxfFile = await fetchDxfTemplateFile(dxfUrl);
        const source = await renderDxfBlobToBitmapSource(dxfFile, 'remote-dxf', '远程 DXF 图纸');

        if (!cancelled) {
          setDxfBitmapSources([source]);
          setSelectedBitmapSourceId(source.id);
          setDxfFileState('ready');
          setRegionDesignIds({});
          setSelectedRegionId(null);
          setSelectedDesignId(null);
          setPreviewZoom(1);
        }
      } catch (err) {
        if (!cancelled) {
          setDxfBitmapSources([]);
          setDxfFileError(err instanceof Error ? err.message : '读取 DXF 文件失败');
          setDxfFileState('error');
        }
      }
    }

    loadDxfFile();

    return () => {
      cancelled = true;
    };
  }, [localDxfFileName, selectedTemplateDetail?.dxf_path, selectedTemplateDetail?.prj_path]);

  useEffect(() => {
    return () => {
      if (uploadedBitmapSource?.url.startsWith('blob:')) {
        URL.revokeObjectURL(uploadedBitmapSource.url);
      }
    };
  }, [uploadedBitmapSource]);

  useEffect(() => {
    return () => {
      for (const source of dxfBitmapSources) {
        if (source.url.startsWith('blob:')) {
          URL.revokeObjectURL(source.url);
        }
      }
    };
  }, [dxfBitmapSources]);

  useEffect(() => {
    const sourceUrl = selectedBitmapSource?.url ?? null;
    if (!sourceUrl) {
      setSelectedBitmapSize(null);
      setSelectedRegionId(null);
      return;
    }

    let cancelled = false;

    async function loadBitmapSize() {
      try {
        const image = await loadCanvasImage(sourceUrl);
        if (!cancelled) {
          setSelectedBitmapSize({ width: image.naturalWidth, height: image.naturalHeight });
        }
      } catch {
        if (!cancelled) {
          setSelectedBitmapSize(null);
        }
      }
    }

    loadBitmapSize();

    return () => {
      cancelled = true;
    };
  }, [selectedBitmapSource?.url]);

  useEffect(() => {
    if (selectedRegionId && !regionShapes.some((region) => region.id === selectedRegionId)) {
      setSelectedRegionId(null);
    }
  }, [regionShapes, selectedRegionId]);

  useEffect(() => {
    const templateImageUrl = selectedBitmapSource?.url ?? null;

    if (!templateImageUrl || regionAssignments.length === 0) {
      setPreviewUrl(null);
      setCanvasState('idle');
      return;
    }

    let cancelled = false;
    const templateSrc: string = templateImageUrl;

    async function renderPreview() {
      setCanvasState('rendering');
      setCanvasError(null);

      try {
        const renderedUrl = await renderTemplatePreviewInBrowser(
          templateSrc,
          regionAssignments,
          activeRegionPayload
        );
        if (!cancelled) {
          setPreviewUrl(renderedUrl);
          setCanvasState('ready');
        }
      } catch (err) {
        if (!cancelled) {
          setPreviewUrl(null);
          setCanvasError(err instanceof Error ? err.message : '浏览器预览渲染失败');
          setCanvasState('error');
        }
      }
    }

    renderPreview();

    return () => {
      cancelled = true;
    };
  }, [activeRegionPayload, regionAssignments, selectedBitmapSource]);

  function resetModelPreview() {
    setModelPreviewState('idle');
    setModelPreviewError(null);
    setModelPreviewUrl(null);
  }

  function selectRegion(regionId: string) {
    setSelectedRegionId(regionId);
    const assignedDesignId = regionDesignIds[regionId];
    setSelectedDesignId(assignedDesignId ?? null);
  }

  function selectDesign(designId: number) {
    setSelectedDesignId(designId);
    if (selectedRegionId) {
      setRegionDesignIds((current) => ({ ...current, [selectedRegionId]: designId }));
    }
    setPreviewUrl(null);
    setCanvasState('idle');
    setCanvasError(null);
    resetModelPreview();
  }

  function selectBitmapSource(sourceId: string) {
    setSelectedBitmapSourceId(sourceId);
    setPreviewUrl(null);
    setCanvasState('idle');
    setCanvasError(null);
    setPreviewZoom(1);
    resetModelPreview();
  }

  function removeSelectedRegionFill() {
    if (!selectedRegionId) {
      return;
    }

    setRegionDesignIds((current) => {
      const next = { ...current };
      delete next[selectedRegionId];
      return next;
    });
    setSelectedDesignId(null);
    setPreviewUrl(null);
    setCanvasState('idle');
    setCanvasError(null);
    resetModelPreview();
  }

  function resetAllRegionFills() {
    setRegionDesignIds({});
    setSelectedDesignId(null);
    setSelectedRegionId(null);
    setPreviewUrl(null);
    setCanvasState('idle');
    setCanvasError(null);
    resetModelPreview();
  }

  function zoomPreview(delta: number) {
    setPreviewZoom((current) => Math.max(MIN_PREVIEW_ZOOM, Math.min(MAX_PREVIEW_ZOOM, current + delta)));
  }

  function resetPreviewZoom() {
    setPreviewZoom(1);
  }

  async function handleDxfUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (!file.name.toLowerCase().endsWith('.dxf')) {
      setDxfFileState('error');
      setDxfFileError('请选择 .dxf 模板文件');
      event.target.value = '';
      return;
    }

    setDxfFileState('loading');
    setDxfFileError(null);
    setDxfBitmapSources([]);
    setLocalDxfFileName(file.name);
    setPreviewUrl(null);
    setCanvasState('idle');
    setCanvasError(null);

    try {
      const source = await renderDxfBlobToBitmapSource(file, 'local-dxf', `本地 DXF：${file.name}`);

      setDxfBitmapSources([source]);
      setSelectedBitmapSourceId(source.id);
      setDxfFileState('ready');
      setRegionDesignIds({});
      setSelectedRegionId(null);
      setSelectedDesignId(null);
      setPreviewZoom(1);
      resetModelPreview();
    } catch (err) {
      setDxfBitmapSources([]);
      setDxfFileError(err instanceof Error ? err.message : '读取本地 DXF 文件失败');
      setDxfFileState('error');
    } finally {
      event.target.value = '';
    }
  }

  function handleBitmapUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (!file.type.startsWith('image/')) {
      setCanvasError('请选择 PNG、JPG、WebP 等图片文件作为模板位图');
      event.target.value = '';
      return;
    }

    const uploadedUrl = URL.createObjectURL(file);
    const source: BitmapSource = {
      id: 'uploaded-bitmap',
      kind: 'upload',
      label: `本地位图：${file.name}`,
      url: uploadedUrl,
    };

    setUploadedBitmapSource(source);
    setSelectedBitmapSourceId(source.id);
    setRegionDesignIds({});
    setSelectedRegionId(null);
    setSelectedDesignId(null);
    setPreviewUrl(null);
    setCanvasState('idle');
    setCanvasError(null);
    setPreviewZoom(1);
    resetModelPreview();
    event.target.value = '';
  }

  function openTemplateModal(template: Template) {
    setSelectedTemplate(template);
    setSelectedTemplateDetail(null);
    setHistoryPage(1);
    setHistoryPages(0);
    setSelectedDesignId(null);
    setSelectedRegionId(null);
    setRegionDesignIds({});
    setPreviewUrl(null);
    setModalError(null);
    setCanvasState('idle');
    setCanvasError(null);
    setDxfFileState('idle');
    setDxfFileError(null);
    setDxfBitmapSources([]);
    setSelectedBitmapSourceId(null);
    setLocalDxfFileName(null);
    setUploadedBitmapSource(null);
    setSelectedBitmapSize(null);
    setPreviewZoom(1);
    resetModelPreview();
  }

  function closeTemplateModal() {
    setSelectedTemplate(null);
    setSelectedTemplateDetail(null);
    setSelectedDesignId(null);
    setSelectedRegionId(null);
    setRegionDesignIds({});
    setPreviewUrl(null);
    setModalError(null);
    setCanvasState('idle');
    setCanvasError(null);
    setDxfFileState('idle');
    setDxfFileError(null);
    setDxfBitmapSources([]);
    setSelectedBitmapSourceId(null);
    setLocalDxfFileName(null);
    setUploadedBitmapSource(null);
    setSelectedBitmapSize(null);
    setPreviewZoom(1);
    setHistoryMaterials([]);
    resetModelPreview();
  }

  async function handleGeneratePreview() {
    if (!selectedTemplate || fallbackDesignId === null) {
      return;
    }

    setModalState('generating');
    setModalError(null);

    try {
      const response = await createPrjTemplatePreview(selectedTemplate.id, fallbackDesignId);
      setPreviewUrl(response.preview_url);
      resetModelPreview();
      setModalState('idle');
    } catch (err) {
      setModalError(err instanceof Error ? err.message : '生成服装预览失败');
      setModalState('error');
    }
  }

  async function handleCreateModelPreview() {
    if (!currentPreviewSourceUrl) {
      return;
    }

    setModelPreviewState('generating');
    setModelPreviewError(null);

    try {
      const imageDataUrl = await imageUrlToPngDataUrl(currentPreviewSourceUrl);
      const response = await createModelPreview(
        imageDataUrl,
        selectedTemplate?.id,
        MODEL_PREVIEW_PROMPT
      );
      const task = await pollModelPreviewTask(response.task_id);
      const previewUrl = task.result?.preview_url;
      if (!previewUrl) {
        throw new Error('AI 模特预览任务完成但没有返回预览图');
      }
      setModelPreviewUrl(previewUrl);
      setModelPreviewState('ready');
      setModelPreviewError(task.result?.method === 'fallback' ? 'AI 暂不可用，已使用后端兜底生成预览。' : null);
    } catch (err) {
      setModelPreviewError(err instanceof Error ? err.message : '生成模特预览图失败');
      setModelPreviewState('error');
    }
  }
   
  return (
    <div className="py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {state === 'loading' && (
          <div className="flex items-center justify-center py-12">
            <div className="relative h-12 w-12">
              <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
              <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
            </div>
          </div>
        )}

        {state === 'error' && error && (
          <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4">
            <div className="flex items-start gap-3">
              <svg
                className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <div className="flex-1">
                <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                  错误
                </h3>
                <p className="mt-1 text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            </div>
          </div>
        )}

        {state === 'idle' && templates.length === 0 && (
          <div className="text-center py-12 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
            <p className="text-zinc-600 dark:text-zinc-400">暂无可用模板。</p>
          </div>
        )}

        {state === 'idle' && templates.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {templates.map((template) => (
              <button
                key={template.id} 
                type="button"
                onClick={() => openTemplateModal(template)}
                className="text-left border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 rounded-lg p-4 hover:shadow-lg dark:hover:shadow-zinc-800/50 transition-shadow focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <div className="relative w-full h-64 bg-zinc-50 dark:bg-zinc-800 rounded mb-3 overflow-hidden">
                  {template.preview_url ? (
                    <Image
                      src={template.preview_url}
                      alt={template.name}
                      fill
                      unoptimized
                      className="object-contain"
                      sizes="(max-width: 768px) 100vw, 33vw"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-zinc-400">
                      无预览图
                    </div>
                  )}
                </div>
                <h3 className="mt-3 font-medium text-lg text-zinc-950 dark:text-zinc-50">{template.name}</h3>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 capitalize">{template.category}</p>
                {template.is_builtin && (
                  <span className="inline-block mt-2 px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded">
                    内置模板
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-h-[90vh] w-full max-w-6xl overflow-hidden rounded-xl bg-white dark:bg-zinc-950 shadow-2xl border border-zinc-200 dark:border-zinc-800">
            <div className="flex items-start justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 px-6 py-4">
              <div>
                <h2 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50">
                  选择图案生成服装预览
                </h2>
                <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                  模板：{selectedTemplate.name} · 从设计历史中选择一个已完成图案，浏览器会按模板位图区域即时填充。
                </p>
              </div>
              <button
                type="button"
                onClick={closeTemplateModal}
                className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 dark:text-zinc-400"
                aria-label="关闭"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="grid max-h-[calc(90vh-82px)] grid-cols-1 overflow-y-auto lg:grid-cols-[1.3fr_0.9fr]">
              <div className="border-b border-zinc-200 dark:border-zinc-800 p-6 lg:border-b-0 lg:border-r">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h3 className="font-medium text-zinc-950 dark:text-zinc-50">设计历史</h3>
                    <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                      {selectedRegion
                        ? `当前填充：${selectedRegion.label}，请选择一个素材。`
                        : '点击右侧区域可局部填充；未选区域时选择素材会用于服务端兜底。'}
                    </p>
                  </div>
                  {historyPages > 1 && (
                    <div className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
                      <button
                        type="button"
                        onClick={() => setHistoryPage((page) => Math.max(1, page - 1))}
                        disabled={historyPage <= 1 || modalState === 'loading'}
                        className="rounded border border-zinc-200 px-2 py-1 disabled:opacity-50 dark:border-zinc-700"
                      >
                        上一页
                      </button>
                      <span>{historyPage} / {historyPages}</span>
                      <button
                        type="button"
                        onClick={() => setHistoryPage((page) => Math.min(historyPages, page + 1))}
                        disabled={historyPage >= historyPages || modalState === 'loading'}
                        className="rounded border border-zinc-200 px-2 py-1 disabled:opacity-50 dark:border-zinc-700"
                      >
                        下一页
                      </button>
                    </div>
                  )}
                </div>

                {modalState === 'loading' && (
                  <div className="flex items-center justify-center py-16 text-zinc-500 dark:text-zinc-400">
                    加载设计历史中...
                  </div>
                )}

                {modalState === 'error' && modalError && (
                  <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                    {modalError}
                  </div>
                )}

                {modalState !== 'loading' && historyMaterials.length === 0 && (
                  <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
                    暂无可选择的设计历史，请先生成图案。
                  </div>
                )}

                {modalState !== 'loading' && historyMaterials.length > 0 && (
                  <div className="space-y-5">
                    {historyMaterials.map((material) => (
                      <div key={material.id}>
                        <div className="mb-2 flex items-center justify-between gap-3">
                          <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-200">
                            {material.original_filename || `素材 #${material.id}`}
                          </p>
                          <span className="text-xs text-zinc-500 dark:text-zinc-400">
                            {material.designs.length} 个结果
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                          {material.designs.map((design) => {
                            const imageUrl = designImageUrl(design);
                            const selectable = isDesignSelectable(design);
                            const selected = selectedRegionId
                              ? regionDesignIds[selectedRegionId] === design.id
                              : selectedDesignId === design.id;
                            const canAssign = selectable;

                            return (
                              <button
                                key={design.id}
                                type="button"
                                onClick={() => canAssign && selectDesign(design.id)}
                                disabled={!canAssign}
                                title={selectedRegionId ? '填充当前选中区域' : '未选区域时作为服务端兜底素材'}
                                className={`overflow-hidden rounded-lg border text-left transition ${selected ? 'border-blue-500 ring-2 ring-blue-500' : 'border-zinc-200 dark:border-zinc-700'} ${canAssign ? 'hover:border-blue-400' : 'cursor-not-allowed opacity-50'}`}
                              >
                                <div className="aspect-square bg-zinc-100 dark:bg-zinc-800">
                                  {imageUrl ? (
                                    <div className="relative h-full w-full">
                                      <Image
                                        src={imageUrl}
                                        alt={`Design variant ${design.variant_index + 1}`}
                                        fill
                                        unoptimized
                                        className="object-cover"
                                        sizes="(max-width: 640px) 50vw, 180px"
                                      />
                                    </div>
                                  ) : (
                                    <div className="flex h-full items-center justify-center text-xs text-zinc-400">
                                      无图片
                                    </div>
                                  )}
                                </div>
                                <div className="flex items-center justify-between gap-2 p-2 text-xs">
                                  <span className="text-zinc-700 dark:text-zinc-300">#{design.variant_index + 1}</span>
                                  <span className="text-zinc-500 dark:text-zinc-400">
                                    {selected ? '已选' : design.status}
                                  </span>
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="p-6">
                <h3 className="mb-4 font-medium text-zinc-950 dark:text-zinc-50">浏览器预览</h3>
                <div className="mb-4 space-y-3 rounded-lg border border-zinc-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-950">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-zinc-900 dark:text-zinc-100">DXF 文件</p>
                      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                        {localDxfFileName
                          ? `已读取本地 DXF：${localDxfFileName}`
                          : selectedTemplateDetail?.dxf_path ?? selectedTemplateDetail?.prj_path
                          ? dxfFileState === 'loading'
                            ? '正在下载并渲染 DXF 文件...'
                            : dxfBitmapSources.length > 0
                            ? '已渲染 DXF 图纸'
                            : 'DXF 图纸尚未渲染'
                          : '该模板没有上传 DXF 文件'}
                      </p>
                    </div>
                    {(selectedTemplateDetail?.dxf_path ?? selectedTemplateDetail?.prj_path) && (
                      <a
                        href={selectedTemplateDetail.dxf_path ?? selectedTemplateDetail.prj_path ?? undefined}
                        download
                        className="shrink-0 rounded-md border border-zinc-200 px-2.5 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                      >
                        下载 DXF
                      </a>
                    )}
                  </div>

                  <div className="space-y-2">
                    <button
                      type="button"
                      onClick={() => dxfFileInputRef.current?.click()}
                      className="flex w-full items-center justify-center rounded-md border border-dashed border-zinc-300 px-3 py-2 text-xs text-zinc-600 hover:border-blue-400 hover:text-blue-600 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-blue-500 dark:hover:text-blue-300"
                    >
                      选择本地 DXF 文件并直接渲染
                    </button>
                    <input
                      ref={dxfFileInputRef}
                      type="file"
                      accept=".dxf,application/dxf,application/x-dxf,text/plain,application/octet-stream"
                      onChange={handleDxfUpload}
                      className="hidden"
                    />
                    {dxfFileState === 'loading' && (
                      <p className="text-xs text-blue-600 dark:text-blue-300">
                        正在渲染 DXF：{localDxfFileName ?? '本地文件'}...
                      </p>
                    )}
                    {localDxfFileName && dxfFileState !== 'loading' && (
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        当前本地 DXF：{localDxfFileName}
                      </p>
                    )}
                  </div>

                  {dxfFileState === 'error' && dxfFileError && (
                    <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
                      {dxfFileError}。仍可使用模板预览图或上传本地位图。
                    </div>
                  )}

                  {dxfFileState === 'ready' && dxfFileError && (
                    <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
                      {dxfFileError}。可以改用模板预览图或上传本地位图作为模板底图。
                    </div>
                  )}

                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                      选择模板底图来源
                    </p>
                    <div className="grid grid-cols-1 gap-2">
                      {bitmapSources.length === 0 && (
                        <div className="rounded-md border border-dashed border-zinc-300 px-3 py-2 text-xs text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
                          当前模板没有可用底图。请上传 DXF、上传本地位图，或在后台为模板配置预览图。
                        </div>
                      )}
                      {bitmapSources.map((source) => (
                        <button
                          key={source.id}
                          type="button"
                          onClick={() => selectBitmapSource(source.id)}
                          className={`flex items-center justify-between rounded-md border px-3 py-2 text-left text-xs transition ${selectedBitmapSource?.id === source.id ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-200' : 'border-zinc-200 text-zinc-700 hover:border-blue-300 dark:border-zinc-700 dark:text-zinc-300'}`}
                        >
                          <span className="flex min-w-0 items-center gap-2">
                            <span
                              aria-hidden="true"
                              className="h-10 w-10 shrink-0 rounded border border-zinc-200 bg-zinc-100 bg-cover bg-center dark:border-zinc-700 dark:bg-zinc-800"
                              style={{ backgroundImage: `url(${source.url})` }}
                            />
                            <span className="truncate">{source.label}</span>
                          </span>
                          <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] uppercase text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                            {source.kind === 'dxf' ? 'DXF' : source.kind === 'upload' ? '本地' : '预览'}
                          </span>
                        </button>
                      ))}
                    </div>
                    <label className="mt-2 flex cursor-pointer items-center justify-center rounded-md border border-dashed border-zinc-300 px-3 py-2 text-xs text-zinc-600 hover:border-blue-400 hover:text-blue-600 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-blue-500 dark:hover:text-blue-300">
                      上传本地位图作为模板底图
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleBitmapUpload}
                        className="sr-only"
                      />
                    </label>
                  </div>
                </div>
                <div className="mb-3 rounded-lg border border-zinc-200 bg-white p-3 text-xs dark:border-zinc-800 dark:bg-zinc-950">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-zinc-600 dark:text-zinc-400">
                      {selectedRegion
                        ? `已选中 ${selectedRegion.label}`
                        : regionShapes.length > 0
                        ? '点击下方 DXF 区域后选择素材填充'
                        : '等待 DXF 区域信息'}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => zoomPreview(-PREVIEW_ZOOM_STEP)}
                        disabled={previewZoom <= MIN_PREVIEW_ZOOM}
                        className="rounded border border-zinc-200 px-2 py-1 disabled:opacity-50 dark:border-zinc-700"
                      >
                        缩小
                      </button>
                      <span className="min-w-12 text-center text-zinc-500 dark:text-zinc-400">
                        {Math.round(previewZoom * 100)}%
                      </span>
                      <button
                        type="button"
                        onClick={() => zoomPreview(PREVIEW_ZOOM_STEP)}
                        disabled={previewZoom >= MAX_PREVIEW_ZOOM}
                        className="rounded border border-zinc-200 px-2 py-1 disabled:opacity-50 dark:border-zinc-700"
                      >
                        放大
                      </button>
                      <button
                        type="button"
                        onClick={resetPreviewZoom}
                        className="rounded border border-zinc-200 px-2 py-1 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                      >
                        重置缩放
                      </button>
                      <button
                        type="button"
                        onClick={removeSelectedRegionFill}
                        disabled={!selectedRegionId || !regionDesignIds[selectedRegionId]}
                        className="rounded border border-zinc-200 px-2 py-1 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                      >
                        清除当前区域
                      </button>
                      <button
                        type="button"
                        onClick={resetAllRegionFills}
                        disabled={Object.keys(regionDesignIds).length === 0}
                        className="rounded border border-zinc-200 px-2 py-1 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                      >
                        重置填充
                      </button>
                    </div>
                  </div>
                </div>

                <div className="mb-4 overflow-auto rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900">
                  <div
                    className="relative min-w-full"
                    style={{
                      width: `${previewZoom * 100}%`,
                      aspectRatio: selectedBitmapSize ? `${selectedBitmapSize.width} / ${selectedBitmapSize.height}` : '4 / 5',
                    }}
                  >
                    {previewUrl || selectedBitmapSource ? (
                      <>
                        <div
                          aria-label={previewUrl ? `${selectedTemplate.name} 预览` : selectedBitmapSource?.label}
                          className={`absolute inset-0 bg-contain bg-center bg-no-repeat ${previewUrl ? '' : 'opacity-70'}`}
                          style={{ backgroundImage: `url(${previewUrl ?? selectedBitmapSource?.url})` }}
                        />
                        {selectedBitmapSize && regionShapes.length > 0 && (
                          <svg
                            className="absolute inset-0 h-full w-full"
                            viewBox={`0 0 ${selectedBitmapSize.width} ${selectedBitmapSize.height}`}
                            role="img"
                            aria-label="可点击填充区域"
                          >
                            {regionShapes.map((region) => {
                              const isSelected = selectedRegionId === region.id;
                              const isAssigned = Boolean(regionDesignIds[region.id]);
                              const fill = isSelected
                                ? 'rgba(37, 99, 235, 0.28)'
                                : isAssigned
                                ? 'rgba(16, 185, 129, 0.2)'
                                : 'rgba(245, 158, 11, 0.12)';
                              const stroke = isSelected ? '#2563eb' : isAssigned ? '#10b981' : '#f59e0b';

                              return region.kind === 'polygon' ? (
                                <polygon
                                  key={region.id}
                                  points={region.points.map(([x, y]) => `${x},${y}`).join(' ')}
                                  fill={fill}
                                  stroke={stroke}
                                  strokeWidth={isSelected ? 4 : 2}
                                  className="cursor-pointer transition hover:fill-blue-500/25"
                                  onClick={() => selectRegion(region.id)}
                                />
                              ) : (
                                <rect
                                  key={region.id}
                                  x={region.rectangle[0]}
                                  y={region.rectangle[1]}
                                  width={region.rectangle[2] - region.rectangle[0]}
                                  height={region.rectangle[3] - region.rectangle[1]}
                                  fill={fill}
                                  stroke={stroke}
                                  strokeWidth={isSelected ? 4 : 2}
                                  className="cursor-pointer transition hover:fill-blue-500/25"
                                  onClick={() => selectRegion(region.id)}
                                />
                              );
                            })}
                          </svg>
                        )}
                        {canvasState === 'rendering' && (
                          <div className="absolute inset-0 flex items-center justify-center bg-white/70 text-sm text-zinc-600 dark:bg-zinc-950/70 dark:text-zinc-300">
                            浏览器渲染中...
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="flex h-full items-center justify-center text-zinc-400">
                        等待模板位图
                      </div>
                    )}
                  </div>
                </div>

                {canvasState === 'ready' && (
                  <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-300">
                    已在浏览器中按已选择区域完成填充预览。
                  </div>
                )}

                {canvasState === 'error' && canvasError && (
                  <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
                    浏览器渲染失败：{canvasError}。可以使用下方服务端兜底生成。
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleGeneratePreview}
                  disabled={fallbackDesignId === null || modalState === 'generating'}
                  className="w-full rounded-lg bg-zinc-950 px-4 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-950 dark:hover:bg-zinc-200"
                >
                  {modalState === 'generating' ? '服务端生成中...' : '服务端兜底生成预览'}
                </button>
                <div className="mt-3 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-zinc-950 dark:text-zinc-50">模特预览图</p>
                      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                        异步提交 AI 任务生成正面模特穿着效果图；AI 不可用时自动兜底。
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={handleCreateModelPreview}
                      disabled={!currentPreviewSourceUrl || modelPreviewState === 'generating'}
                      className="shrink-0 rounded-md bg-blue-600 px-3 py-2 text-xs font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {modelPreviewState === 'generating' ? 'AI 任务生成中...' : 'AI 生成正面模特预览'}
                    </button>
                  </div>

                  {modelPreviewState === 'ready' && modelPreviewError && (
                    <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
                      {modelPreviewError}
                    </div>
                  )}

                  {modelPreviewState === 'error' && modelPreviewError && (
                    <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                      {modelPreviewError}
                    </div>
                  )}

                  {modelPreviewUrl && (
                    <div className="mt-3 overflow-hidden rounded-md border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900">
                      <div className="relative aspect-[3/4] w-full">
                        <Image
                          src={modelPreviewUrl}
                          alt="模特预览图"
                          fill
                          unoptimized
                          className="object-contain"
                          sizes="(max-width: 1024px) 100vw, 360px"
                        />
                      </div>
                    </div>
                  )}
                </div>
                <p className="mt-3 text-xs leading-5 text-zinc-500 dark:text-zinc-400">
                  浏览器会先下载 DXF 文件并直接渲染成模板底图；你也可以改用模板预览图或上传本地位图。
                  先点击预览里的区域，再在左侧选择设计历史素材填充；区域优先使用模板 regions，没有配置时会使用 DXF 闭合轮廓，仍无法识别时才把整张底图作为一个区域。缩放只影响当前预览视图。
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
