'use client';

import { useState, useEffect } from 'react';
import { Material } from '@/types/upload';
import { PosterGenerateRequest, PosterGenerateResponse, PosterTaskStatusResponse, PosterHistoryItem, PosterHistoryResponse } from '@/types/poster';
import { submitPosterGeneration, pollPosterTask } from '@/lib/poster';
import { apiRequest } from '@/lib/api';

type PosterState = 'loading_materials' | 'ready' | 'generating' | 'complete' | 'error';
type ViewMode = 'generate' | 'history';

const PRODUCT_TYPES = [
  { id: 'tops', label: '上衣', icon: '👕' },
  { id: 'pants', label: '裤子', icon: '👖' },
  { id: 'skirts', label: '裙子', icon: '👗' },
  { id: 'outerwear', label: '外套', icon: '🧥' },
  { id: 'shoes', label: '鞋类', icon: '👟' },
  { id: 'bags', label: '包包', icon: '👜' },
  { id: 'accessories', label: '配饰', icon: '💍' },
  { id: 'other', label: '其他', icon: '📦' },
];

const STYLES = [
  { id: 'studio', label: '工作室白底', description: 'Studio White Background' },
  { id: 'lifestyle', label: 'lifestyle/场景', description: 'Lifestyle/Scene' },
  { id: 'minimalist', label: '极简风格', description: 'Minimalist' },
  { id: 'luxury', label: '奢华高级', description: 'Luxury/Premium' },
  { id: 'vintage', label: '复古胶片', description: 'Vintage/Film' },
  { id: 'outdoor', label: '自然户外', description: 'Natural/Outdoor' },
  { id: 'editorial', label: '时尚杂志', description: 'Fashion Editorial' },
];

const RESOLUTION_PRESETS = [
  { width: 1024, height: 1024, label: '1:1 正方形' },
  { width: 1024, height: 768, label: '4:3' },
  { width: 1024, height: 1536, label: '2:3 竖版' },
  { width: 1536, height: 1024, label: '3:2 横版' },
];

function Spinner({ className = 'h-12 w-12' }: { className?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <div className={`relative ${className}`}>
        <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
        <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
      </div>
    </div>
  );
}

