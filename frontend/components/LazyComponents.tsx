'use client';

import dynamic from 'next/dynamic';

export const LazyVersionList = dynamic(
  () => import('@/components/history/VersionList'),
  {
    loading: () => (
      <div className="flex justify-center items-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 dark:border-blue-400"></div>
      </div>
    ),
    ssr: false,
  }
);

export const LazyGenerationProgress = dynamic(
  () => import('@/components/generate/GenerationProgress'),
  {
    loading: () => (
      <div className="flex justify-center items-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-950 dark:border-zinc-50"></div>
      </div>
    ),
    ssr: false,
  }
);

export const LazyPatternResult = dynamic(
  () => import('@/components/generate/PatternResult'),
  {
    loading: () => (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-zinc-950 dark:border-zinc-50"></div>
      </div>
    ),
    ssr: false,
  }
);

export const LazyPreviewCanvas = dynamic(
  () => import('@/components/preview/PreviewCanvas'),
  {
    loading: () => (
      <div className="flex justify-center items-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 dark:border-blue-400"></div>
      </div>
    ),
    ssr: false,
  }
);
