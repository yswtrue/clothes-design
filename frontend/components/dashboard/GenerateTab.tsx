'use client';

import { useState, useEffect } from 'react';
import {
  submitGeneration,
  pollTaskStatus,
  getPromptFeatures,
  PromptFeatureResponse,
} from '@/lib/generate';
import { Material } from '@/types/upload';
import { GenerateRequest, TaskStatusResponse } from '@/types/generate';
import MaterialSelector from '@/components/generate/MaterialSelector';
import { LazyGenerationProgress, LazyPatternResult } from '@/components/LazyComponents';
import { apiRequest } from '@/lib/api';
import { triggerMaterialExport, pollExportStatus } from '@/lib/export';

type GenerateState = 'idle' | 'loading_materials' | 'ready' | 'generating' | 'complete' | 'error' | 'pending_background';

function getDefaultPromptFeatureIds(promptFeatures: PromptFeatureResponse[]) {
  return promptFeatures.filter((feature) => feature.is_default).map((feature) => feature.id);
}

function buildGenerationPrompt(
  promptFeatures: PromptFeatureResponse[],
  selectedFeatureIds: number[],
  customPrompt: string
) {
  const selectedFeaturePrompts = promptFeatures
    .filter((feature) => selectedFeatureIds.includes(feature.id))
    .map((feature) => feature.prompt.trim())
    .filter(Boolean);

  return [...selectedFeaturePrompts, customPrompt.trim()]
    .filter(Boolean)
    .join('\n');
}

