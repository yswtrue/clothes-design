import type {
  GenerateVariantsRequest,
  GenerateVariantsResponse,
  VariantsTaskStatusResponse,
  GeneratedVariant,
  PrjTemplate,
  ComposeRequest,
  ComposeResponse,
  ComposeTaskStatusResponse,
} from '@/types/variants';
import { apiRequest } from './api';

export async function submitVariantsGeneration(
  request: GenerateVariantsRequest
): Promise<GenerateVariantsResponse> {
  return apiRequest<GenerateVariantsResponse>('/api/generate/variants', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
}

export async function pollVariantsTask(
  taskId: string,
  onProgress?: (task: VariantsTaskStatusResponse) => void,
  maxAttempts: number = 60,
  intervalMs: number = 2000
): Promise<VariantsTaskStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const task = await apiRequest<VariantsTaskStatusResponse>(
      `/api/generate/variants/tasks/${taskId}`
    );

    if (onProgress) {
      onProgress(task);
    }

    if (task.status === 'completed') {
      return task;
    }

    if (task.status === 'failed') {
      throw new Error(task.error || 'Variants generation failed');
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('Variants generation timeout');
}

export async function getVariantsByMaterial(
  materialId: number
): Promise<GeneratedVariant[]> {
  const response = await apiRequest<{ items: GeneratedVariant[] }>(
    `/api/generate/variants?material_id=${materialId}`
  );
  return response.items;
}

export async function selectVariant(variantId: number): Promise<GeneratedVariant> {
  return apiRequest<GeneratedVariant>(`/api/generate/variants/${variantId}/select`, {
    method: 'POST',
  });
}

export async function getPrjTemplates(): Promise<PrjTemplate[]> {
  const response = await apiRequest<{ items: PrjTemplate[] }>(
    '/api/prj-templates?is_active=true'
  );
  return response.items;
}

export async function getPrjTemplate(id: number): Promise<PrjTemplate> {
  return apiRequest<PrjTemplate>(`/api/prj-templates/${id}`);
}

export async function submitCompose(
  request: ComposeRequest
): Promise<ComposeResponse> {
  return apiRequest<ComposeResponse>('/api/designs/compose', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
}

export async function pollComposeTask(
  taskId: string,
  onProgress?: (task: ComposeTaskStatusResponse) => void,
  maxAttempts: number = 120,
  intervalMs: number = 2000
): Promise<ComposeTaskStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const task = await apiRequest<ComposeTaskStatusResponse>(
      `/api/designs/compose/tasks/${taskId}`
    );

    if (onProgress) {
      onProgress(task);
    }

    if (task.status === 'completed') {
      return task;
    }

    if (task.status === 'failed') {
      throw new Error(task.error || 'TIF composition failed');
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('TIF composition timeout');
}
