import type { UploadResponse, Material, UploadProgress, UploadError } from '@/types/upload';
import { apiRequest } from './api';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

export function validateFile(file: File): UploadError | null {
  if (file.size > MAX_FILE_SIZE) {
    return {
      message: `File size exceeds 50MB limit (${(file.size / 1024 / 1024).toFixed(2)}MB)`,
      code: 'FILE_TOO_LARGE',
    };
  }

  const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
  if (!validTypes.includes(file.type)) {
    return {
      message: `Unsupported file type. Please upload JPG, PNG, or WebP images.`,
      code: 'INVALID_FILE_TYPE',
    };
  }

  return null;
}

export async function uploadFile(
  file: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadResponse> {
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
          const response = JSON.parse(xhr.responseText);
          resolve(response);
        } catch (error) {
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

    xhr.open('POST', '/api/upload');
    xhr.send(formData);
  });
}

export async function fetchMaterial(materialId: number): Promise<Material> {
  return apiRequest<Material>(`/api/materials/${materialId}`);
}

export async function pollForAnalysis(
  materialId: number,
  maxAttempts: number = 30,
  intervalMs: number = 2000
): Promise<Material> {
  let attempts = 0;

  while (attempts < maxAttempts) {
    const material = await fetchMaterial(materialId);

    if (material.meta?.style_analysis) {
      return material;
    }

    attempts++;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('Analysis timeout. Please refresh to check status.');
}
