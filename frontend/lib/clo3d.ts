import { apiRequest } from '@/lib/api';
import type {
  Clo3dProject,
  Clo3dRenderRequest,
  Clo3dRenderSubmitResponse,
  Clo3dRenderTaskStatus,
} from '@/types/clo3d';

export async function fetchClo3dProjects(params?: {
  category?: string;
  status?: string;
  page?: number;
  size?: number;
}): Promise<{ items: Clo3dProject[]; total: number; page: number; size: number }> {
  const searchParams = new URLSearchParams();
  if (params?.category) searchParams.set('category', params.category);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.size) searchParams.set('size', String(params.size));

  const qs = searchParams.toString();
  return apiRequest(`/api/clo3d/projects${qs ? `?${qs}` : ''}`);
}

export async function fetchClo3dProject(projectId: number): Promise<Clo3dProject> {
  return apiRequest<Clo3dProject>(`/api/clo3d/projects/${projectId}`);
}

export async function uploadClo3dProject(formData: FormData): Promise<Clo3dProject> {
  const response = await fetch('/api/clo3d/projects', {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed: ${response.status}`);
  }

  return response.json();
}

export async function submitClo3dRender(
  request: Clo3dRenderRequest
): Promise<Clo3dRenderSubmitResponse> {
  return apiRequest<Clo3dRenderSubmitResponse>('/api/clo3d/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
}

export async function fetchClo3dTaskStatus(
  taskId: string
): Promise<Clo3dRenderTaskStatus> {
  return apiRequest<Clo3dRenderTaskStatus>(`/api/clo3d/tasks/${taskId}`);
}

export async function pollClo3dTask(
  taskId: string,
  onProgress?: (task: Clo3dRenderTaskStatus) => void,
  maxAttempts: number = 120,
  intervalMs: number = 3000
): Promise<Clo3dRenderTaskStatus> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const task = await fetchClo3dTaskStatus(taskId);

    if (onProgress) {
      onProgress(task);
    }

    if (task.status === 'completed') {
      return task;
    }

    if (task.status === 'failed') {
      throw new Error(task.error || 'CLO3D 渲染失败');
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('渲染超时，请稍后重试');
}

export async function fetchRenderHistory(
  projectId: number,
  params?: { page?: number; size?: number }
): Promise<{ items: Clo3dRenderTaskStatus[]; total: number; page: number; size: number }> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.size) searchParams.set('size', String(params.size));

  const qs = searchParams.toString();
  return apiRequest(`/api/clo3d/projects/${projectId}/render-history${qs ? `?${qs}` : ''}`);
}

export interface ExtractedPiece {
  index: number;
  image_b64: string;
  bounds: { x: number; y: number; width: number; height: number };
}

export interface ExtractPiecesResponse {
  piece_count: number;
  pieces: ExtractedPiece[];
}

export async function extractPiecesFromScreenshot(
  file: File
): Promise<ExtractPiecesResponse> {
  const formData = new FormData();
  formData.append('screenshot', file);

  const response = await fetch('/api/clo3d/extract-pieces', {
    method: 'POST',
    credentials: 'include',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `提取失败: ${response.status}`);
  }

  return response.json();
}
