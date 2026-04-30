'use client';

import { useState } from 'react';
import { PrjTemplate } from '@/types/variants';

interface PrjTemplateSelectorProps {
  templates: PrjTemplate[];
  selectedTemplateId: number | null;
  onSelectTemplate: (template: PrjTemplate) => void;
  isLoading?: boolean;
}

export default function PrjTemplateSelector({
  templates,
  selectedTemplateId,
  onSelectTemplate,
  isLoading = false,
}: PrjTemplateSelectorProps) {
  const [loadedImages, setLoadedImages] = useState<Set<number>>(new Set());

  const handleImageLoad = (id: number) => {
    setLoadedImages((prev) => new Set(prev).add(id));
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-20 rounded-lg bg-zinc-200 dark:bg-zinc-800 animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (templates.length === 0) {
    return (
      <div className="text-center py-8 text-zinc-500 dark:text-zinc-400 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-lg">
        <svg
          className="mx-auto h-12 w-12 text-zinc-400 dark:text-zinc-600 mb-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <p>暂无可用的 PRJ 模板</p>
        <p className="text-xs mt-1">请先上传模板文件</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          选择服装模板
        </h3>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          {templates.length} 个模板可用
        </span>
      </div>

      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
        {templates.map((template) => {
          const isSelected = selectedTemplateId === template.id;

          return (
            <button
              key={template.id}
              onClick={() => onSelectTemplate(template)}
              className={`
                w-full flex items-center gap-4 p-3 rounded-lg transition-all text-left
                ${isSelected
                  ? 'bg-zinc-100 dark:bg-zinc-800 ring-2 ring-zinc-950 dark:ring-zinc-50'
                  : 'bg-white dark:bg-zinc-900 ring-1 ring-zinc-200 dark:ring-zinc-800 hover:ring-zinc-400 dark:hover:ring-zinc-600'
                }
              `}
            >
              <div className="w-14 h-14 rounded-md overflow-hidden flex-shrink-0 bg-zinc-100 dark:bg-zinc-800">
                {template.thumbnail_url ? (
                  <>
                    {!loadedImages.has(template.id) && (
                      <div className="w-full h-full animate-pulse bg-zinc-200 dark:bg-zinc-700" />
                    )}
                    <img
                      src={template.thumbnail_url}
                      alt={template.name}
                      className={`
                        w-full h-full object-cover
                        ${loadedImages.has(template.id) ? 'block' : 'hidden'}
                      `}
                      onLoad={() => handleImageLoad(template.id)}
                    />
                  </>
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <svg
                      className="w-6 h-6 text-zinc-400 dark:text-zinc-600"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                  </div>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-zinc-900 dark:text-zinc-100 truncate">
                    {template.name}
                  </span>
                  {isSelected && (
                    <span className="px-1.5 py-0.5 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 text-xs rounded">
                      已选
                    </span>
                  )}
                </div>
                {template.description && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate mt-0.5">
                    {template.description}
                  </p>
                )}
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-zinc-400 dark:text-zinc-500">
                    {template.piece_count} 个裁片
                  </span>
                </div>
              </div>

              <div className="flex-shrink-0">
                <div
                  className={`
                    w-5 h-5 rounded-full border-2 transition-colors
                    ${isSelected
                      ? 'border-zinc-950 dark:border-zinc-50 bg-zinc-950 dark:bg-zinc-50'
                      : 'border-zinc-300 dark:border-zinc-600'
                    }
                  `}
                >
                  {isSelected && (
                    <svg
                      className="w-full h-full text-white dark:text-zinc-950"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
