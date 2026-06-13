'use client';

import { useState, useEffect, useMemo } from 'react';
import Image from 'next/image';
import { apiRequest } from '@/lib/api';
import { fetchHistory } from '@/lib/history';
import { createPrjTemplatePreview, fetchPrjTemplateDetail } from '@/lib/prjTemplates';
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

type CanvasPoint = [number, number];
type CanvasRectangle = [number, number, number, number];
type CanvasRegion = Record<string, unknown>;

const HISTORY_PAGE_SIZE = 6;

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

function loadCanvasImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new window.Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('图片加载失败'));
    image.src = src;
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
  patternUrl: string,
  regionsPayload: unknown
): Promise<string> {
  const [templateImage, patternImage] = await Promise.all([
    loadCanvasImage(templateUrl),
    loadCanvasImage(patternUrl),
  ]);

  const canvas = document.createElement('canvas');
  canvas.width = templateImage.naturalWidth;
  canvas.height = templateImage.naturalHeight;

  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('浏览器不支持 Canvas 渲染');
  }

  context.drawImage(templateImage, 0, 0, canvas.width, canvas.height);
  const regions = regionsFromPayload(regionsPayload);
  const drawableRegions = regions.length > 0
    ? regions
    : [{ x: 0, y: 0, width: canvas.width, height: canvas.height }];

  for (const region of drawableRegions) {
    context.save();
    context.beginPath();
    const polygon = polygonFromRegion(region, canvas.width, canvas.height);
    if (polygon.length > 0) {
      context.moveTo(polygon[0][0], polygon[0][1]);
      for (const [x, y] of polygon.slice(1)) {
        context.lineTo(x, y);
      }
      context.closePath();
    } else {
      const rectangle = rectangleFromRegion(region, canvas.width, canvas.height);
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

export default function TemplatesTab() {
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

  const selectedDesign = useMemo(() => {
    if (selectedDesignId === null) {
      return null;
    }

    for (const material of historyMaterials) {
      const design = material.designs.find((item) => item.id === selectedDesignId);
      if (design) {
        return design;
      }
    }

    return null;
  }, [historyMaterials, selectedDesignId]);

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
    const templateImageUrl = selectedTemplateDetail?.preview_url ?? selectedTemplate?.preview_url ?? null;
    const patternUrl = selectedDesign ? designImageUrl(selectedDesign) : null;

    if (!templateImageUrl || !patternUrl) {
      return;
    }

    let cancelled = false;
    const templateSrc: string = templateImageUrl;
    const patternSrc: string = patternUrl;

    async function renderPreview() {
      setCanvasState('rendering');
      setCanvasError(null);

      try {
        const renderedUrl = await renderTemplatePreviewInBrowser(
          templateSrc,
          patternSrc,
          selectedTemplateDetail?.regions
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
  }, [selectedDesign, selectedTemplate, selectedTemplateDetail]);

  function selectDesign(designId: number) {
    setSelectedDesignId(designId);
    setPreviewUrl(null);
    setCanvasState('idle');
    setCanvasError(null);
  }

  function openTemplateModal(template: Template) {
    setSelectedTemplate(template);
    setSelectedTemplateDetail(null);
    setHistoryPage(1);
    setHistoryPages(0);
    setSelectedDesignId(null);
    setPreviewUrl(null);
    setModalError(null);
    setCanvasState('idle');
    setCanvasError(null);
  }

  function closeTemplateModal() {
    setSelectedTemplate(null);
    setSelectedTemplateDetail(null);
    setSelectedDesignId(null);
    setPreviewUrl(null);
    setModalError(null);
    setCanvasState('idle');
    setCanvasError(null);
    setHistoryMaterials([]);
  }

  async function handleGeneratePreview() {
    if (!selectedTemplate || selectedDesignId === null) {
      return;
    }

    setModalState('generating');
    setModalError(null);

    try {
      const response = await createPrjTemplatePreview(selectedTemplate.id, selectedDesignId);
      setPreviewUrl(response.preview_url);
      setModalState('idle');
    } catch (err) {
      setModalError(err instanceof Error ? err.message : '生成服装预览失败');
      setModalState('error');
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
                  <h3 className="font-medium text-zinc-950 dark:text-zinc-50">设计历史</h3>
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
                            const selected = selectedDesignId === design.id;

                            return (
                              <button
                                key={design.id}
                                type="button"
                                onClick={() => selectable && selectDesign(design.id)}
                                disabled={!selectable}
                                className={`overflow-hidden rounded-lg border text-left transition ${selected ? 'border-blue-500 ring-2 ring-blue-500' : 'border-zinc-200 dark:border-zinc-700'} ${selectable ? 'hover:border-blue-400' : 'cursor-not-allowed opacity-50'}`}
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
                                  <span className="text-zinc-500 dark:text-zinc-400">{design.status}</span>
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
                <div className="mb-4 overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900">
                  <div className="relative aspect-[4/5]">
                    {previewUrl ? (
                      <Image
                        src={previewUrl}
                        alt={`${selectedTemplate.name} 预览`}
                        fill
                        unoptimized
                        className="object-contain"
                        sizes="(max-width: 1024px) 100vw, 420px"
                      />
                    ) : selectedTemplate.preview_url ? (
                      <>
                        <Image
                          src={selectedTemplate.preview_url}
                          alt={selectedTemplate.name}
                          fill
                          unoptimized
                          className="object-contain opacity-70"
                          sizes="(max-width: 1024px) 100vw, 420px"
                        />
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
                    已在浏览器中根据模板 regions 完成预览渲染。
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
                  disabled={selectedDesignId === null || modalState === 'generating'}
                  className="w-full rounded-lg bg-zinc-950 px-4 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-950 dark:hover:bg-zinc-200"
                >
                  {modalState === 'generating' ? '服务端生成中...' : '服务端兜底生成预览'}
                </button>
                <p className="mt-3 text-xs leading-5 text-zinc-500 dark:text-zinc-400">
                  浏览器会读取模板位图并按照详情接口的 regions 区域填充图案；若模板没有区域配置，则默认填充整张模板预览图。
                  服务端按钮用于浏览器图片跨域或 Canvas 不可用时兜底。
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
