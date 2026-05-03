'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { fetchHistory, deleteGeneratedDesign } from '@/lib/history';
import type { MaterialWithDesigns, GeneratedDesign } from '@/types/history';
import ConfirmModal from '@/components/history/ConfirmModal';
import Pagination from '@/components/history/Pagination';

type PageState = 'loading' | 'idle' | 'deleting' | 'error';

interface ConfirmModalState {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  variant: 'danger' | 'default';
  onConfirm: () => void;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400',
    generating: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400',
    exporting: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400',
    exported: 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-400',
    failed: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-300'}`}>
      {status}
    </span>
  );
}

function GeneratedDesignCard({
  design,
  onExport,
  onDelete,
}: {
  design: GeneratedDesign;
  onExport: () => void;
  onDelete: () => void;
}) {
  const imageUrl = design.thumbnail_url || design.image_url;
  
  return (
    <div className="group relative rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 overflow-hidden">
      <div className="aspect-square relative bg-zinc-100 dark:bg-zinc-800">
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={`Design variant ${design.variant_index}`}
            fill
            unoptimized
            className="object-cover"
            sizes="(max-width: 768px) 50vw, 25vw"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-zinc-400">
            <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
        {design.is_selected && (
          <div className="absolute top-2 left-2 bg-blue-500 text-white text-xs px-2 py-0.5 rounded">
            已选中
          </div>
        )}
      </div>
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            #{design.variant_index + 1}
          </span>
          <StatusBadge status={design.status} />
        </div>
        {design.created_at && (
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">
            {new Date(design.created_at).toLocaleDateString()}
          </p>
        )}
        <div className="flex gap-2">
          <button
            onClick={onExport}
            disabled={!['completed', 'exported'].includes(design.status)}
            className="flex-1 px-2 py-1.5 text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded hover:bg-blue-100 dark:hover:bg-blue-900/40 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {design.exported_at ? '重新导出' : '导出'}
          </button>
          <button
            onClick={onDelete}
            className="px-2 py-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  );
}

function MaterialCard({
  material,
  isExpanded,
  onToggleExpand,
  onExportDesign,
  onDeleteDesign,
}: {
  material: MaterialWithDesigns;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onExportDesign: (designId: number) => void;
  onDeleteDesign: (design: GeneratedDesign) => void;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
      <div
        role="button"
        tabIndex={0}
        onClick={onToggleExpand}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleExpand();
          }
        }}
        className="w-full p-4 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-lg overflow-hidden bg-zinc-100 dark:bg-zinc-800 flex-shrink-0">
            {material.thumbnail_url ? (
              <Image
                src={material.thumbnail_url}
                alt={material.original_filename || 'Material'}
                width={64}
                height={64}
                unoptimized
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-zinc-400">
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-medium text-zinc-900 dark:text-zinc-100 truncate">
              {material.original_filename || `素材 #${material.id}`}
            </h3>
            <div className="mt-1 flex items-center gap-3 text-sm text-zinc-500 dark:text-zinc-400">
              {material.created_at && (
                <span>{new Date(material.created_at).toLocaleDateString()}</span>
              )}
              <span>{material.designs_count} 个生成结果</span>
            </div>
          </div>
          <svg
            className={`w-5 h-5 text-zinc-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {isExpanded && material.designs.length > 0 && (
        <div className="border-t border-zinc-200 dark:border-zinc-700 p-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {material.designs.map((design) => (
              <GeneratedDesignCard
                key={design.id}
                design={design}
                onExport={() => onExportDesign(design.id)}
                onDelete={() => onDeleteDesign(design)}
              />
            ))}
          </div>
        </div>
      )}

      {isExpanded && material.designs.length === 0 && (
        <div className="border-t border-zinc-200 dark:border-zinc-700 p-8 text-center text-zinc-500 dark:text-zinc-400">
          暂无生成结果
        </div>
      )}
    </div>
  );
}

export default function HistoryTab() {
  const router = useRouter();
  const [state, setState] = useState<PageState>('loading');
  const [materials, setMaterials] = useState<MaterialWithDesigns[]>([]);
  const [expandedMaterialIds, setExpandedMaterialIds] = useState<Set<number>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

  const [confirmModal, setConfirmModal] = useState<ConfirmModalState>({
    isOpen: false,
    title: '',
    message: '',
    confirmText: '',
    variant: 'default',
    onConfirm: () => {},
  });

  const MATERIALS_PER_PAGE = 10;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setState('loading');
      setError(null);
      setSuccessMessage(null);

      try {
        const response = await fetchHistory(currentPage, MATERIALS_PER_PAGE);
        if (!cancelled) {
          setMaterials(response.items);
          setTotalPages(response.pages);
          setState('idle');
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载历史失败');
          setState('error');
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [currentPage, retryTrigger]);

  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  function toggleExpand(materialId: number) {
    setExpandedMaterialIds((prev) => {
      const next = new Set(prev);
      if (next.has(materialId)) {
        next.delete(materialId);
      } else {
        next.add(materialId);
      }
      return next;
    });
  }

  function confirmDeleteDesign(design: GeneratedDesign) {
    setConfirmModal({
      isOpen: true,
      title: '删除生成结果',
      message: `确定要删除此生成结果吗？此操作无法撤销。`,
      confirmText: '删除',
      variant: 'danger',
      onConfirm: () => handleDeleteDesign(design),
    });
  }

  async function handleDeleteDesign(design: GeneratedDesign) {
    setConfirmModal((prev) => ({ ...prev, isOpen: false }));
    setState('deleting');
    setError(null);

    try {
      await deleteGeneratedDesign(design.id);

      setMaterials((prev) =>
        prev.map((m) =>
          m.id === design.material_id
            ? { ...m, designs: m.designs.filter((d) => d.id !== design.id), designs_count: m.designs_count - 1 }
            : m
        )
      );

      setSuccessMessage('删除成功');
      setState('idle');
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
      setState('error');
    }
  }

  function handlePageChange(page: number) {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function handleExport(designId: number) {
    router.push(`/export/${designId}`);
  }

  return (
    <div className="py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        {successMessage && (
          <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
            <p className="text-green-800 dark:text-green-200">{successMessage}</p>
          </div>
        )}

        {error && state === 'error' && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-800 dark:text-red-200">{error}</p>
            <button
              onClick={() => setRetryTrigger((prev) => prev + 1)}
              className="mt-2 text-red-600 dark:text-red-400 underline hover:text-red-700 dark:hover:text-red-300"
            >
              重试
            </button>
          </div>
        )}

        {state === 'loading' && (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 dark:border-blue-400"></div>
          </div>
        )}

        {state === 'idle' && materials.length === 0 && (
          <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg shadow">
            <svg
              className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">暂无历史</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">上传素材开始创作。</p>
          </div>
        )}

        {state !== 'loading' && materials.length > 0 && (
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">生成历史</h2>
          </div>
        )}

        {state !== 'loading' && materials.length > 0 && (
          <div className="space-y-4">
            {materials.map((material) => (
              <MaterialCard
                key={material.id}
                material={material}
                isExpanded={expandedMaterialIds.has(material.id)}
                onToggleExpand={() => toggleExpand(material.id)}
                onExportDesign={handleExport}
                onDeleteDesign={confirmDeleteDesign}
              />
            ))}
          </div>
        )}

        {state !== 'loading' && materials.length > 0 && totalPages > 1 && (
          <div className="mt-8">
            <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={handlePageChange} />
          </div>
        )}

        <ConfirmModal
          isOpen={confirmModal.isOpen}
          title={confirmModal.title}
          message={confirmModal.message}
          confirmText={confirmModal.confirmText}
          cancelText="取消"
          variant={confirmModal.variant}
          onConfirm={confirmModal.onConfirm}
          onCancel={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
        />
      </div>
    </div>
  );
}
