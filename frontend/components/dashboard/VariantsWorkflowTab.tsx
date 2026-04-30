'use client';

import { useState, useEffect } from 'react';
import { Material } from '@/types/upload';
import { GeneratedVariant, PrjTemplate, VariantsTaskStatusResponse, ComposeTaskStatusResponse } from '@/types/variants';
import { apiRequest } from '@/lib/api';
import {
  submitVariantsGeneration,
  pollVariantsTask,
  selectVariant,
  getPrjTemplates,
  submitCompose,
  pollComposeTask,
} from '@/lib/variants';
import MaterialSelector from '@/components/generate/MaterialSelector';
import VariantsGallery from '@/components/generate/VariantsGallery';
import PrjTemplateSelector from '@/components/generate/PrjTemplateSelector';

type WorkflowStep = 'select_material' | 'generating_variants' | 'select_variant' | 'select_template' | 'composing' | 'complete';

interface WorkflowState {
  step: WorkflowStep;
  material: Material | null;
  variants: GeneratedVariant[];
  selectedVariant: GeneratedVariant | null;
  templates: PrjTemplate[];
  selectedTemplate: PrjTemplate | null;
  variantsTask: VariantsTaskStatusResponse | null;
  composeTask: ComposeTaskStatusResponse | null;
  resultTifUrl: string | null;
  resultFileName: string;
  error: string | null;
}

const initialState: WorkflowState = {
  step: 'select_material',
  material: null,
  variants: [],
  selectedVariant: null,
  templates: [],
  selectedTemplate: null,
  variantsTask: null,
  composeTask: null,
  resultTifUrl: null,
  resultFileName: '',
  error: null,
};

