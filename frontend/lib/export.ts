import type { ExportContentType, ExportFormat, ExportResponse, ExportStatusResponse } from '@/types/export';
import { apiRequest } from './api';

export async function triggerExport(
  designId: number,
  format: ExportFormat = 'svg',
  contentType: ExportContentType = 'pattern',
  sharpen: boolean = false,
): Promise<ExportResponse> {
  return apiRequest<ExportResponse>(
    `/api/export/generated-designs/${designId}?format=${format}&content_type=${contentType}&sharpen=${sharpen}`,
    {
      method: 'POST',
    }
  );
}

export interface MaterialExportResponse {
  task_id: string | null;
  material_id: number;
  format: ExportFormat;
  status: string;
  download_url: string | null;
}

export async function triggerMaterialExport(
  materialId: number,
  format: ExportFormat = 'tif',
  contentType: ExportContentType = 'pattern',
  sharpen: boolean = false,
  targetResolution: number = 12000,
): Promise<MaterialExportResponse> {
  return apiRequest<MaterialExportResponse>(
    `/api/export/materials/${materialId}?format=${format}&content_type=${contentType}&sharpen=${sharpen}&target_resolution=${targetResolution}`,
    {
      method: 'POST',
    }
  );
}

export async function fetchExportStatus(taskId: string): Promise<ExportStatusResponse> {
  return apiRequest<ExportStatusResponse>(`/api/export/tasks/${taskId}`);
}

export async function pollExportStatus(
  taskId: string,
  onProgress?: (status: ExportStatusResponse) => void,
  maxAttempts: number = 30,
  intervalMs: number = 3000
): Promise<ExportStatusResponse> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const status = await fetchExportStatus(taskId);

    if (onProgress) {
      onProgress(status);
    }

    if (status.status === 'exported') {
      return status;
    }

    if (status.status === 'failed') {
      throw new Error(status.error || 'Export failed');
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('Export timeout after 90 seconds');
}
