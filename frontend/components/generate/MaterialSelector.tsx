'use client';

import { useState } from 'react';
import type { Material } from '@/types/upload';

interface MaterialSelectorProps {
  materials: Material[];
  selectedMaterial: Material | null;
  onSelectMaterial: (material: Material) => void;
  onDeleteMaterial?: (materialId: number) => Promise<void>;
}

function PreviewModal({
  material,
  onClose,
}: {
  material: Material;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="relative max-w-4xl max-h-[90vh] bg-white dark:bg-zinc-900 rounded-lg overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-2 right-2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        {material.thumbnail_url ? (
          <img
            src={material.thumbnail_url}
            alt={material.original_filename}
            className="max-w-full max-h-[80vh] object-contain"
          />
        ) : (
          <div className="w-96 h-64 flex items-center justify-center text-zinc-500">
            无预览图
          </div>
        )}
        <div className="p-4 border-t border-zinc-200 dark:border-zinc-700">
          <p className="font-medium text-zinc-950 dark:text-zinc-50">{material.original_filename}</p>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
            {(material.file_size / 1024 / 1024).toFixed(2)} MB
          </p>
        </div>
      </div>
    </div>
  );
}

function DeleteConfirmModal({
  material,
  onConfirm,
  onCancel,
  isDeleting,
}: {
  material: Material;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onCancel}
    >
      <div
        className="bg-white dark:bg-zinc-900 rounded-lg p-6 max-w-sm mx-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50 mb-2">
          确认删除
        </h3>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
          确定要删除素材 <span className="font-medium">{material.original_filename}</span> 吗？此操作无法撤销。
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isDeleting && (
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            )}
            {isDeleting ? '删除中...' : '删除'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function MaterialSelector({
  materials,
  selectedMaterial,
  onSelectMaterial,
  onDeleteMaterial,
}: MaterialSelectorProps) {
  const [previewMaterial, setPreviewMaterial] = useState<Material | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Material | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    if (!deleteTarget || !onDeleteMaterial) return;
    
    setIsDeleting(true);
    try {
      await onDeleteMaterial(deleteTarget.id);
      setDeleteTarget(null);
    } catch (error) {
      console.error('Failed to delete material:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  if (materials.length === 0) {
    return (
      <div className="text-center py-8 text-zinc-600 dark:text-zinc-400">
        未找到素材。<a href="/upload" className="underline">上传素材</a>开始创作。
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
        选择素材
      </label>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {materials.map((material) => {
          const isSelected = selectedMaterial?.id === material.id;
          return (
            <div
              key={material.id}
              className={`
                relative rounded-lg border-2 transition-all overflow-hidden group
                ${
                  isSelected
                    ? 'border-zinc-950 dark:border-zinc-50 ring-2 ring-zinc-950/20 dark:ring-zinc-50/20'
                    : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600'
                }
              `}
            >
              <button
                onClick={() => onSelectMaterial(material)}
                className="w-full text-left"
              >
                <div className="aspect-square bg-zinc-100 dark:bg-zinc-800 relative">
                  {material.thumbnail_url ? (
                    <img
                      src={material.thumbnail_url}
                      alt={material.original_filename}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-zinc-400">
                      <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                  )}
                  {isSelected && (
                    <div className="absolute top-2 right-2 w-6 h-6 bg-zinc-950 dark:bg-zinc-50 rounded-full flex items-center justify-center">
                      <svg className="w-4 h-4 text-white dark:text-zinc-950" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </div>
                <div className="p-2">
                  <p className="text-sm font-medium text-zinc-950 dark:text-zinc-50 truncate">
                    {material.original_filename}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    {(material.file_size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  {material.meta?.style_analysis && (
                    <div className="mt-1 flex gap-1">
                      {material.meta.style_analysis.color_palette.slice(0, 4).map((color, idx) => (
                        <div
                          key={idx}
                          className="w-3 h-3 rounded-full border border-zinc-300 dark:border-zinc-600"
                          style={{ backgroundColor: color }}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </button>
              
              <div className="absolute top-2 left-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {material.thumbnail_url && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setPreviewMaterial(material);
                    }}
                    className="w-7 h-7 bg-black/50 hover:bg-black/70 rounded-full flex items-center justify-center text-white"
                    title="预览大图"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                    </svg>
                  </button>
                )}
                {onDeleteMaterial && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget(material);
                    }}
                    className="w-7 h-7 bg-red-500/80 hover:bg-red-600 rounded-full flex items-center justify-center text-white"
                    title="删除素材"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {selectedMaterial?.meta?.style_analysis && (
        <div className="bg-zinc-100 dark:bg-zinc-800 rounded-lg p-4 mt-4">
          <h4 className="text-sm font-medium text-zinc-950 dark:text-zinc-50 mb-2">
            风格分析
          </h4>
          <p className="text-sm text-zinc-700 dark:text-zinc-300 mb-3">
            {selectedMaterial.meta.style_analysis.style_description}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-600 dark:text-zinc-400">图案类型：</span>
            <span className="text-xs font-medium bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 px-2 py-1 rounded">
              {selectedMaterial.meta.style_analysis.pattern_type}
            </span>
          </div>
        </div>
      )}

      {previewMaterial && (
        <PreviewModal
          material={previewMaterial}
          onClose={() => setPreviewMaterial(null)}
        />
      )}

      {deleteTarget && (
        <DeleteConfirmModal
          material={deleteTarget}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={isDeleting}
        />
      )}
    </div>
  );
}
