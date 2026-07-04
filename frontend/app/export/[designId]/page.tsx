'use client';

import { use, useState, useEffect } from 'react';
import {
  EXPORT_TARGET_MULTIPLIERS,
  getExportMultiplierForResolution,
  getExportTargetResolution,
  triggerExport,
  pollExportStatus,
  type ExportTargetMultiplier,
} from '@/lib/export';
import { fetchGeneratedDesign } from '@/lib/history';
import type { ExportContentType, ExportFormat, ExportStatusResponse } from '@/types/export';
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
  const [exportFormat, setExportFormat] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [contentType, setContentType] = useState<ExportContentType>('pattern');
  const [sharpen, setSharpen] = useState(false);
  const [targetMultiplier, setTargetMultiplier] = useState<ExportTargetMultiplier>(8);

  const targetResolution = getExportTargetResolution(targetMultiplier);

  useEffect(() => {
    loadDesignPreview();
  }, [designIdNum]);

  const loadDesignPreview = async () => {
    setState('loading');
    setError(null);
    try {
      const design = await fetchGeneratedDesign(designIdNum);
      setPreviewUrl(design.thumbnail_url || design.image_url || null);
      const historicalSettings = design.export_settings?.tif ?? design.export_settings?.svg;
      if (historicalSettings?.content_type) {
        setContentType(historicalSettings.content_type);
      }
      if (historicalSettings?.sharpen !== null && historicalSettings?.sharpen !== undefined) {
        setSharpen(historicalSettings.sharpen);
      }
      setTargetMultiplier(getExportMultiplierForResolution(historicalSettings?.target_resolution));
      setState('idle');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load design');
      setState('error');
    }
  };

  const handleExport = async (format: ExportFormat) => {
    setState('exporting');
    setExportFormat(format);
    setError(null);
    setExportStatus(null);

    try {
      const response = await triggerExport(designIdNum, format, contentType, sharpen, targetResolution);

      if (!response.task_id && response.status === 'exported' && response.download_url) {
        setExportStatus({
          task_id: '',
          generated_design_id: designIdNum,
          format: format,
          status: 'exported',
          progress: 100,
          current_step: 'complete',
          download_url: response.download_url,
          upscaled_url: response.upscaled_url,
          content_type: response.content_type,
          sharpen: response.sharpen,
          target_resolution: response.target_resolution,
          error: null,
        });
        setState('complete');
        return;
      }

      if (!response.task_id) {
        throw new Error('No task ID returned');
      }

      const completedStatus = await pollExportStatus(response.task_id, (status) => {
        setExportStatus(status);
      });

      if (completedStatus.status === 'exported' && completedStatus.download_url) {
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
    setExportFormat(null);
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
                <div className="space-y-3 mb-6">
                  <div className="flex justify-between items-center py-2 border-b border-zinc-200 dark:border-zinc-800">
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      目标倍数
                    </span>
                    <div className="flex rounded-md border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                      {EXPORT_TARGET_MULTIPLIERS.map((multiplier) => (
                        <button
                          key={multiplier}
                          type="button"
                          onClick={() => setTargetMultiplier(multiplier)}
                          disabled={state === 'exporting'}
                          className={`px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                            targetMultiplier === multiplier
                              ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950'
                              : 'bg-white dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800'
                          }`}
                        >
                          {multiplier}x
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-zinc-200 dark:border-zinc-800">
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      输出最长边
                    </span>
                    <span className="text-sm text-zinc-600 dark:text-zinc-400">
                      {targetResolution.toLocaleString()}px
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

                <div className="space-y-3 mb-6">
                  <div className="flex justify-between items-center py-2 border-b border-zinc-200 dark:border-zinc-800">
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                      图案类型
                    </span>
                    <div className="flex rounded-md border border-zinc-200 dark:border-zinc-800 overflow-hidden">
                      <button
                        onClick={() => setContentType('line-art')}
                        className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                          contentType === 'line-art'
                            ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950'
                            : 'bg-white dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800'
                        }`}
                      >
                        线条型
                      </button>
                      <button
                        onClick={() => setContentType('pattern')}
                        className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                          contentType === 'pattern'
                            ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950'
                            : 'bg-white dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800'
                        }`}
                      >
                        图案型
                      </button>
                    </div>
                  </div>

                  <div className="flex justify-between items-center py-2">
                    <div>
                      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                        后期锐化
                      </span>
                      <p className="text-xs text-zinc-500 dark:text-zinc-500 mt-0.5">
                        减少放大后的模糊感，线条图案推荐开启
                      </p>
                    </div>
                    <button
                      onClick={() => setSharpen(!sharpen)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        sharpen ? 'bg-zinc-950 dark:bg-zinc-50' : 'bg-zinc-200 dark:bg-zinc-700'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white dark:bg-zinc-900 transition-transform ${
                          sharpen ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                </div>

                <div className="space-y-3">
                  <button
                    onClick={() => handleExport('svg')}
                    disabled={state === 'exporting'}
                    className="w-full rounded-md border-2 border-zinc-950 dark:border-zinc-50 bg-transparent px-4 py-3 text-sm font-medium text-zinc-950 dark:text-zinc-50 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {state === 'exporting' && exportFormat === 'svg' ? (
                      'Exporting SVG...'
                    ) : (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                        Export SVG (Vector)
                      </span>
                    )}
                  </button>

                  <button
                    onClick={() => handleExport('tif')}
                    disabled={state === 'exporting'}
                    className="w-full rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {state === 'exporting' && exportFormat === 'tif' ? (
                      'Exporting TIF...'
                    ) : (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        Export TIF (CMYK, Print-Ready)
                      </span>
                    )}
                  </button>
                </div>

                <p className="mt-4 text-xs text-zinc-500 dark:text-zinc-500 text-center">
                  SVG: Infinitely scalable vector format<br />
                  TIF: 300 DPI CMYK for professional printing
                </p>
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

        {state === 'complete' && exportStatus?.download_url && exportFormat && (
          <div className="max-w-2xl mx-auto space-y-6">
            <DownloadButton
              downloadUrl={exportStatus.download_url}
              designId={designIdNum}
              format={exportFormat}
              targetResolution={exportStatus.target_resolution ?? targetResolution}
            />
            <div className="text-center">
              <button
                onClick={handleReset}
                className="text-sm text-zinc-600 dark:text-zinc-400 hover:text-zinc-950 dark:hover:text-zinc-50 transition-colors"
              >
                Export Another Format
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
