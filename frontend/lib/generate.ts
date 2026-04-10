import type { GenerateRequest, GenerateResponse, TaskStatusResponse } from '@/types/generate';
import { apiRequest } from './api';

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
