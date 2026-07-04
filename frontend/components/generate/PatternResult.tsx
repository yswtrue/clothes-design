'use client';

import { useState } from 'react';
import { triggerExport, pollExportStatus } from '@/lib/export';
import type { ExportContentType, ExportStatusResponse } from '@/types/export';
import ExportProgress from '@/components/export/ExportProgress';
import DownloadButton from '@/components/export/DownloadButton';

interface PatternResultProps {
  patternUrl: string;
  fileName: string;
  designId: number;
  fileSize?: number;
  dimensions?: { width: number; height: number };
  onGenerateAnother: () => void;
}

type TifExportState = 'idle' | 'exporting' | 'complete' | 'error';

export default function PatternResult({
  patternUrl,
  fileName,
  designId,
  fileSize,
  dimensions,
  onGenerateAnother,
}: PatternResultProps) {
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '未知';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // TIF export state
  const [tifExportState, setTifExportState] = useState<TifExportState>('idle');
  const [tifExportStatus, setTifExportStatus] = useState<ExportStatusResponse | null>(null);
  const [tifExportError, setTifExportError] = useState<string | null>(null);
  const [tifDownloadUrl, setTifDownloadUrl] = useState<string | null>(null);
  const [contentType, setContentType] = useState<ExportContentType>('pattern');
  const [sharpen, setSharpen] = useState(false);

  const handleExportTif = async () => {
    setTifExportState('exporting');
    setTifExportError(null);
    setTifExportStatus(null);
    setTifDownloadUrl(null);

    try {
      const response = await triggerExport(designId, 'tif', contentType, sharpen);

      if (!response.task_id && response.status === 'exported' && response.download_url) {
        setTifDownloadUrl(response.download_url);
        setTifExportStatus({
          task_id: '',
          generated_design_id: designId,
          format: 'tif',
          status: 'exported',
          progress: 100,
          current_step: 'complete',
          download_url: response.download_url,
          upscaled_url: response.upscaled_url,
          content_type: response.content_type,
          sharpen: response.sharpen,
          error: null,
        });
        setTifExportState('complete');
        return;
      }

      if (!response.task_id) {
        throw new Error('No task ID returned');
      }

      const completedStatus = await pollExportStatus(response.task_id, (status) => {
        setTifExportStatus(status);
      });

      if (completedStatus.status === 'exported' && completedStatus.download_url) {
        setTifDownloadUrl(completedStatus.download_url);
        setTifExportState('complete');
      } else if (completedStatus.status === 'failed') {
        setTifExportError(completedStatus.error || '导出TIF失败');
        setTifExportState('error');
      }
    } catch (err) {
      setTifExportError(err instanceof Error ? err.message : '导出TIF失败');
      setTifExportState('error');
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
        <div className="aspect-square relative bg-zinc-100 dark:bg-zinc-800">
          <img
            src={patternUrl}
            alt={fileName}
            className="w-full h-full object-contain"
          />
        </div>
      </div>

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
        <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50 mb-4">
          图案详情
        </h3>
        <dl className="space-y-3">
          <div className="flex justify-between">
            <dt className="text-sm text-zinc-600 dark:text-zinc-400">文件名</dt>
            <dd className="text-sm font-medium text-zinc-950 dark:text-zinc-50 font-mono">
              {fileName}
            </dd>
          </div>
          {fileSize && (
            <div className="flex justify-between">
              <dt className="text-sm text-zinc-600 dark:text-zinc-400">文件大小</dt>
              <dd className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                {formatFileSize(fileSize)}
              </dd>
            </div>
          )}
          {dimensions && (
            <div className="flex justify-between">
              <dt className="text-sm text-zinc-600 dark:text-zinc-400">尺寸</dt>
              <dd className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                {dimensions.width} × {dimensions.height} px
              </dd>
            </div>
          )}
        </dl>
      </div>

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
        <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50 mb-4">
          放大选项
        </h3>
        <div className="space-y-3">
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
      </div>

      {/* TIF Export Progress */}
      {tifExportState === 'exporting' && (
        <ExportProgress
          status={tifExportStatus}
          isPolling={true}
          error={tifExportError || undefined}
        />
      )}

      {/* TIF Export Error */}
      {tifExportState === 'error' && (
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
                导出TIF失败
              </h3>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">{tifExportError}</p>
            </div>
          </div>
          <button
            onClick={handleExportTif}
            className="mt-4 rounded-md bg-red-600 dark:bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 dark:hover:bg-red-600 transition-colors"
          >
            重试导出
          </button>
        </div>
      )}

      {/* TIF Export Complete */}
      {tifExportState === 'complete' && tifDownloadUrl && (
        <DownloadButton
          downloadUrl={tifDownloadUrl}
          designId={designId}
          format="tif"
        />
      )}

      <div className="flex flex-col gap-3">
        <div className="flex gap-3">
          <a
            href={patternUrl}
            download={fileName}
            className="flex-1 rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-2.5 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors text-center"
          >
            下载图案
          </a>
          <button
            onClick={handleExportTif}
            disabled={tifExportState === 'exporting'}
            className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-2.5 text-sm font-medium text-zinc-950 dark:text-zinc-50 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {tifExportState === 'exporting' ? '导出中...' : '导出TIF'}
          </button>
        </div>
        <button
          onClick={onGenerateAnother}
          className="w-full rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-2.5 text-sm font-medium text-zinc-950 dark:text-zinc-50 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
        >
          再生成一个
        </button>
      </div>
    </div>
  );
}
