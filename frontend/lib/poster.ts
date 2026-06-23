import type { PosterGenerateRequest, PosterGenerateResponse, PosterTaskStatusResponse } from '@/types/poster';
import { apiRequest } from './api';

export async function submitPosterGeneration(request: PosterGenerateRequest): Promise<PosterGenerateResponse> {
  return apiRequest<PosterGenerateResponse>(
    '/api/posters/generate',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    }
  );
}

export async function pollPosterTask(
  taskId: string,
  onProgress?: (task: PosterTaskStatusResponse) => void,
  maxAttempts: number = 60,
  intervalMs: number = 2000
): Promise<PosterTaskStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const task = await apiRequest<PosterTaskStatusResponse>(
      `/api/posters/tasks/${taskId}`
    );

    if (onProgress) {
      onProgress(task);
    }

    if (task.status === 'completed') {
      return task;
    }

    if (task.status === 'failed') {
      throw new Error(task.error || '海报生成失败');
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  return { task_id: taskId, status: 'pending' } as PosterTaskStatusResponse;
}
