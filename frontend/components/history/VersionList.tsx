'use client';

import { useState, useEffect } from 'react';
import type { DesignVersion } from '@/types/history';
import { fetchVersions } from '@/lib/history';
import ImagePreviewModal from './ImagePreviewModal';

interface VersionListProps {
  designId: number;
  onRollback: (version: number) => void;
  isRollingBack: boolean;
}

export default function VersionList({
  designId,
  onRollback,
  isRollingBack,
}: VersionListProps) {
  const [versions, setVersions] = useState<DesignVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewState, setPreviewState] = useState<{ url: string; version: number } | null>(null);

  useEffect(() => {
    loadVersions();
  }, [designId]);

  const loadVersions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVersions(designId);
      setVersions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load versions');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="relative h-8 w-8">
          <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
          <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
        <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        <button
          onClick={loadVersions}
          className="mt-2 text-sm text-red-600 dark:text-red-400 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-zinc-600 dark:text-zinc-400">
        No versions available
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
        Version History ({versions.length})
      </h4>
      <div className="space-y-2">
        {versions.map((version) => {
          const date = new Date(version.created_at).toLocaleString();
          const thumbnailUrl = version.data?.pattern_url;

          return (
            <div
              key={version.id}
              className="flex items-center gap-4 p-3 rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50"
            >
              {thumbnailUrl ? (
                <div 
                  className="h-12 w-12 rounded bg-zinc-100 dark:bg-zinc-700 overflow-hidden flex-shrink-0 cursor-pointer hover:ring-2 ring-zinc-400 dark:ring-zinc-500 transition-all"
                  onClick={() => setPreviewState({ url: thumbnailUrl, version: version.version })}
                  title="点击预览大图"
                >
                  <img
                    src={thumbnailUrl}
                    alt={`Version ${version.version}`}
                    className="h-full w-full object-cover"
                  />
                </div>
              ) : (
                <div className="h-12 w-12 rounded bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center flex-shrink-0" title="暂无图片">
                  <span className="text-[10px] text-zinc-400 dark:text-zinc-500">暂无</span>
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                    Version {version.version}
                  </span>
                  {version.version === versions[0].version && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400">
                      Current
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">{date}</p>
              </div>
              {version.version !== versions[0].version && (
                <button
                  onClick={() => onRollback(version.version)}
                  disabled={isRollingBack}
                  className="px-3 py-1.5 rounded-md text-sm font-medium text-zinc-950 dark:text-zinc-50 bg-zinc-100 dark:bg-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isRollingBack ? 'Rolling back...' : 'Rollback'}
                </button>
              )}
            </div>
          );
        })}
      </div>
      <ImagePreviewModal
        isOpen={!!previewState}
        imageUrl={previewState?.url || ''}
        version={previewState?.version || 0}
        onClose={() => setPreviewState(null)}
      />
    </div>
  );
}
