import type {
  GeneratedDesign,
  PaginatedHistoryResponse,
} from '@/types/history';
import { apiRequest } from './api';

export async function fetchHistory(
  page: number = 1,
  size: number = 10
): Promise<PaginatedHistoryResponse> {
  return apiRequest<PaginatedHistoryResponse>(
    `/api/history?page=${page}&size=${size}`
  );
}

export async function fetchGeneratedDesign(id: number): Promise<GeneratedDesign> {
  return apiRequest<GeneratedDesign>(`/api/history/${id}`);
}

export async function deleteGeneratedDesign(id: number): Promise<void> {
  await apiRequest<void>(`/api/history/${id}`, { method: 'DELETE' });
}

export interface ExportResponse {
  task_id: string | null;
  generated_design_id: number;
  status: string;
  download_url?: string | null;
  upscaled_url?: string | null;
}

export interface ExportStatusResponse {
  task_id: string;
  generated_design_id: number | null;
  status: string;
  progress: number;
  current_step: string | null;
  download_url: string | null;
  upscaled_url: string | null;
  error: string | null;
}

export async function triggerExport(generatedDesignId: number): Promise<ExportResponse> {
  return apiRequest<ExportResponse>(
    `/api/export/generated-designs/${generatedDesignId}`,
    { method: 'POST' }
  );
}

export async function getExportStatus(taskId: string): Promise<ExportStatusResponse> {
  return apiRequest<ExportStatusResponse>(`/api/export/tasks/${taskId}`);
}
