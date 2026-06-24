'use client';

import { useState } from 'react';
import { segmentFabricPatches } from '@/lib/fabricSegmentation';
import DropZone from '@/components/upload/DropZone';
import PatchGallery from '@/components/fabric/PatchGallery';
import type { FabricPatch } from '@/types/fabric';

type UploadState = 'idle' | 'segmenting' | 'complete' | 'error';

export default function FabricPatchUploader() {
  const [state, setState] = useState<UploadState>('idle');
  const [patches, setPatches] = useState<FabricPatch[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleFileAccepted = async (file: File) => {
    setError(null);
    setState('segmenting');

    try {
      const results = await segmentFabricPatches(file);

      if (results.length === 0) {
        setError('未检测到布块，请确认图片中包含多个彩色布块且背景为白色。');
        setState('error');
        return;
      }

      setPatches(
        results.map((r) => ({
          index: r.index,
          url: r.blobUrl,
          width: r.width,
          height: r.height,
        })),
      );
      setState('complete');
    } catch (err) {
      setError(err instanceof Error ? err.message : '分割失败，请重试。');
      setState('error');
    }
  };

  const handleReset = () => {
    setState('idle');
    // Revoke old blob URLs to free memory
    for (const p of patches) {
      if (p.url.startsWith('blob:') || p.url.startsWith('data:')) {
        URL.revokeObjectURL(p.url);
      }
    }
    setPatches([]);
    setError(null);
  };

  return (
    <div>
      {state === 'idle' && <DropZone onFileAccepted={handleFileAccepted} />}

      {state === 'segmenting' && (
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
          <div className="flex items-center space-x-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-zinc-950 dark:border-zinc-50 border-t-transparent" />
            <div>
              <h2 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">
                正在分割布块...
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                纯浏览器处理，图片不会上传到服务器
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