export default function VariantsWorkflowTab() {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [isLoadingMaterials, setIsLoadingMaterials] = useState(true);
  const [state, setState] = useState<WorkflowState>(initialState);

  useEffect(() => {
    loadMaterials();
  }, []);

  const loadMaterials = async () => {
    setIsLoadingMaterials(true);
    try {
      const data = await apiRequest<{ items: Material[] }>('/api/materials?size=100');
      setMaterials(data.items || []);
    } catch (err) {
      setState((s) => ({ ...s, error: err instanceof Error ? err.message : '加载素材失败' }));
    } finally {
      setIsLoadingMaterials(false);
    }
  };

  const handleSelectMaterial = (material: Material) => {
    setState((s) => ({ ...s, material, error: null }));
  };

  const handleGenerateVariants = async () => {
    if (!state.material) return;

    setState((s) => ({ ...s, step: 'generating_variants', error: null, variantsTask: null }));

    try {
      const response = await submitVariantsGeneration({ material_id: state.material.id, count: 4 });
      setState((s) => ({ ...s, variantsTask: { task_id: response.task_id, status: 'pending' } }));

      const completedTask = await pollVariantsTask(response.task_id, (task) => {
        setState((s) => ({ ...s, variantsTask: task }));
      });

      if (completedTask.status === 'completed' && completedTask.result) {
        const templates = await getPrjTemplates();
        setState((s) => ({
          ...s,
          step: 'select_variant',
          variants: completedTask.result!.variants,
          templates,
        }));
      } else {
        setState((s) => ({ ...s, step: 'select_material', error: completedTask.error || '生成失败' }));
      }
    } catch (err) {
      setState((s) => ({
        ...s,
        step: 'select_material',
        error: err instanceof Error ? err.message : '生成变体失败',
      }));
    }
  };

  const handleSelectVariant = async (variant: GeneratedVariant) => {
    try {
      const updated = await selectVariant(variant.id);
      setState((s) => ({
        ...s,
        selectedVariant: updated,
        variants: s.variants.map((v) => ({ ...v, is_selected: v.id === updated.id })),
      }));
    } catch (err) {
      setState((s) => ({ ...s, error: err instanceof Error ? err.message : '选择变体失败' }));
    }
  };

  const handleProceedToTemplate = () => {
    if (!state.selectedVariant) return;
    setState((s) => ({ ...s, step: 'select_template' }));
  };

  const handleSelectTemplate = (template: PrjTemplate) => {
    setState((s) => ({ ...s, selectedTemplate: template }));
  };

  const handleCompose = async () => {
    if (!state.selectedVariant || !state.selectedTemplate) return;

    setState((s) => ({ ...s, step: 'composing', error: null, composeTask: null }));

    try {
      const response = await submitCompose({
        generated_design_id: state.selectedVariant.id,
        prj_template_id: state.selectedTemplate.id,
      });
      setState((s) => ({ ...s, composeTask: { task_id: response.task_id, status: 'pending' } }));

      const completedTask = await pollComposeTask(response.task_id, (task) => {
        setState((s) => ({ ...s, composeTask: task }));
      });

      if (completedTask.status === 'completed' && completedTask.result) {
        setState((s) => ({
          ...s,
          step: 'complete',
          resultTifUrl: completedTask.result!.tif_url,
          resultFileName: completedTask.result!.file_name,
        }));
      } else {
        setState((s) => ({ ...s, step: 'select_template', error: completedTask.error || '合成失败' }));
      }
    } catch (err) {
      setState((s) => ({
        ...s,
        step: 'select_template',
        error: err instanceof Error ? err.message : 'TIF合成失败',
      }));
    }
  };

  const handleReset = () => {
    setState(initialState);
  };

  const renderStepIndicator = () => {
    const steps = [
      { key: 'select_material', label: '选择素材' },
      { key: 'generating_variants', label: '生成变体' },
      { key: 'select_variant', label: '选择设计' },
      { key: 'select_template', label: '选择模板' },
      { key: 'composing', label: '合成TIF' },
      { key: 'complete', label: '完成' },
    ];

    const currentIndex = steps.findIndex((s) => s.key === state.step);

    return (
      <div className="flex items-center justify-center mb-8">
        {steps.map((s, i) => (
          <div key={s.key} className="flex items-center">
            <div
              className={`
                w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                ${i <= currentIndex
                  ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950'
                  : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400'
                }
              `}
            >
              {i + 1}
            </div>
            {i < steps.length - 1 && (
              <div
                className={`
                  w-12 h-0.5 mx-1
                  ${i < currentIndex ? 'bg-zinc-950 dark:bg-zinc-50' : 'bg-zinc-200 dark:bg-zinc-800'}
                `}
              />
            )}
          </div>
        ))}
      </div>
    );
  };

  const renderError = () => {
    if (!state.error) return null;
    return (
      <div className="mb-6 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4">
        <div className="flex items-start gap-3">
          <svg className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-red-700 dark:text-red-300">{state.error}</p>
        </div>
      </div>
    );
  };

  const renderGeneratingProgress = () => {
    const task = state.variantsTask;
    return (
      <div className="max-w-md mx-auto text-center py-12">
        <div className="relative h-16 w-16 mx-auto mb-6">
          <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
          <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
        </div>
        <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100 mb-2">正在生成布料设计变体</h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          {task?.status === 'processing' ? 'AI 正在创作中...' : '准备中...'}
        </p>
      </div>
    );
  };

  const renderComposingProgress = () => {
    const task = state.composeTask;
    return (
      <div className="max-w-md mx-auto text-center py-12">
        <div className="relative h-16 w-16 mx-auto mb-6">
          <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
          <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
        </div>
        <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100 mb-2">正在合成 TIF 文件</h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          {task?.status === 'processing' ? '正在填充裁片区域...' : '准备中...'}
        </p>
      </div>
    );
  };

  const renderComplete = () => (
    <div className="max-w-lg mx-auto text-center py-8">
      <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
        <svg className="w-8 h-8 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h3 className="text-xl font-medium text-zinc-900 dark:text-zinc-100 mb-2">TIF 文件已生成</h3>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">{state.resultFileName}</p>
      <div className="flex items-center justify-center gap-4">
        {state.resultTifUrl && (
          <a
            href={state.resultTifUrl}
            download={state.resultFileName}
            className="inline-flex items-center gap-2 px-6 py-3 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 rounded-lg hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            下载 TIF
          </a>
        )}
        <button
          onClick={handleReset}
          className="px-6 py-3 border border-zinc-300 dark:border-zinc-700 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
        >
          重新开始
        </button>
      </div>
    </div>
  );

  return (
    <div>
      {renderStepIndicator()}
      {renderError()}

      {state.step === 'select_material' && (
        <div className="space-y-6">
          {isLoadingMaterials ? (
            <div className="flex items-center justify-center py-12">
              <div className="relative h-12 w-12">
                <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
                <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
              </div>
            </div>
          ) : (
            <>
              <MaterialSelector
                materials={materials}
                selectedMaterial={state.material}
                onSelectMaterial={handleSelectMaterial}
              />
              {state.material && (
                <button
                  onClick={handleGenerateVariants}
                  className="w-full rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
                >
                  生成 4 个布料设计变体
                </button>
              )}
            </>
          )}
        </div>
      )}

      {state.step === 'generating_variants' && renderGeneratingProgress()}

      {state.step === 'select_variant' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <VariantsGallery
            variants={state.variants}
            selectedVariantId={state.selectedVariant?.id ?? null}
            onSelectVariant={handleSelectVariant}
          />
          <div className="space-y-4">
            <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-lg">
              <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">已选择的设计</h4>
              {state.selectedVariant ? (
                <div className="flex items-center gap-3">
                  {state.selectedVariant.thumbnail_url && (
                    <img
                      src={state.selectedVariant.thumbnail_url}
                      alt="选中的设计"
                      className="w-16 h-16 rounded object-cover"
                    />
                  )}
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">
                    变体 #{state.selectedVariant.variant_index + 1}
                  </span>
                </div>
              ) : (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">请从左侧选择一个设计</p>
              )}
            </div>
            <button
              onClick={handleProceedToTemplate}
              disabled={!state.selectedVariant}
              className="w-full rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              下一步：选择服装模板
            </button>
          </div>
        </div>
      )}

      {state.step === 'select_template' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <PrjTemplateSelector
            templates={state.templates}
            selectedTemplateId={state.selectedTemplate?.id ?? null}
            onSelectTemplate={handleSelectTemplate}
          />
          <div className="space-y-4">
            <div className="p-4 bg-zinc-50 dark:bg-zinc-900 rounded-lg space-y-3">
              <div>
                <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-1">选中的设计</h4>
                <div className="flex items-center gap-2">
                  {state.selectedVariant?.thumbnail_url && (
                    <img src={state.selectedVariant.thumbnail_url} alt="" className="w-10 h-10 rounded object-cover" />
                  )}
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">变体 #{(state.selectedVariant?.variant_index ?? 0) + 1}</span>
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-1">选中的模板</h4>
                {state.selectedTemplate ? (
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">{state.selectedTemplate.name}</span>
                ) : (
                  <span className="text-sm text-zinc-500 dark:text-zinc-400">请从左侧选择模板</span>
                )}
              </div>
            </div>
            <button
              onClick={handleCompose}
              disabled={!state.selectedTemplate}
              className="w-full rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              开始合成 TIF
            </button>
          </div>
        </div>
      )}

      {state.step === 'composing' && renderComposingProgress()}
      {state.step === 'complete' && renderComplete()}
    </div>
  );
}