export default function GenerateTab() {
  const [state, setState] = useState<GenerateState>('loading_materials');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null);
  const [promptFeatures, setPromptFeatures] = useState<PromptFeatureResponse[]>([]);
  const [selectedPromptFeatureIds, setSelectedPromptFeatureIds] = useState<number[]>([]);
  const [customPrompt, setCustomPrompt] = useState('');
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resultDesignId, setResultDesignId] = useState<number | null>(null);
  const [resultPatternUrl, setResultPatternUrl] = useState<string | null>(null);
  const [resultFileName, setResultFileName] = useState<string>('');
  const [materialTifExporting, setMaterialTifExporting] = useState(false);

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

    getPromptFeatures().then((features) => {
      if (!isMounted) return;
      setPromptFeatures(features);
      setSelectedPromptFeatureIds(getDefaultPromptFeatureIds(features));
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const resetPromptFeaturesToDefaults = (features: PromptFeatureResponse[] = promptFeatures) => {
    setSelectedPromptFeatureIds(getDefaultPromptFeatureIds(features));
  };

  const handleDeleteMaterial = async (materialId: number) => {
    await apiRequest(`/api/materials/${materialId}`, { method: 'DELETE' });
    setMaterials((prev) => prev.filter((m) => m.id !== materialId));
    if (selectedMaterial?.id === materialId) {
      setSelectedMaterial(null);
      setCustomPrompt('');
      resetPromptFeaturesToDefaults();
    }
  };

  const handleSelectMaterial = (material: Material) => {
    setSelectedMaterial(material);
    setCustomPrompt('');
    resetPromptFeaturesToDefaults();
  };

  const togglePromptFeature = (featureId: number) => {
    setSelectedPromptFeatureIds((current) =>
      current.includes(featureId)
        ? current.filter((id) => id !== featureId)
        : [...current, featureId]
    );
  };

  const handleGenerate = async () => {
    if (!selectedMaterial) return;

    setState('generating');
    setError(null);
    setTaskStatus(null);

    try {
      const request: GenerateRequest = {
        material_id: selectedMaterial.id,
        prompt: buildGenerationPrompt(
          promptFeatures,
          selectedPromptFeatureIds,
          customPrompt
        ) || undefined,
      };

      const response = await submitGeneration(request);
      setResultDesignId(response.design_id);
      setTaskStatus(response);

      const completedTask = await pollTaskStatus(response.task_id, (task) => {
        setTaskStatus(task);
      });

      if (completedTask.status === 'completed' && completedTask.result) {
        if (completedTask.result.status === 'error') {
          setError(completedTask.result.error || '生成失败');
          setState('error');
          return;
        }

        const patternUrl = completedTask.result.pattern_url
          || (completedTask.result.image_data
            ? `data:image/png;base64,${completedTask.result.image_data}`
            : null);

        if (!patternUrl) {
          setError('生成完成但未返回图片');
          setState('error');
          return;
        }

        setResultPatternUrl(patternUrl);
        setResultFileName(completedTask.result.file_name || `pattern-${response.design_id}.png`);
        setState('complete');
      } else if (completedTask.status === 'failed') {
        setError(completedTask.error || '生成失败');
        setState('error');
      } else if (completedTask.status === 'pending' || completedTask.status === 'processing') {
        setState('pending_background');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成图案失败');
      setState('error');
    }
  };

  const handleExportMaterialTif = async () => {
    if (!selectedMaterial) return;

    setMaterialTifExporting(true);
    setError(null);
    try {
      const response = await triggerMaterialExport(selectedMaterial.id, 'tif', 12000);

      // Already exported (cached) — direct download
      if (!response.task_id && response.status === 'exported' && response.download_url) {
        const link = document.createElement('a');
        link.href = response.download_url;
        link.download = `material-${selectedMaterial.id}-12K-CMYK.tif`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        return;
      }

      if (!response.task_id) {
        throw new Error('未获取到任务ID');
      }

      // Poll until complete
      const completedStatus = await pollExportStatus(response.task_id);

      if (completedStatus.status === 'exported' && completedStatus.download_url) {
        const link = document.createElement('a');
        link.href = completedStatus.download_url;
        link.download = `material-${selectedMaterial.id}-12K-CMYK.tif`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else if (completedStatus.status === 'failed') {
        throw new Error(completedStatus.error || '导出TIF失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '导出原图TIF失败');
    } finally {
      setMaterialTifExporting(false);
    }
  };

  const handleReset = () => {
    setSelectedMaterial(null);
    resetPromptFeaturesToDefaults();
    setCustomPrompt('');
    setTaskStatus(null);
    setError(null);
    setResultPatternUrl(null);
    setResultFileName('');
    setResultDesignId(null);
    setState('ready');
  };

  const finalPromptPreview = buildGenerationPrompt(
    promptFeatures,
    selectedPromptFeatureIds,
    customPrompt
  );

  return (
    <div>
      {state === 'loading_materials' && (
        <div className="flex items-center justify-center py-12">
          <div className="relative h-12 w-12">
            <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
            <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
          </div>
        </div>
      )}

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

      {(state === 'ready' || state === 'generating') && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <MaterialSelector
              materials={materials}
              selectedMaterial={selectedMaterial}
              onSelectMaterial={handleSelectMaterial}
              onDeleteMaterial={handleDeleteMaterial}
            />

            {selectedMaterial && (
              <>
                <div className="space-y-4">
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    生成提示词
                  </label>
                  <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 space-y-4">
                    <div>
                      <p className="text-sm font-medium text-zinc-950 dark:text-zinc-50 mb-2">
                        按功能勾选
                      </p>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {promptFeatures.map((feature) => {
                          const isChecked = selectedPromptFeatureIds.includes(feature.id);
                          return (
                            <label
                              key={feature.id}
                              className={`
                                flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors
                                ${isChecked
                                  ? 'border-zinc-950 dark:border-zinc-50 bg-zinc-100 dark:bg-zinc-800'
                                  : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600'
                                }
                              `}
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => togglePromptFeature(feature.id)}
                                className="mt-0.5 h-4 w-4 rounded border-zinc-300 dark:border-zinc-700 text-zinc-950 dark:text-zinc-50 focus:ring-2 focus:ring-zinc-950 dark:focus:ring-zinc-50"
                              />
                              <span>
                                <span className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
                                  {feature.label}
                                </span>
                                <span className="mt-1 block text-xs text-zinc-600 dark:text-zinc-400">
                                  {feature.description}
                                </span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                      {promptFeatures.length === 0 && (
                        <p className="rounded-md bg-zinc-50 dark:bg-zinc-950/50 p-3 text-xs text-zinc-500 dark:text-zinc-400">
                          暂无可用功能项，可在后台 Prompt Features 中启用或新增。
                        </p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="custom-prompt" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                        自定义提示词
                      </label>
                      <textarea
                        id="custom-prompt"
                        value={customPrompt}
                        onChange={(e) => setCustomPrompt(e.target.value)}
                        rows={3}
                        className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                        placeholder="例如：加入复古花卉、降低饱和度、面向童装系列..."
                      />
                    </div>

                    <details className="rounded-md bg-zinc-50 dark:bg-zinc-950/50 p-3">
                      <summary className="cursor-pointer text-xs font-medium text-zinc-600 dark:text-zinc-400">
                        查看最终提交提示词
                      </summary>
                      <pre className="mt-3 whitespace-pre-wrap text-xs leading-5 text-zinc-600 dark:text-zinc-400">
                        {finalPromptPreview || '未选择功能，也未填写自定义提示词，将使用后端默认提示词。'}
                      </pre>
                    </details>
                  </div>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    勾选后台配置的功能项，并按需填写自定义提示词补充生成要求。
                  </p>
                </div>

                <button
                  onClick={handleGenerate}
                  disabled={state === 'generating'}
                  className="w-full rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {state === 'generating' ? '生成中...' : '生成图案'}
                </button>

                <button
                  onClick={handleExportMaterialTif}
                  disabled={materialTifExporting || state === 'generating'}
                  className="w-full rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-3 text-sm font-medium text-zinc-950 dark:text-zinc-50 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {materialTifExporting ? '导出中...' : '导出原图TIF (CMYK · 300DPI)'}
                </button>
              </>
            )}
          </div>

          <div className="lg:col-span-1">
            {state === 'generating' && (
              <LazyGenerationProgress
                task={taskStatus}
                isPolling={true}
                error={error || undefined}
              />
            )}
          </div>
        </div>
      )}

      {state === 'complete' && resultPatternUrl && resultDesignId && (
        <div className="max-w-2xl mx-auto">
          <LazyPatternResult
            patternUrl={resultPatternUrl}
            fileName={resultFileName}
            designId={resultDesignId}
            onGenerateAnother={handleReset}
          />
        </div>
      )}

      {state === 'pending_background' && (
        <div className="max-w-md mx-auto">
          <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 p-6 text-center">
            <svg
              className="h-12 w-12 text-blue-600 dark:text-blue-400 mx-auto mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 className="text-lg font-medium text-blue-800 dark:text-blue-200 mb-2">
              图案生成中
            </h3>
            <p className="text-sm text-blue-700 dark:text-blue-300 mb-4">
              AI 正在努力生成图案，您可以前往设计历史查看进度
            </p>
            <div className="flex flex-col gap-3">
              <a
                href="/dashboard?tab=history"
                className="inline-flex items-center justify-center rounded-md bg-blue-600 dark:bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 dark:hover:bg-blue-600 transition-colors"
              >
                查看设计历史
              </a>
              <button
                onClick={handleReset}
                className="inline-flex items-center justify-center rounded-md border border-blue-300 dark:border-blue-700 px-4 py-2 text-sm font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
              >
                继续生成新图案
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
