import type { SegmentResponse, UploadProgress } from '@/types/fabric';

export async function segmentFabricPatches(
  file: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<SegmentResponse> {
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
          resolve(response);
        } catch {
          reject(new Error('Invalid response format'));
        }
      } else {
        try {
          const errorResponse = JSON.parse(xhr.responseText);
          reject(new Error(errorResponse.detail || 'Segmentation failed'));
        } catch {
          reject(new Error(`Segmentation failed with status ${xhr.status}`));
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
