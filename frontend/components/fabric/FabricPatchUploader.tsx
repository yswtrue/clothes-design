'use client';

import { useState } from 'react';
import { uploadFabricImage, pollSegmentStatus } from '@/lib/fabric';
import DropZone from '@/components/upload/DropZone';
import PatchGallery from '@/components/fabric/PatchGallery';
import type { UploadProgress, FabricPatch } from '@/types/fabric';

type UploadState = 'idle' | 'uploading' | 'segmenting' | 'complete' | 'error';

export default function FabricPatchUploader() {
  const [state, setState] = useState<UploadState>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress>({ loaded: 0, total: 0, percentage: 0 });
  const [patches, setPatches] = useState<FabricPatch[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleFileAccepted = async (file: File) => {
    setSelectedFile(file);
    setError(null);
    setState('uploading');

    try {
      const taskId = await uploadFabricImage(file, setUploadProgress);
      setState('segmenting');

      const result = await pollSegmentStatus(taskId);
      setPatches(result);
      setState('complete');
    } catch (err) {
      setError(err instanceof Error ? err.message : '分割失败，请重试。');
      setState('error');
    }
  };

  const handleReset = () => {
    setState('idle');
    setSelectedFile(null);
    setUploadProgress({ loaded: 0, total: 0, percentage: 0 });
    setPatches([]);
    setError(null);
  };

  return (
    <div>
      {state === 'idle' && (
        <DropZone onFileAccepted={handleFileAccepted} />
      )}

      {state === 'uploading' && selectedFile && (
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
          <h2 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50 mb-4">
            上传中...
          </h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-zinc-950 dark:text-zinc-50 truncate pr-4">
                {selectedFile.name}
              </span>
              <span className="text-zinc-600 dark:text-zinc-400">
                {uploadProgress.percentage}%
              </span>
            </div>

            <div className="w-full bg-zinc-200 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-zinc-950 dark:bg-zinc-50 h-full transition-all duration-300 ease-out"
                style={{ width: `${uploadProgress.percentage}%` }}
              />
            </div>

            <div className="text-xs text-zinc-500 dark:text-zinc-500">
              {(uploadProgress.loaded / 1024 / 1024).toFixed(2)}MB / {(uploadProgress.total / 1024 / 1024).toFixed(2)}MB
            </div>
          </div>
        </div>
      )}

      {state === 'segmenting' && (
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
          <div className="flex items-center space-x-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-zinc-950 dark:border-zinc-50 border-t-transparent" />
            <div>
              <h2 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">
                正在分割布块...
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                后台处理中，请耐心等待
              </p>
            </div>
          </div>
        </div>
      )}

      {state === 'complete' && patches.length > 0 && (
        <PatchGallery patches={patches} onReset={handleReset} />
      )}

      {state === 'error' && error && (
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
          <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 text-sm">
            {error}
          </div>
          <button
            onClick={handleReset}
            className="w-full py-2 px-4 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 rounded-md font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
          >
            重试
          </button>
        </div>
      )}
    </div>
  );
}
