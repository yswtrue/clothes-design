'use client';

import { useState, useCallback } from 'react';
import Image from 'next/image';
import type { Clo3dRenderTaskStatus } from '@/types/clo3d';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const ZOOM_STEP = 0.25;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;

// ---------------------------------------------------------------------------
// Status labels (matching the backend enum values)
// ---------------------------------------------------------------------------
const STATUS_LABELS: Record<Clo3dRenderTaskStatus['status'], string> = {
  pending: '等待渲染',
  processing: '渲染中',
  completed: '渲染完成',
  failed: '渲染失败',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface RenderPreviewProps {
  task: Clo3dRenderTaskStatus | null;
  isLoading: boolean;
}

// ---------------------------------------------------------------------------
// SVG Spinner
// ---------------------------------------------------------------------------
function Spinner({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Progress bar (animated)
// ---------------------------------------------------------------------------
function ProgressBar({ status }: { status: 'pending' | 'processing' }) {
  const isProcessing = status === 'processing';
  return (
    <div className="w-full max-w-xs mx-auto">
      <div className="h-1.5 w-full rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
        <div
          className={`h-full rounded-full bg-zinc-950 dark:bg-zinc-50 transition-all ${
            isProcessing ? 'w-3/4 animate-pulse' : 'w-1/3'
          }`}
        />
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2 text-center">
        {isProcessing ? '正在渲染服装效果...' : '已加入渲染队列...'}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Idle state
// ---------------------------------------------------------------------------
function IdleState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-zinc-400 dark:text-zinc-500">
      <svg className="w-20 h-20 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1}
          d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
        />
      </svg>
      <p className="text-sm font-medium">分配材质并点击渲染以查看结果</p>
      <p className="text-xs mt-1">渲染完成后将在此处显示服装的前后效果图</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------
function ErrorState({ error }: { error: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-red-500 dark:text-red-400">
      <svg className="w-16 h-16 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
        />
      </svg>
      <p className="text-sm font-medium mb-1">渲染失败</p>
      <p className="text-xs max-w-sm text-center text-red-400 dark:text-red-500">
        {error || '未知错误，请检查参数后重试'}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading / in-progress state
// ---------------------------------------------------------------------------
function ProgressState({ status }: { status: 'pending' | 'processing' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-zinc-600 dark:text-zinc-400">
      <Spinner className="w-10 h-10 mb-4" />
      <p className="text-sm font-medium mb-1">{STATUS_LABELS[status]}</p>
      <ProgressBar status={status} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Image viewer with zoom controls
// ---------------------------------------------------------------------------
function ZoomableImage({
  src,
  alt,
  zoom,
  onZoomIn,
  onZoomOut,
  onReset,
}: {
  src: string;
  alt: string;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-full aspect-[3/4] rounded-lg overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900">
        <div
          className="w-full h-full flex items-center justify-center transition-transform duration-200"
          style={{ transform: `scale(${zoom})` }}
        >
          <Image
            src={src}
            alt={alt}
            fill
            className="object-contain"
            sizes="(max-width: 768px) 100vw, 40vw"
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onZoomOut}
          disabled={zoom <= ZOOM_MIN}
          className="w-8 h-8 flex items-center justify-center rounded-md border border-zinc-300 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          aria-label="缩小"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        </button>
        <span className="text-xs text-zinc-500 dark:text-zinc-400 min-w-[3rem] text-center tabular-nums">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={onZoomIn}
          disabled={zoom >= ZOOM_MAX}
          className="w-8 h-8 flex items-center justify-center rounded-md border border-zinc-300 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          aria-label="放大"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
        <button
          onClick={onReset}
          className="ml-1 px-2 py-1 text-[11px] font-medium text-zinc-500 dark:text-zinc-400 hover:text-zinc-950 dark:hover:text-zinc-50 transition-colors"
        >
          重置
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Completed state — front & back images side by side
// ---------------------------------------------------------------------------
function CompletedState({
  frontUrl,
  backUrl,
}: {
  frontUrl: string;
  backUrl: string;
}) {
  const [frontZoom, setFrontZoom] = useState(1);
  const [backZoom, setBackZoom] = useState(1);

  const adjustZoom = useCallback(
    (
      setter: React.Dispatch<React.SetStateAction<number>>,
      delta: number,
    ) => {
      setter((prev) => {
        const next = prev + delta;
        return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, next));
      });
    },
    [],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Front view */}
        <div>
          <h4 className="text-sm font-medium text-zinc-950 dark:text-zinc-50 mb-2 text-center">
            正面
          </h4>
          <ZoomableImage
            src={frontUrl}
            alt="服装正面渲染图"
            zoom={frontZoom}
            onZoomIn={() => adjustZoom(setFrontZoom, ZOOM_STEP)}
            onZoomOut={() => adjustZoom(setFrontZoom, -ZOOM_STEP)}
            onReset={() => setFrontZoom(1)}
          />
        </div>

        {/* Back view */}
        <div>
          <h4 className="text-sm font-medium text-zinc-950 dark:text-zinc-50 mb-2 text-center">
            背面
          </h4>
          <ZoomableImage
            src={backUrl}
            alt="服装背面渲染图"
            zoom={backZoom}
            onZoomIn={() => adjustZoom(setBackZoom, ZOOM_STEP)}
            onZoomOut={() => adjustZoom(setBackZoom, -ZOOM_STEP)}
            onReset={() => setBackZoom(1)}
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RenderPreview — main component
// ---------------------------------------------------------------------------
export default function RenderPreview({ task, isLoading }: RenderPreviewProps) {
  // --- Loading (initial fetch or submission in progress) ---
  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
        <div className="flex flex-col items-center justify-center py-16 text-zinc-500 dark:text-zinc-400">
          <Spinner className="w-10 h-10 mb-4" />
          <p className="text-sm font-medium">正在提交渲染任务...</p>
        </div>
      </div>
    );
  }

  // --- No task yet (idle) ---
  if (!task) {
    return (
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
        <IdleState />
      </div>
    );
  }

  // --- Pending / Processing ---
  if (task.status === 'pending' || task.status === 'processing') {
    return (
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
        <ProgressState status={task.status} />
      </div>
    );
  }

  // --- Failed ---
  if (task.status === 'failed') {
    return (
      <div className="rounded-xl border border-red-200 dark:border-red-900 bg-white dark:bg-zinc-950">
        <ErrorState error={task.error ?? '渲染任务失败'} />
      </div>
    );
  }

  // --- Completed ---
  if (task.front_url && task.back_url) {
    return (
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-5">
        <CompletedState frontUrl={task.front_url} backUrl={task.back_url} />
      </div>
    );
  }

  // --- Completed but missing image URLs (edge case) ---
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
      <div className="flex flex-col items-center justify-center py-16 text-zinc-400 dark:text-zinc-500">
        <p className="text-sm">渲染已完成但未返回图像</p>
      </div>
    </div>
  );
}

// Export types for consumers
export type { RenderPreviewProps };
