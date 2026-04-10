'use client';

import { TaskStatusResponse } from '@/types/generate';

interface GenerationProgressProps {
  task: TaskStatusResponse | null;
  isPolling: boolean;
  error?: string;
}

export default function GenerationProgress({ task, isPolling, error }: GenerationProgressProps) {
  if (!isPolling && !task && !error) return null;

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
      <div className="flex flex-col items-center gap-4">
        {error ? (
          <>
            <div className="h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center">
              <svg
                className="h-6 w-6 text-red-600 dark:text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <div className="text-center">
              <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50">
                生成失败
              </h3>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{error}</p>
            </div>
          </>
        ) : task?.status === 'failed' ? (
          <>
            <div className="h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center">
              <svg
                className="h-6 w-6 text-red-600 dark:text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <div className="text-center">
              <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50">
                生成失败
              </h3>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                {task.error || '生成过程中发生未知错误。'}
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="relative h-12 w-12">
              <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
              <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
            </div>
            <div className="text-center">
              <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50">
                {task?.status === 'processing' ? '处理中' : '已排队'}
              </h3>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                正在生成您的图案... 这可能需要 30-60 秒
              </p>
              {task?.task_id && (
                <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-500 font-mono">
                  任务 ID: {task.task_id.slice(0, 8)}...
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
