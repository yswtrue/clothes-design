import type { GenerateRequest, GenerateResponse, TaskStatusResponse } from '@/types/generate';

export async function submitGeneration(request: GenerateRequest): Promise<GenerateResponse> {
  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to start generation');
  }

  return response.json();
}

export async function pollTaskStatus(
  taskId: string,
  onProgress?: (task: TaskStatusResponse) => void,
  maxAttempts: number = 30,
  intervalMs: number = 2000
): Promise<TaskStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const response = await fetch(`/api/generate/tasks/${taskId}`, {
      credentials: 'include',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Failed to fetch task status');
    }

    const task: TaskStatusResponse = await response.json();

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
