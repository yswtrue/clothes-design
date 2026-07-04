'use client';

import type { ExportFormat } from '@/types/export';

interface DownloadButtonProps {
  downloadUrl: string;
  designId: number;
  format: ExportFormat;
  targetResolution?: number | null;
}

const formatLabels: Record<ExportFormat, { name: string; extension: string; description: string }> = {
  svg: {
    name: 'SVG',
    extension: 'svg',
    description: 'Vector format, infinitely scalable',
  },
  tif: {
    name: 'TIF',
    extension: 'tif',
    description: 'CMYK, 300 DPI, print-ready',
  },
};

function formatResolutionLabel(targetResolution?: number | null): string {
  return targetResolution ? `${targetResolution}px` : 'export';
}

function formatResolutionSlug(targetResolution?: number | null): string {
  return targetResolution ? `${targetResolution}px` : 'export';
}

export default function DownloadButton({ downloadUrl, designId, format, targetResolution }: DownloadButtonProps) {
  const formatInfo = formatLabels[format];
  const resolutionLabel = formatResolutionLabel(targetResolution);
  const resolutionSlug = formatResolutionSlug(targetResolution);

  return (
    <div className="rounded-lg border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-6">
      <div className="flex flex-col items-center gap-4">
        <div className="h-12 w-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
          <svg
            className="h-6 w-6 text-green-600 dark:text-green-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <div className="text-center">
          <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50">
            Export Complete!
          </h3>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Your {formatInfo.name} file is ready for download{targetResolution ? ` (${resolutionLabel})` : ''}
          </p>
        </div>
        <a
          href={downloadUrl}
          download={`design-${designId}-${resolutionSlug}.${formatInfo.extension}`}
          className="inline-flex items-center gap-2 rounded-md bg-zinc-950 dark:bg-zinc-50 px-6 py-3 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          Download {formatInfo.name}
        </a>
        <p className="text-xs text-zinc-500 dark:text-zinc-500">
          Format: {formatInfo.name} • {formatInfo.description}
        </p>
      </div>
    </div>
  );
}
