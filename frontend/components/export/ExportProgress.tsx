'use client';

import type { ExportStatusResponse } from '@/types/export';

interface ExportProgressProps {
  status: ExportStatusResponse | null;
  isPolling: boolean;
  error?: string;
}

export default function ExportProgress({ status, isPolling, error }: ExportProgressProps) {
  if (!isPolling && !status && !error) return null;

  const getResolutionText = (targetResolution: number | null | undefined): string => (
    targetResolution ? `${targetResolution.toLocaleString()}px` : 'target'
  );

  const getStepText = (currentStep: string | null, format: string | null, targetResolution: number | null | undefined): string => {
    const formatLabel = format === 'tif' ? 'TIF' : 'SVG';
    if (currentStep === 'upscaling') {
      return `Step 1/2: Upscaling to ${getResolutionText(targetResolution)} resolution...`;
    }
    if (currentStep === 'vectorizing') {
      return `Step 2/2: Vectorizing to ${formatLabel}...`;
    }
    if (currentStep === 'converting') {
      return `Step 2/2: Converting to ${formatLabel} (CMYK)...`;
    }
    if (currentStep === 'complete') {
      return 'Export complete!';
    }
    return 'Preparing export...';
  };

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
                Export Failed
              </h3>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{error}</p>
            </div>
          </>
        ) : status?.status === 'failed' ? (
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
                Export Failed
              </h3>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                {status.error || 'An unknown error occurred during export.'}
              </p>
            </div>
          </>
        ) : (
          <>
            <div className="relative h-12 w-12">
              <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
              <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
            </div>
            <div className="text-center w-full">
              <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50">
                {getStepText(status?.current_step || null, status?.format || null, status?.target_resolution)}
              </h3>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                Processing high-resolution export... this may take 1-2 minutes
              </p>
              
              {status && status.progress > 0 && (
                <div className="mt-4 w-full max-w-xs mx-auto">
                  <div className="h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-zinc-950 dark:bg-zinc-50 transition-all duration-300 ease-out"
                      style={{ width: `${status.progress}%` }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-500">
                    {status.progress}% complete
                  </p>
                </div>
              )}

              {status?.task_id && (
                <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-500 font-mono">
                  Task ID: {status.task_id.slice(0, 8)}...
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
