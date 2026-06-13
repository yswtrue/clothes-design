import { apiRequest } from '@/lib/api';
import type { PrjTemplateDetail } from '@/types/preview';

export interface PrjTemplatePreviewResponse {
  template_id: number;
  generated_design_id: number;
  preview_url: string;
}

export interface ModelPreviewResponse {
  preview_url: string;
  status: 'completed';
  method: 'ai' | 'fallback';
}

export interface ModelPreviewSubmitResponse {
  task_id: string;
  status: 'pending';
}

export interface ModelPreviewTaskResult {
  status?: string;
  preview_url?: string;
  method?: 'ai' | 'fallback';
}

export interface ModelPreviewTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result: ModelPreviewTaskResult | null;
  error: string | null;
}

export async function fetchPrjTemplateDetail(templateId: number): Promise<PrjTemplateDetail> {
  return apiRequest<PrjTemplateDetail>(`/api/prj-templates/${templateId}`);
}

export async function fetchDxfTemplateFile(dxfUrl: string): Promise<Blob> {
  const response = await fetch(dxfUrl, { credentials: 'omit' });

  if (!response.ok) {
    throw new Error(`下载 DXF 文件失败：HTTP ${response.status}`);
  }

  return response.blob();
}

export async function createPrjTemplatePreview(
  templateId: number,
  generatedDesignId: number
): Promise<PrjTemplatePreviewResponse> {
  return apiRequest<PrjTemplatePreviewResponse>(
    `/api/prj-templates/${templateId}/preview`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ generated_design_id: generatedDesignId }),
    }
  );
}

export async function createModelPreview(
  imageDataUrl: string,
  templateId?: number,
  prompt?: string
): Promise<ModelPreviewSubmitResponse> {
  return apiRequest<ModelPreviewSubmitResponse>('/api/model-previews', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      image_data_url: imageDataUrl,
      template_id: templateId,
      prompt,
    }),
  });
}

export async function fetchModelPreviewTaskStatus(taskId: string): Promise<ModelPreviewTaskStatus> {
  return apiRequest<ModelPreviewTaskStatus>(`/api/model-previews/tasks/${taskId}`);
}

export async function pollModelPreviewTask(
  taskId: string,
  onProgress?: (task: ModelPreviewTaskStatus) => void,
  maxAttempts: number = 90,
  intervalMs: number = 2000
): Promise<ModelPreviewTaskStatus> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const task = await fetchModelPreviewTaskStatus(taskId);

    if (onProgress) {
      onProgress(task);
    }

    if (task.status === 'completed') {
      return task;
    }

    if (task.status === 'failed') {
      throw new Error(task.error || 'AI 模特预览生成失败');
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  return { task_id: taskId, status: 'pending', result: null, error: null };
}
