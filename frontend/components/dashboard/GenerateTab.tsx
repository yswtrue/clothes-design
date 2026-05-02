'use client';

import { useState, useEffect, useRef } from 'react';
import { submitGeneration, pollTaskStatus, getPromptTemplates, PromptTemplateResponse } from '@/lib/generate';
import { Material } from '@/types/upload';
import { GenerateRequest, TaskStatusResponse } from '@/types/generate';
import MaterialSelector from '@/components/generate/MaterialSelector';
import PrintTypeSelector from '@/components/generate/PrintTypeSelector';
import { LazyGenerationProgress, LazyPatternResult } from '@/components/LazyComponents';
import { apiRequest } from '@/lib/api';

type GenerateState = 'idle' | 'loading_materials' | 'ready' | 'generating' | 'complete' | 'error';

export default function GenerateTab() {
  const [state, setState] = useState<GenerateState>('idle');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null);
  const [printType, setPrintType] = useState<'seamless' | 'standalone' | 'full'>('seamless');
  const [prompt, setPrompt] = useState('');
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplateResponse[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [isLoadingPrompt, setIsLoadingPrompt] = useState(false);
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resultPatternUrl, setResultPatternUrl] = useState<string | null>(null);
  const [resultFileName, setResultFileName] = useState<string>('');
  const [designId, setDesignId] = useState<number | null>(null);
  const [showTimeoutHint, setShowTimeoutHint] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    loadMaterials();
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const startTimer = () => {
    setElapsedSeconds(0);
    setShowTimeoutHint(false);
    timerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => {
        const next = prev + 1;
        if (next >= 60 && !showTimeoutHint) {
          setShowTimeoutHint(true);
        }
        return next;
      });
    }, 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const loadMaterials = async () => {
    setState('loading_materials');
    setError(null);
    try {
      const data = await apiRequest<{ items: Material[] }>('/api/materials?size=100');
      setMaterials(data.items || []);
      setState('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载素材失败');
      setState('error');
    }
  };

  const handleDeleteMaterial = async (materialId: number) => {
    await apiRequest(`/api/materials/${materialId}`, { method: 'DELETE' });
    setMaterials((prev) => prev.filter((m) => m.id !== materialId));
    if (selectedMaterial?.id === materialId) {
      setSelectedMaterial(null);
      setPrompt('');
    }
  };

  const handleSelectMaterial = async (material: Material) => {
    setSelectedMaterial(material);
    setIsLoadingPrompt(true);
    try {
      const templates = await getPromptTemplates('img2img');
      setPromptTemplates(templates);
      const defaultTemplate = templates.find((t: PromptTemplateResponse) => t.is_default);
      if (defaultTemplate) {
        setSelectedTemplateId(defaultTemplate.id);
        setPrompt(defaultTemplate.template);
      } else if (templates.length > 0) {
        setSelectedTemplateId(templates[0].id);
        setPrompt(templates[0].template);
      }
    } catch {
    } finally {
      setIsLoadingPrompt(false);
    }
  };

  const handleTemplateChange = (templateId: number) => {
    setSelectedTemplateId(templateId);
    const template = promptTemplates.find(t => t.id === templateId);
    if (template) {
      setPrompt(template.template);
    }
  };

  const handleGenerate = async () => {
    if (!selectedMaterial) return;

    setState('generating');
    setError(null);
    setTaskStatus(null);
    startTimer();

    try {
      const request: GenerateRequest = {
        material_id: selectedMaterial.id,
        pattern_type: printType,
        prompt: prompt || undefined,
      };

      const response = await submitGeneration(request);
      setDesignId(response.design_id);
      setTaskStatus(response);

      const completedTask = await pollTaskStatus(response.task_id, (task) => {
        setTaskStatus(task);
      });

      stopTimer();

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
      }
    } catch (err) {
      stopTimer();
      setError(err instanceof Error ? err.message : '生成图案失败');
      setState('error');
    }
  };

  const handleReset = () => {
    stopTimer();
    setSelectedMaterial(null);
    setPrintType('seamless');
    setPrompt('');
    setPromptTemplates([]);
    setSelectedTemplateId(null);
    setTaskStatus(null);
    setError(null);
    setResultPatternUrl(null);
    setResultFileName('');
    setDesignId(null);
    setShowTimeoutHint(false);
    setElapsedSeconds(0);
    setState('ready');
  };

  const suggestedPrintType = selectedMaterial?.meta?.style_analysis?.pattern_type || 'seamless';

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
                <PrintTypeSelector
                  selected={printType}
                  onChange={setPrintType}
                  suggestedType={suggestedPrintType}
                />

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label htmlFor="prompt" className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      提示词
                    </label>
                    {promptTemplates.length > 0 && (
                      <select
                        value={selectedTemplateId || ''}
                        onChange={(e) => handleTemplateChange(Number(e.target.value))}
                        className="text-sm rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2 py-1 text-zinc-900 dark:text-zinc-100 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                      >
                        {promptTemplates.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name} {t.is_default ? '(默认)' : ''}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                  {isLoadingPrompt ? (
                    <div className="h-32 flex items-center justify-center bg-zinc-50 dark:bg-zinc-900 rounded-md border border-zinc-300 dark:border-zinc-700">
                      <div className="h-5 w-5 rounded-full border-2 border-zinc-300 dark:border-zinc-600 border-t-zinc-950 dark:border-t-zinc-50 animate-spin"></div>
                    </div>
                  ) : (
                    <textarea
                      id="prompt"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      rows={5}
                      className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                      placeholder="输入生成提示词，或使用默认模板..."
                    />
                  )}
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    支持变量: {'{style_description}'}, {'{color_palette}'}, {'{pattern_type}'}, {'{width}'}, {'{height}'}
                  </p>
                </div>

                <button
                  onClick={handleGenerate}
                  disabled={state === 'generating'}
                  className="w-full rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {state === 'generating' ? '生成中...' : '生成图案'}
                </button>
              </>
            )}
          </div>

          <div className="lg:col-span-1">
            {state === 'generating' && (
              <div className="space-y-4">
                <LazyGenerationProgress
                  task={taskStatus}
                  isPolling={true}
                  error={error || undefined}
                />
                
                {showTimeoutHint && (
                  <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-4">
                    <div className="flex items-start gap-3">
                      <svg
                        className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5"
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
                      <div className="flex-1">
                        <h3 className="text-sm font-medium text-amber-800 dark:text-amber-200">
                          生成时间较长 ({elapsedSeconds}秒)
                        </h3>
                        <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
                          AI 正在努力生成图案，您可以：
                        </p>
                        <div className="mt-3 flex flex-col gap-2">
                          <a
                            href="/dashboard?tab=history"
                            className="inline-flex items-center justify-center rounded-md bg-amber-100 dark:bg-amber-800/50 px-3 py-2 text-sm font-medium text-amber-800 dark:text-amber-200 hover:bg-amber-200 dark:hover:bg-amber-800 transition-colors"
                          >
                            <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            去设计历史查看进度
                          </a>
                          <button
                            onClick={() => setShowTimeoutHint(false)}
                            className="inline-flex items-center justify-center rounded-md border border-amber-300 dark:border-amber-700 px-3 py-2 text-sm font-medium text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
                          >
                            继续等待
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {state === 'complete' && resultPatternUrl && (
        <div className="max-w-2xl mx-auto">
          <LazyPatternResult
            patternUrl={resultPatternUrl}
            fileName={resultFileName}
            onGenerateAnother={handleReset}
          />
        </div>
      )}
    </div>
  );
}
