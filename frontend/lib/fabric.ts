import type { SegmentResponse, SegmentTaskStatus, UploadProgress, FabricPatch } from '@/types/fabric';
import { NetworkError, fetchWithRetry } from './api';

export async function uploadFabricImage(
  file: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<string> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress({
          loaded: event.loaded,
          total: event.total,
          percentage: Math.round((event.loaded / event.total) * 100),
        });
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response: SegmentResponse = JSON.parse(xhr.responseText);
          resolve(response.task_id);
        } catch {
          reject(new Error('Invalid response format'));
        }
      } else {
        try {
          const errorResponse = JSON.parse(xhr.responseText);
          reject(new Error(errorResponse.detail || 'Upload failed'));
        } catch {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('Network error. Please try again.'));
    });

    xhr.addEventListener('abort', () => {
      reject(new Error('Upload cancelled'));
    });

    xhr.open('POST', '/api/fabric-patches/segment');
    xhr.withCredentials = true;
    xhr.send(formData);
  });
}

export async function pollSegmentStatus(
  taskId: string,
  maxAttempts: number = 60,
  intervalMs: number = 2000
): Promise<FabricPatch[]> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const status = await fetchWithRetry<SegmentTaskStatus>(
      `/api/fabric-patches/status/${taskId}`,
      { credentials: 'include' }
    );

    if (status.status === 'completed' && status.result) {
      return status.result.patches;
    }

    if (status.status === 'failed') {
      throw new Error(status.error || 'Segmentation failed');
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('Segmentation timeout. Please refresh to check status.');
}
