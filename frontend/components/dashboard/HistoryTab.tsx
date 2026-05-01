'use client';

import { useState, useEffect } from 'react';
import { fetchDesigns, deleteDesign, rollbackVersion, triggerExport, getExportStatus } from '@/lib/history';
import type { Design } from '@/types/history';
import DesignCard from '@/components/history/DesignCard';
import { LazyVersionList } from '@/components/LazyComponents';
import ConfirmModal from '@/components/history/ConfirmModal';
import Pagination from '@/components/history/Pagination';

type PageState = 'loading' | 'idle' | 'deleting' | 'rolling-back' | 'error';

interface ConfirmModalState {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  variant: 'danger' | 'default';
  onConfirm: () => void;
}

export default function HistoryTab() {
  const [state, setState] = useState<PageState>('loading');
  const [designs, setDesigns] = useState<Design[]>([]);
  const [expandedDesignIds, setExpandedDesignIds] = useState<Set<number>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [rollingBackDesignId, setRollingBackDesignId] = useState<number | null>(null);
  const [exportingDesignId, setExportingDesignId] = useState<number | null>(null);
  const [retryTrigger, setRetryTrigger] = useState(0);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const [confirmModal, setConfirmModal] = useState<ConfirmModalState>({
    isOpen: false,
    title: '',
    message: '',
    confirmText: '',
    variant: 'default',
    onConfirm: () => {},
  });

  const DESIGNS_PER_PAGE = 10;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setState('loading');
      setError(null);
      setSuccessMessage(null);

      try {
        const response = await fetchDesigns(currentPage, DESIGNS_PER_PAGE);
        if (!cancelled) {
          setDesigns(response.items);
          setTotalPages(response.pages);
          setState('idle');
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载设计失败');
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

  function toggleExpand(designId: number) {
    setExpandedDesignIds((prev) => {
      const next = new Set(prev);
      if (next.has(designId)) {
        next.delete(designId);
      } else {
        next.add(designId);
      }
      return next;
    });
  }

  function confirmDelete(design: Design) {
    setConfirmModal({
      isOpen: true,
      title: '删除设计',
      message: `确定要删除"${design.name}"吗？此操作无法撤销。`,
      confirmText: '删除',
      variant: 'danger',
      onConfirm: () => handleDelete(design.id),
    });
  }

  async function handleDelete(designId: number) {
    setConfirmModal((prev) => ({ ...prev, isOpen: false }));
    setState('deleting');
    setError(null);

    try {
      await deleteDesign(designId);

      setDesigns((prev) => prev.filter((d) => d.id !== designId));

      setExpandedDesignIds((prev) => {
        const next = new Set(prev);
        next.delete(designId);
        return next;
      });

      setSuccessMessage('设计删除成功');
      setState('idle');

      if (designs.length === 1 && currentPage > 1) {
        setCurrentPage(currentPage - 1);
      } else if (designs.length === 1 && currentPage === 1) {
        setRetryTrigger(prev => prev + 1);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除设计失败');
      setState('error');
    }
  }

  function toggleSelectionMode() {
    setSelectionMode(!selectionMode);
    setSelectedIds(new Set());
  }

  function toggleSelectAll() {
    if (selectedIds.size === designs.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(designs.map(d => d.id)));
    }
  }

  function toggleSelectDesign(id: number) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function confirmBatchDelete() {
    if (selectedIds.size === 0) return;
    setConfirmModal({
      isOpen: true,
      title: '批量删除设计',
      message: `确定要删除选中的 ${selectedIds.size} 个设计吗？此操作无法撤销。`,
      confirmText: '删除',
      variant: 'danger',
      onConfirm: () => handleBatchDelete(),
    });
  }

  async function handleBatchDelete() {
    setConfirmModal((prev) => ({ ...prev, isOpen: false }));
    setState('deleting');
    setError(null);

    try {
      await Promise.all(Array.from(selectedIds).map(id => deleteDesign(id)));

      setSuccessMessage(`成功删除了 ${selectedIds.size} 个设计`);
      setState('idle');
      setSelectionMode(false);
      setSelectedIds(new Set());
      setRetryTrigger(prev => prev + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量删除设计失败');
      setState('error');
    }
  }

  function confirmRollback(designId: number, designName: string, versionNumber: number) {
    setConfirmModal({
      isOpen: true,
      title: '回滚到版本',
      message: `将"${designName}"回滚到版本 ${versionNumber}？这将使用版本 ${versionNumber} 的数据创建一个新版本。`,
      confirmText: '回滚',
      variant: 'default',
      onConfirm: () => handleRollback(designId, versionNumber),
    });
  }

  async function handleRollback(designId: number, versionNumber: number) {
    setConfirmModal((prev) => ({ ...prev, isOpen: false }));
    setState('rolling-back');
    setRollingBackDesignId(designId);
    setError(null);

    try {
      const response = await rollbackVersion(designId, versionNumber);
      setSuccessMessage(`已回滚到版本 ${versionNumber}。新版本 ${response.version} 已创建。`);
      setState('idle');
      setRollingBackDesignId(null);

      setExpandedDesignIds((prev) => {
        const next = new Set(prev);
        next.delete(designId);
        return next;
      });
      setTimeout(() => {
        setExpandedDesignIds((prev) => {
          const next = new Set(prev);
          next.add(designId);
          return next;
        });
      }, 100);
    } catch (err) {
      setError(err instanceof Error ? err.message : '版本回滚失败');
      setState('error');
      setRollingBackDesignId(null);
    }
  }

  function handlePageChange(page: number) {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function handleExport(designId: number) {
    setExportingDesignId(designId);
    setError(null);

    try {
      const { task_id } = await triggerExport(designId);
      
      // Poll for export status
      const maxAttempts = 60;
      let attempts = 0;
      
      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const status = await getExportStatus(task_id);
        
        if (status.status === 'complete' && status.download_url) {
          // Trigger download
          const link = document.createElement('a');
          link.href = status.download_url;
          link.download = `design-${designId}-export.tif`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          
          setSuccessMessage('导出完成，文件已开始下载');
          setExportingDesignId(null);
          return;
        }
        
        if (status.status === 'failed') {
          throw new Error(status.error || '导出失败');
        }
        
        attempts++;
      }
      
      throw new Error('导出超时，请重试');
    } catch (err) {
      setError(err instanceof Error ? err.message : '导出失败');
      setExportingDesignId(null);
    }
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
              onClick={() => setRetryTrigger(prev => prev + 1)}
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

        {state === 'idle' && designs.length === 0 && (
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
            <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">暂无设计</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              上传素材开始创作。
            </p>
          </div>
        )}

        {state !== 'loading' && designs.length > 0 && (
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">设计历史</h2>
            <button 
              onClick={toggleSelectionMode}
              className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            >
              {selectionMode ? '取消选择' : '选择'}
            </button>
          </div>
        )}

        {selectionMode && designs.length > 0 && (
          <div className="mb-4 flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
            <div className="flex items-center space-x-2">
              <input 
                type="checkbox"
                checked={selectedIds.size === designs.length}
                onChange={toggleSelectAll}
                className="w-4 h-4 rounded border-zinc-300 text-zinc-600 focus:ring-zinc-500 bg-white dark:bg-zinc-700 dark:border-zinc-600 cursor-pointer"
              />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">全选</span>
            </div>
            <button
              onClick={confirmBatchDelete}
              disabled={selectedIds.size === 0}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                selectedIds.size > 0 
                  ? 'bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50' 
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed dark:bg-gray-800 dark:text-gray-600'
              }`}
            >
              删除选中 ({selectedIds.size})
            </button>
          </div>
        )}

        {state !== 'loading' && designs.length > 0 && (
          <div className="space-y-4">
            {designs.map((design) => (
              <div key={design.id} className="flex gap-4">
                {selectionMode && (
                  <div className="flex-none flex items-start pt-6">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(design.id)}
                      onChange={() => toggleSelectDesign(design.id)}
                      className="w-5 h-5 rounded border-zinc-300 text-zinc-600 focus:ring-zinc-500 bg-white dark:bg-zinc-700 dark:border-zinc-600 cursor-pointer"
                    />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <DesignCard
                    design={design}
                    isExpanded={expandedDesignIds.has(design.id)}
                    onToggleExpand={() => toggleExpand(design.id)}
                    onDelete={() => confirmDelete(design)}
                    onExport={() => handleExport(design.id)}
                    isExporting={exportingDesignId === design.id}
                  />
                  {expandedDesignIds.has(design.id) && (
                    <div className="bg-gray-50 dark:bg-gray-800 border-x border-b border-gray-200 dark:border-gray-700 rounded-b-lg p-4">
                      <LazyVersionList
                        designId={design.id}
                        onRollback={(versionNumber) =>
                          confirmRollback(design.id, design.name, versionNumber)
                        }
                        isRollingBack={rollingBackDesignId === design.id}
                      />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {state !== 'loading' && designs.length > 0 && totalPages > 1 && (
          <div className="mt-8">
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={handlePageChange}
            />
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
