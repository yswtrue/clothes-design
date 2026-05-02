import type { GenerateRequest, GenerateResponse, TaskStatusResponse } from '@/types/generate';
import { apiRequest } from './api';

export interface PromptTemplateResponse {
  id: number;
  name: string;
  task_type: string;
  provider_type: string | null;
  template: string;
  description: string | null;
  is_default: boolean;
  is_active: boolean;
}

export async function getDefaultPromptTemplate(
  taskType: string,
  providerType?: string
): Promise<PromptTemplateResponse | null> {
  const params = new URLSearchParams();
  if (providerType) params.set('provider_type', providerType);
  const query = params.toString();
  const url = `/api/prompt-templates/default/${taskType}${query ? `?${query}` : ''}`;
  
  try {
    return await apiRequest<PromptTemplateResponse>(url);
  } catch {
    return null;
  }
}

export async function getPromptTemplates(
  taskType?: string
): Promise<PromptTemplateResponse[]> {
  const params = new URLSearchParams();
  if (taskType) params.set('task_type', taskType);
  const query = params.toString();
  const url = `/api/prompt-templates${query ? `?${query}` : ''}`;
  
  try {
    const response = await apiRequest<{ items: PromptTemplateResponse[] }>(url);
    return response.items || [];
  } catch {
    return [];
  }
}

export async function submitGeneration(request: GenerateRequest): Promise<GenerateResponse> {
  return apiRequest<GenerateResponse>(
    '/api/generate',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    }
  );
}

export async function pollTaskStatus(
  taskId: string,
  onProgress?: (task: TaskStatusResponse) => void,
  maxAttempts: number = 30,
  intervalMs: number = 2000
): Promise<TaskStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const task = await apiRequest<TaskStatusResponse>(
      `/api/generate/tasks/${taskId}`
    );

    if (onProgress) {
      onProgress(task);
    }

    if (task.status === 'completed') {
      return task;
    }

    if (task.status === 'failed') {
      throw new Error(task.error || 'Generation failed');
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('Generation timeout after 60 seconds');
}
