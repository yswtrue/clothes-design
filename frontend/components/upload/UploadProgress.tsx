'use client';

import type { UploadProgress as UploadProgressType } from '@/types/upload';

interface UploadProgressProps {
  progress: UploadProgressType;
  filename: string;
}

export default function UploadProgress({ progress, filename }: UploadProgressProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-zinc-950 dark:text-zinc-50 truncate pr-4">
          {filename}
        </span>
        <span className="text-zinc-600 dark:text-zinc-400">
          {progress.percentage}%
        </span>
      </div>

      <div className="w-full bg-zinc-200 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
        <div
          className="bg-zinc-950 dark:bg-zinc-50 h-full transition-all duration-300 ease-out"
          style={{ width: `${progress.percentage}%` }}
        />
      </div>

      <div className="text-xs text-zinc-500 dark:text-zinc-500">
        {(progress.loaded / 1024 / 1024).toFixed(2)}MB / {(progress.total / 1024 / 1024).toFixed(2)}MB
      </div>
    </div>
  );
}
