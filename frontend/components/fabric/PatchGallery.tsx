'use client';

import type { FabricPatch } from '@/types/fabric';

interface PatchGalleryProps {
  patches: FabricPatch[];
  onReset: () => void;
}

export default function PatchGallery({ patches, onReset }: PatchGalleryProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50">
          检测到 {patches.length} 个布块
        </h2>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
        {patches.map((patch) => (
          <div
            key={patch.index}
            className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden group"
          >
            <div className="aspect-square relative bg-zinc-100 dark:bg-zinc-800">
              <img
                src={patch.url}
                alt={`布料 ${patch.index + 1}`}
                className="w-full h-full object-contain p-2"
                loading="lazy"
                onError={(e) => {
                  const target = e.currentTarget;
                  target.style.display = 'none';
                  const parent = target.parentElement;
                  if (parent) {
                    const placeholder = document.createElement('div');
                    placeholder.className = 'w-full h-full flex items-center justify-center text-zinc-400 dark:text-zinc-600 text-sm';
                    placeholder.textContent = '加载失败';
                    parent.appendChild(placeholder);
                  }
                }}
              />
            </div>

            <div className="p-3 space-y-2">
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                {patch.width} × {patch.height} px
              </p>

              <a
                href={patch.url}
                download={`fabric-patch-${patch.index + 1}.png`}
                className="inline-flex items-center justify-center w-full gap-1.5 px-3 py-1.5 text-xs font-medium
                  bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 rounded-md
                  hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                下载
              </a>
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={onReset}
        className="w-full py-2 px-4 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 rounded-md font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
      >
        重新上传
      </button>
    </div>
  );
}
