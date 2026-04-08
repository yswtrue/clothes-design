import type { ExportResponse, ExportStatusResponse } from '@/types/export';

export async function triggerExport(designId: number): Promise<ExportResponse> {
  const response = await fetch(`/api/export/designs/${designId}`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to start export');
  }

  return response.json();
}

export async function fetchExportStatus(taskId: string): Promise<ExportStatusResponse> {
  const response = await fetch(`/api/export/tasks/${taskId}`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to fetch export status');
  }

  return response.json();
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

    if (status.status === 'complete') {
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
