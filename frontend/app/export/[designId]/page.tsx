'use client';

import { use, useState, useEffect } from 'react';
import { triggerExport, pollExportStatus } from '@/lib/export';
import { ExportStatusResponse } from '@/types/export';
import ExportProgress from '@/components/export/ExportProgress';
import DownloadButton from '@/components/export/DownloadButton';

type ExportState = 'idle' | 'loading' | 'exporting' | 'complete' | 'error';

interface PageProps {
  params: Promise<{
    designId: string;
  }>;
}

export default function ExportPage({ params }: PageProps) {
  const { designId } = use(params);
  const designIdNum = parseInt(designId, 10);

  const [state, setState] = useState<ExportState>('idle');
  const [exportStatus, setExportStatus] = useState<ExportStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    loadDesignPreview();
  }, [designIdNum]);

  const loadDesignPreview = async () => {
    setState('loading');
    setError(null);
    try {
      const response = await fetch(`/api/designs/${designIdNum}`, {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to load design');
      }

      const design = await response.json();
      if (design.preview_state?.pattern_url) {
        setPreviewUrl(design.preview_state.pattern_url);
      }
      setState('idle');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load design');
      setState('error');
    }
  };

  const handleExport = async () => {
    setState('exporting');
    setError(null);
    setExportStatus(null);

    try {
      const response = await triggerExport(designIdNum);

      const completedStatus = await pollExportStatus(response.task_id, (status) => {
        setExportStatus(status);
      });

      if (completedStatus.status === 'complete' && completedStatus.download_url) {
        setState('complete');
      } else if (completedStatus.status === 'failed') {
        setError(completedStatus.error || 'Export failed');
        setState('error');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export design');
      setState('error');
    }
  };

  const handleReset = () => {
    setState('idle');
    setExportStatus(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-zinc-950 dark:text-zinc-50">
            Export Design
          </h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            Export high-resolution TIF file for professional printing
          </p>
        </div>

        {state === 'loading' && (
          <div className="flex items-center justify-center py-12">
            <div className="relative h-12 w-12">
              <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
              <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
            </div>
          </div>
        )}

        {state === 'error' && !exportStatus && (
          <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4">
            <div className="flex items-start gap-3">
              <svg
                className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <div className="flex-1">
                <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                  Error
                </h3>
                <p className="mt-1 text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            </div>
            <button
              onClick={loadDesignPreview}
              className="mt-4 rounded-md bg-red-600 dark:bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 dark:hover:bg-red-600 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {(state === 'idle' || state === 'exporting') && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
                <h2 className="text-lg font-medium text-zinc-950 dark:text-zinc-50 mb-4">
                  Design Preview
                </h2>
                {previewUrl ? (
                  <div className="aspect-square w-full max-w-md mx-auto bg-zinc-100 dark:bg-zinc-800 rounded-lg overflow-hidden">
                    <img
                      src={previewUrl}
                      alt="Design preview"
                      className="w-full h-full object-contain"
                    />
                  </div>
                ) : (
                  <div className="aspect-square w-full max-w-md mx-auto bg-zinc-100 dark:bg-zinc-800 rounded-lg flex items-center justify-center">
                    <p className="text-zinc-500 dark:text-zinc-500">No preview available</p>
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
                <h2 className="text-lg font-medium text-zinc-950 dark:text-zinc-50 mb-4">
                  Export Options
                </h2>
                <div className="space-y-3">
                  <div className="flex justify-between items-center py-2 border-b border-zinc-200 dark:border-zinc-800">
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      Resolution
                    </span>
                    <span className="text-sm text-zinc-600 dark:text-zinc-400">
                      12K (12000px)
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-zinc-200 dark:border-zinc-800">
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      Format
                    </span>
                    <span className="text-sm text-zinc-600 dark:text-zinc-400">
                      TIF (CMYK)
                    </span>
                  </div>
                  <div className="flex justify-between items-center py-2">
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      Processing Time
                    </span>
                    <span className="text-sm text-zinc-600 dark:text-zinc-400">
                      ~1-2 minutes
                    </span>
                  </div>
                </div>

                <button
                  onClick={handleExport}
                  disabled={state === 'exporting'}
                  className="w-full mt-6 rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {state === 'exporting' ? 'Exporting...' : 'Start Export'}
                </button>
              </div>
            </div>

            <div className="lg:col-span-1">
              {state === 'exporting' && (
                <ExportProgress
                  status={exportStatus}
                  isPolling={true}
                  error={error || undefined}
                />
              )}
            </div>
          </div>
        )}

        {state === 'complete' && exportStatus?.download_url && (
          <div className="max-w-2xl mx-auto space-y-6">
            <DownloadButton
              downloadUrl={exportStatus.download_url}
              designId={designIdNum}
            />
            <div className="text-center">
              <button
                onClick={handleReset}
                className="text-sm text-zinc-600 dark:text-zinc-400 hover:text-zinc-950 dark:hover:text-zinc-50 transition-colors"
              >
                Export Another Design
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