export default function EcommercePosterTab() {
  const [viewMode, setViewMode] = useState<ViewMode>('generate');
  const [state, setState] = useState<PosterState>('loading_materials');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<number[]>([]);
  const [productType, setProductType] = useState<string>('tops');
  const [style, setStyle] = useState<string>('studio');
  const [language, setLanguage] = useState<string>('en');
  const [customPrompt, setCustomPrompt] = useState('');
  const [imageCount, setImageCount] = useState(1);
  const [width, setWidth] = useState(1024);
  const [height, setHeight] = useState(1024);
  const [taskStatus, setTaskStatus] = useState<PosterTaskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resultImages, setResultImages] = useState<string[]>([]);
  const [showMaterialModal, setShowMaterialModal] = useState(false);
  const [pendingMaterialIds, setPendingMaterialIds] = useState<number[]>([]);

  // History
  const [historyItems, setHistoryItems] = useState<PosterHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const HISTORY_SIZE = 20;

  useEffect(() => {
    let isMounted = true;

    apiRequest<{ items: Material[] }>('/api/materials?size=100')
      .then((data) => {
        if (!isMounted) return;
        setMaterials(data.items || []);
        setState('ready');
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : '加载素材失败');
        setState('error');
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // ── history ──

  const loadHistory = async (page: number = 1) => {
    setHistoryLoading(true);
    try {
      const data = await apiRequest<PosterHistoryResponse>(
        `/api/posters?page=${page}&size=${HISTORY_SIZE}`
      );
      setHistoryItems(data.items || []);
      setHistoryTotal(data.total || 0);
      setHistoryPage(data.page || 1);
    } catch (err) {
      console.error('加载历史记录失败:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const switchToHistory = () => {
    setViewMode('history');
    loadHistory(1);
  };

  // ── generation ──

  const openMaterialModal = () => {
    setPendingMaterialIds([...selectedMaterialIds]);
    setShowMaterialModal(true);
  };

  const togglePendingMaterial = (id: number) => {
    setPendingMaterialIds((prev) =>
      prev.includes(id) ? prev.filter((mid) => mid !== id) : [...prev, id]
    );
  };

  const confirmMaterialSelection = () => {
    setSelectedMaterialIds(pendingMaterialIds);
    setShowMaterialModal(false);
  };

  const removeMaterial = (id: number) => {
    setSelectedMaterialIds((prev) => prev.filter((mid) => mid !== id));
  };

  const handleResolutionSelect = (presetWidth: number, presetHeight: number) => {
    setWidth(presetWidth);
    setHeight(presetHeight);
  };

  const handleGenerate = async () => {
    if (selectedMaterialIds.length === 0) return;

    setState('generating');
    setError(null);
    setTaskStatus(null);
    setResultImages([]);

    try {
      const request: PosterGenerateRequest = {
        material_ids: selectedMaterialIds,
        product_type: productType,
        style: style,
        language: language,
        custom_prompt: customPrompt.trim() || undefined,
        image_count: imageCount,
        width: width,
        height: height,
      };

      const response: PosterGenerateResponse = await submitPosterGeneration(request);
      setTaskStatus(response as unknown as PosterTaskStatusResponse);

      const completedTask = await pollPosterTask(response.task_id, (task) => {
        setTaskStatus(task);
      });

      if (completedTask.status === 'completed' && completedTask.result) {
        if (completedTask.result.status === 'error') {
          setError(completedTask.result.error || '生成失败');
          setState('error');
          return;
        }

        const imageUrls = completedTask.result.image_urls || [];
        if (imageUrls.length === 0) {
          setError('生成完成但未返回图片');
          setState('error');
          return;
        }

        setResultImages(imageUrls);
        setState('complete');
      } else if (completedTask.status === 'failed') {
        setError(completedTask.error || '生成失败');
        setState('error');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成电商图失败');
      setState('error');
    }
  };

  const handleReset = () => {
    setSelectedMaterialIds([]);
    setCustomPrompt('');
    setTaskStatus(null);
    setError(null);
    setResultImages([]);
    setImageCount(1);
    setProductType('tops');
    setStyle('studio');
    setLanguage('en');
    setWidth(1024);
    setHeight(1024);
    setState('ready');
  };

  const selectedMaterials = materials.filter((m) => selectedMaterialIds.includes(m.id));

  const canGenerate = selectedMaterialIds.length > 0 && state !== 'generating';

  return (
    <div>
      {/* ── View Toggle ── */}
      <div className="flex gap-2 mb-6">
        {([
          { id: 'generate' as ViewMode, label: '生成', icon: '✨' },
          { id: 'history' as ViewMode, label: '历史', icon: '📋' },
        ]).map((tab) => (
          <button
            key={tab.id}
            onClick={() => tab.id === 'history' ? switchToHistory() : setViewMode('generate')}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
              ${viewMode === tab.id
                ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950'
                : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
              }
            `}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── History View ── */}
      {viewMode === 'history' && <PosterHistoryPanel
        items={historyItems}
        total={historyTotal}
        page={historyPage}
        size={HISTORY_SIZE}
        loading={historyLoading}
        onPageChange={(p) => loadHistory(p)}
      />}

      {/* ── Generate View ── */}
      {viewMode === 'generate' && (<>
      {/* Loading State */}
      {state === 'loading_materials' && <Spinner />}

      {/* Error State */}
      {state === 'error' && (
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
                生成失败
              </h3>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">{error}</p>
            </div>
          </div>
          <button
            onClick={handleReset}
            className="mt-4 rounded-md bg-red-600 dark:bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 dark:hover:bg-red-600 transition-colors"
          >
            重试
          </button>
        </div>
      )}

      {/* Ready / Generating State - Two Column Layout */}
      {(state === 'ready' || state === 'generating') && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Form */}
          <div className="lg:col-span-2 space-y-6">
            {/* Material Photo Upload Area */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
                  选择产品照片
                </label>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  {selectedMaterialIds.length} 个素材已选
                </span>
              </div>

              {selectedMaterials.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {selectedMaterials.map((material) => (
                    <div
                      key={material.id}
                      className="relative rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden group"
                    >
                      <div className="aspect-square bg-zinc-100 dark:bg-zinc-800">
                        {material.thumbnail_url ? (
                          <img
                            src={material.thumbnail_url}
                            alt={material.original_filename}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-zinc-400 text-xs">
                            无预览
                          </div>
                        )}
                      </div>
                      <div className="p-2">
                        <p className="text-xs text-zinc-600 dark:text-zinc-400 truncate">
                          {material.original_filename}
                        </p>
                      </div>
                      {state === 'ready' && (
                        <button
                          onClick={() => removeMaterial(material.id)}
                          className="absolute top-1 right-1 w-6 h-6 bg-red-500/80 hover:bg-red-600 rounded-full flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity"
                          title="移除"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  onClick={openMaterialModal}
                  disabled={state === 'generating'}
                  className="rounded-md border border-zinc-300 dark:border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  选择素材
                </button>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                请先在上传素材页面上传产品照片，然后在此选择
              </p>
            </div>

            {/* Product Type Selector */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
                产品类型
              </label>
              <div className="grid grid-cols-4 gap-2">
                {PRODUCT_TYPES.map((pt) => {
                  const isSelected = productType === pt.id;
                  return (
                    <button
                      key={pt.id}
                      onClick={() => setProductType(pt.id)}
                      disabled={state === 'generating'}
                      className={`
                        flex flex-col items-center gap-1 rounded-lg border p-3 text-sm transition-colors
                        ${isSelected
                          ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 border-zinc-950 dark:border-zinc-50'
                          : 'border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                        }
                        disabled:opacity-50 disabled:cursor-not-allowed
                      `}
                    >
                      <span className="text-lg">{pt.icon}</span>
                      <span className="font-medium">{pt.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Style Selector */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
                风格
              </label>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {STYLES.map((s) => {
                  const isSelected = style === s.id;
                  return (
                    <button
                      key={s.id}
                      onClick={() => setStyle(s.id)}
                      disabled={state === 'generating'}
                      className={`
                        rounded-lg border p-3 text-sm text-left transition-colors
                        ${isSelected
                          ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 border-zinc-950 dark:border-zinc-50'
                          : 'border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                        }
                        disabled:opacity-50 disabled:cursor-not-allowed
                      `}
                    >
                      <span className="font-medium">{s.label}</span>
                      <span className="block text-xs mt-0.5 opacity-70">{s.description}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Language Selector */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
                提示词语种
              </label>
              <div className="flex gap-2">
                {[
                  { id: 'en', label: 'English' },
                  { id: 'zh', label: '中文' },
                ].map((lang) => {
                  const isSelected = language === lang.id;
                  return (
                    <button
                      key={lang.id}
                      onClick={() => setLanguage(lang.id)}
                      disabled={state === 'generating'}
                      className={`
                        flex-1 rounded-lg border p-3 text-sm font-medium transition-colors
                        ${isSelected
                          ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 border-zinc-950 dark:border-zinc-50'
                          : 'border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                        }
                        disabled:opacity-50 disabled:cursor-not-allowed
                      `}
                    >
                      {lang.label}
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                选择提示词语言，影响 AI 生成的构图描述
              </p>
            </div>

            {/* Custom Prompt */}
            <div className="space-y-2">
              <label htmlFor="poster-prompt" className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
                自定义提示词
              </label>
              <textarea
                id="poster-prompt"
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                disabled={state === 'generating'}
                rows={3}
                className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 disabled:opacity-50 disabled:cursor-not-allowed"
                placeholder="例如：白色背景、自然光、模特穿着正面展示..."
              />
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                可选。描述您想要的电商图效果，AI 将据此调整生成。
              </p>
            </div>

            {/* Image Count */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
                生成数量
              </label>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setImageCount(Math.max(1, imageCount - 1))}
                  disabled={state === 'generating' || imageCount <= 1}
                  className="w-10 h-10 rounded-lg border border-zinc-300 dark:border-zinc-700 flex items-center justify-center text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                  </svg>
                </button>
                <span className="w-8 text-center text-lg font-medium text-zinc-950 dark:text-zinc-50 tabular-nums">
                  {imageCount}
                </span>
                <button
                  onClick={() => setImageCount(Math.min(10, imageCount + 1))}
                  disabled={state === 'generating' || imageCount >= 10}
                  className="w-10 h-10 rounded-lg border border-zinc-300 dark:border-zinc-700 flex items-center justify-center text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </button>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">（1-10 张）</span>
              </div>
            </div>

            {/* Resolution Selector */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
                分辨率
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {RESOLUTION_PRESETS.map((preset) => {
                  const isSelected = width === preset.width && height === preset.height;
                  return (
                    <button
                      key={`${preset.width}x${preset.height}`}
                      onClick={() => handleResolutionSelect(preset.width, preset.height)}
                      disabled={state === 'generating'}
                      className={`
                        rounded-lg border p-3 text-sm text-center transition-colors
                        ${isSelected
                          ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 border-zinc-950 dark:border-zinc-50'
                          : 'border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                        }
                        disabled:opacity-50 disabled:cursor-not-allowed
                      `}
                    >
                      <span className="font-medium">{preset.width}×{preset.height}</span>
                      <span className="block text-xs mt-0.5 opacity-70">{preset.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              disabled={!canGenerate}
              className="w-full rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {state === 'generating' ? '生成中...' : '生成电商图'}
            </button>
          </div>

          {/* Right Column - Progress Panel */}
          <div className="lg:col-span-1">
            {state === 'generating' && (
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
                <div className="flex flex-col items-center gap-4">
                  <div className="relative h-12 w-12">
                    <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
                    <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
                  </div>
                  <div className="text-center">
                    <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50">
                      {taskStatus?.status === 'processing' ? '处理中' : '已排队'}
                    </h3>
                    <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                      AI 正在生成电商海报... 这可能需要 30-60 秒
                    </p>
                    {taskStatus?.task_id && (
                      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-500 font-mono">
                        任务 ID: {taskStatus.task_id.slice(0, 8)}...
                      </p>
                    )}
                    <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
                      生成 {imageCount} 张 · {width}×{height}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Complete State - Show Results */}
      {state === 'complete' && resultImages.length > 0 && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {resultImages.map((imageUrl, index) => (
              <div
                key={index}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden"
              >
                <div className="aspect-[4/5] relative bg-zinc-100 dark:bg-zinc-800">
                  <img
                    src={imageUrl}
                    alt={`电商海报 ${index + 1}`}
                    className="w-full h-full object-contain"
                  />
                </div>
                <div className="p-4 flex items-center justify-between">
                  <span className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                    海报 {index + 1}
                  </span>
                  <a
                    href={imageUrl}
                    download={`poster-${index + 1}.png`}
                    className="inline-flex items-center gap-1.5 rounded-md bg-zinc-950 dark:bg-zinc-50 px-3 py-1.5 text-xs font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    下载
                  </a>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-center">
            <button
              onClick={handleReset}
              className="rounded-md bg-zinc-950 dark:bg-zinc-50 px-6 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
            >
              继续生成
            </button>
          </div>
        </div>
      )}

      {/* Material Selection Modal */}
      {showMaterialModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setShowMaterialModal(false)}
        >
          <div
            className="bg-white dark:bg-zinc-900 rounded-lg max-w-3xl w-full mx-4 max-h-[80vh] flex flex-col shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800">
              <h3 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">
                选择素材
              </h3>
              <button
                onClick={() => setShowMaterialModal(false)}
                className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-4 flex-1 overflow-y-auto">
              {materials.length === 0 ? (
                <p className="text-center py-8 text-zinc-500 dark:text-zinc-400">
                  暂无素材，请先上传产品照片
                </p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {materials.map((material) => {
                    const isChecked = pendingMaterialIds.includes(material.id);
                    return (
                      <button
                        key={material.id}
                        onClick={() => togglePendingMaterial(material.id)}
                        className={`
                          relative rounded-lg border-2 transition-all overflow-hidden text-left
                          ${isChecked
                            ? 'border-zinc-950 dark:border-zinc-50 ring-2 ring-zinc-950/20 dark:ring-zinc-50/20'
                            : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600'
                          }
                        `}
                      >
                        <div className="aspect-square bg-zinc-100 dark:bg-zinc-800">
                          {material.thumbnail_url ? (
                            <img
                              src={material.thumbnail_url}
                              alt={material.original_filename}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-zinc-400">
                              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                              </svg>
                            </div>
                          )}
                          {isChecked && (
                            <div className="absolute top-2 right-2 w-6 h-6 bg-zinc-950 dark:bg-zinc-50 rounded-full flex items-center justify-center">
                              <svg className="w-4 h-4 text-white dark:text-zinc-950" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                            </div>
                          )}
                        </div>
                        <div className="p-2">
                          <p className="text-xs font-medium text-zinc-950 dark:text-zinc-50 truncate">
                            {material.original_filename}
                          </p>
                          <p className="text-xs text-zinc-500 dark:text-zinc-400">
                            {(material.file_size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between p-4 border-t border-zinc-200 dark:border-zinc-800">
              <span className="text-sm text-zinc-500 dark:text-zinc-400">
                已选 {pendingMaterialIds.length} 个素材
              </span>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowMaterialModal(false)}
                  className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={confirmMaterialSelection}
                  className="px-4 py-2 text-sm font-medium text-white dark:text-zinc-950 bg-zinc-950 dark:bg-zinc-50 hover:bg-zinc-800 dark:hover:bg-zinc-200 rounded-lg transition-colors"
                >
                  确认选择
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      </>)}
    </div>
  );
}

// ── Poster History Panel ──

function PosterHistoryPanel({
  items, total, page, size, loading, onPageChange,
}: {
  items: PosterHistoryItem[];
  total: number;
  page: number;
  size: number;
  loading: boolean;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / size));
  const PRODUCT_LABELS: Record<string, string> = {
    tops: '上衣', pants: '裤子', skirts: '裙子', outerwear: '外套',
    shoes: '鞋类', bags: '包包', accessories: '配饰', other: '其他',
  };
  const STYLE_LABELS: Record<string, string> = {
    studio: '工作室白底', lifestyle: 'lifestyle/场景', minimalist: '极简风格',
    luxury: '奢华高级', vintage: '复古胶片', outdoor: '自然户外', editorial: '时尚杂志',
  };
  const STATUS_LABELS: Record<string, { label: string; color: string }> = {
    generating: { label: '生成中', color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20' },
    completed: { label: '已完成', color: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20' },
    failed: { label: '失败', color: 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20' },
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="relative h-12 w-12">
          <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
          <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">
        <p className="text-lg">暂无生成记录</p>
        <p className="text-sm mt-1">生成电商海报后，记录将显示在这里</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {items.map((item) => {
        const status = STATUS_LABELS[item.status] || { label: item.status, color: 'text-zinc-500' };
        const thumbnail = item.result_images?.[0] || null;
        const [expanded, setExpanded] = useState(false);

        return (
          <div key={item.id} className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
            {/* Header */}
            <div
              className="flex items-center gap-4 p-4 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
              onClick={() => setExpanded(!expanded)}
            >
              {/* Thumbnail */}
              <div className="w-16 h-16 rounded-lg bg-zinc-100 dark:bg-zinc-800 flex-shrink-0 overflow-hidden">
                {thumbnail ? (
                  <img src={thumbnail} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-zinc-400">
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                    {PRODUCT_LABELS[item.product_type] || item.product_type}
                  </span>
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    {STYLE_LABELS[item.style] || item.style}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${status.color}`}>
                    {status.label}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  <span>{item.width}×{item.height}</span>
                  <span>{item.image_count} 张</span>
                  <span>{item.language === 'zh' ? '中文' : 'EN'}</span>
                  {item.created_at && (
                    <span>{new Date(item.created_at).toLocaleString('zh-CN')}</span>
                  )}
                </div>
              </div>

              {/* Expand arrow */}
              <svg
                className={`w-5 h-5 text-zinc-400 transition-transform flex-shrink-0 ${expanded ? 'rotate-180' : ''}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            {/* Expanded: all images */}
            {expanded && item.result_images && item.result_images.length > 0 && (
              <div className="border-t border-zinc-200 dark:border-zinc-800 p-4">
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {item.result_images.map((url, idx) => (
                    <div key={idx} className="rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                      <div className="aspect-square bg-zinc-100 dark:bg-zinc-800">
                        <img src={url} alt={`海报 ${idx + 1}`} className="w-full h-full object-contain" />
                      </div>
                      <div className="p-2 flex justify-between items-center">
                        <span className="text-xs text-zinc-500 dark:text-zinc-400">#{idx + 1}</span>
                        <a
                          href={url}
                          download={`poster-${item.id}-${idx + 1}.png`}
                          className="text-xs text-zinc-950 dark:text-zinc-50 hover:underline"
                        >
                          下载
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Expanded: prompt info */}
            {expanded && item.custom_prompt && (
              <div className="border-t border-zinc-200 dark:border-zinc-800 px-4 py-3 bg-zinc-50 dark:bg-zinc-800/50">
                <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">自定义提示词：</span>
                <span className="text-xs text-zinc-700 dark:text-zinc-300 ml-1">{item.custom_prompt}</span>
              </div>
            )}
          </div>
        );
      })}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="px-3 py-1.5 text-sm border border-zinc-300 dark:border-zinc-700 rounded-md disabled:opacity-30 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            上一页
          </button>
          <span className="text-sm text-zinc-600 dark:text-zinc-400">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="px-3 py-1.5 text-sm border border-zinc-300 dark:border-zinc-700 rounded-md disabled:opacity-30 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
