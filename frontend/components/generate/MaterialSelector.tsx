import type { Material } from '@/types/upload';

interface MaterialSelectorProps {
  materials: Material[];
  selectedMaterial: Material | null;
  onSelectMaterial: (material: Material) => void;
}

export default function MaterialSelector({
  materials,
  selectedMaterial,
  onSelectMaterial,
}: MaterialSelectorProps) {
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
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {materials.map((material) => {
          const isSelected = selectedMaterial?.id === material.id;
          return (
            <button
              key={material.id}
              onClick={() => onSelectMaterial(material)}
              className={`
                relative p-3 rounded-lg border-2 transition-all text-left
                ${
                  isSelected
                    ? 'border-zinc-950 dark:border-zinc-50 bg-zinc-100 dark:bg-zinc-800'
                    : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600'
                }
              `}
            >
              <div className="font-medium text-zinc-950 dark:text-zinc-50 truncate">
                {material.original_filename}
              </div>
              <div className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
                {(material.file_size / 1024 / 1024).toFixed(2)} MB
              </div>
              {material.meta?.style_analysis && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {material.meta.style_analysis.color_palette.slice(0, 3).map((color, idx) => (
                    <div
                      key={idx}
                      className="w-4 h-4 rounded-full border border-zinc-300 dark:border-zinc-700"
                      style={{ backgroundColor: color }}
                      title={color}
                    />
                  ))}
                </div>
              )}
            </button>
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
    </div>
  );
}
