'use client';

import { useState } from 'react';

interface Variant {
  id: number;
  material_id: number;
  image_url: string | null;
  thumbnail_url: string | null;
  variant_index: number;
  is_selected: boolean;
  created_at: string | null;
}

interface VariantsGalleryProps {
  variants: Variant[];
  selectedVariantId: number | null;
  onSelectVariant: (variant: Variant) => void;
  isLoading?: boolean;
}

export default function VariantsGallery({
  variants,
  selectedVariantId,
  onSelectVariant,
  isLoading = false,
}: VariantsGalleryProps) {
  const [loadedImages, setLoadedImages] = useState<Set<number>>(new Set());

  const handleImageLoad = (id: number) => {
    setLoadedImages((prev) => new Set(prev).add(id));
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="aspect-square rounded-lg bg-zinc-200 dark:bg-zinc-800 animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (variants.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-500 dark:text-zinc-400">
        暂无生成的设计变体
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          生成的布料设计 ({variants.length})
        </h3>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          点击选择喜欢的设计
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {variants.map((variant) => {
          const isSelected = selectedVariantId === variant.id;
          const imageUrl = variant.thumbnail_url || variant.image_url;

          return (
            <button
              key={variant.id}
              onClick={() => onSelectVariant(variant)}
              className={`
                relative aspect-square rounded-lg overflow-hidden transition-all
                ${isSelected
                  ? 'ring-4 ring-zinc-950 dark:ring-zinc-50 shadow-lg'
                  : 'ring-1 ring-zinc-200 dark:ring-zinc-800 hover:ring-2 hover:ring-zinc-400 dark:hover:ring-zinc-600'
                }
              `}
            >
              {imageUrl ? (
                <>
                  {!loadedImages.has(variant.id) && (
                    <div className="absolute inset-0 bg-zinc-200 dark:bg-zinc-800 animate-pulse" />
                  )}
                  <img
                    src={imageUrl}
                    alt={`变体 ${variant.variant_index + 1}`}
                    className={`
                      w-full h-full object-cover transition-opacity
                      ${loadedImages.has(variant.id) ? 'opacity-100' : 'opacity-0'}
                    `}
                    onLoad={() => handleImageLoad(variant.id)}
                  />
                </>
              ) : (
                <div className="w-full h-full bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center">
                  <span className="text-zinc-400 dark:text-zinc-600">无图片</span>
                </div>
              )}

              <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
                <span className="px-2 py-1 bg-black/60 text-white text-xs rounded">
                  #{variant.variant_index + 1}
                </span>
                {isSelected && (
                  <span className="px-2 py-1 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 text-xs rounded font-medium">
                    已选择
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
