'use client';

import { useState, useEffect } from 'react';
import { submitGeneration, pollTaskStatus } from '@/lib/generate';
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
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resultPatternUrl, setResultPatternUrl] = useState<string | null>(null);
  const [resultFileName, setResultFileName] = useState<string>('');
  const [designId, setDesignId] = useState<number | null>(null);

  useEffect(() => {
    loadMaterials();
  }, []);

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

  const handleGenerate = async () => {
    if (!selectedMaterial) return;

    setState('generating');
    setError(null);
    setTaskStatus(null);

    try {
      const request: GenerateRequest = {
        material_id: selectedMaterial.id,
        pattern_type: printType,
      };

      const response = await submitGeneration(request);
      setDesignId(response.design_id);
      setTaskStatus(response);

      const completedTask = await pollTaskStatus(response.task_id, (task) => {
        setTaskStatus(task);
      });

      if (completedTask.status === 'completed' && completedTask.result) {
        setResultPatternUrl(completedTask.result.pattern_url);
        setResultFileName(completedTask.result.file_name);
        setState('complete');
      } else if (completedTask.status === 'failed') {
        setError(completedTask.error || '生成失败');
        setState('error');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成图案失败');
      setState('error');
    }
  };

  const handleReset = () => {
    setSelectedMaterial(null);
    setPrintType('seamless');
    setTaskStatus(null);
    setError(null);
    setResultPatternUrl(null);
    setResultFileName('');
    setDesignId(null);
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

      {state === 'error' && !taskStatus && (
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
          <button
            onClick={loadMaterials}
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
              onSelectMaterial={setSelectedMaterial}
            />

            {selectedMaterial && (
              <>
                <PrintTypeSelector
                  selected={printType}
                  onChange={setPrintType}
                  suggestedType={suggestedPrintType}
                />

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
              <LazyGenerationProgress
                task={taskStatus}
                isPolling={true}
                error={error || undefined}
              />
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
