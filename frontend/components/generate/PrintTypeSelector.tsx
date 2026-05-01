type PrintType = 'seamless' | 'standalone' | 'full';

interface PrintTypeSelectorProps {
  selected: PrintType;
  onChange: (type: PrintType) => void;
  suggestedType?: PrintType;
}

function SeamlessIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none">
      <rect x="2" y="2" width="10" height="10" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="14" y="2" width="10" height="10" rx="1" fill="currentColor" opacity="0.5" />
      <rect x="26" y="2" width="10" height="10" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="38" y="2" width="8" height="10" rx="1" fill="currentColor" opacity="0.5" />
      <rect x="2" y="14" width="10" height="10" rx="1" fill="currentColor" opacity="0.5" />
      <rect x="14" y="14" width="10" height="10" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="26" y="14" width="10" height="10" rx="1" fill="currentColor" opacity="0.5" />
      <rect x="38" y="14" width="8" height="10" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="2" y="26" width="10" height="10" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="14" y="26" width="10" height="10" rx="1" fill="currentColor" opacity="0.5" />
      <rect x="26" y="26" width="10" height="10" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="38" y="26" width="8" height="10" rx="1" fill="currentColor" opacity="0.5" />
      <rect x="2" y="38" width="10" height="8" rx="1" fill="currentColor" opacity="0.5" />
      <rect x="14" y="38" width="10" height="8" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="26" y="38" width="10" height="8" rx="1" fill="currentColor" opacity="0.5" />
      <rect x="38" y="38" width="8" height="8" rx="1" fill="currentColor" opacity="0.3" />
    </svg>
  );
}

function StandaloneIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none">
      <rect x="2" y="2" width="44" height="44" rx="4" stroke="currentColor" strokeWidth="2" strokeDasharray="4 2" opacity="0.3" />
      <circle cx="24" cy="24" r="12" fill="currentColor" opacity="0.5" />
      <path d="M24 16l2.5 5 5.5.8-4 3.9.9 5.3-4.9-2.6-4.9 2.6.9-5.3-4-3.9 5.5-.8L24 16z" fill="currentColor" />
    </svg>
  );
}

function FullCoverIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none">
      <rect x="2" y="2" width="44" height="44" rx="4" fill="currentColor" opacity="0.2" />
      <path d="M8 12c4-4 12-4 16 0s12 4 16 0" stroke="currentColor" strokeWidth="2" opacity="0.5" />
      <path d="M8 24c4-4 12-4 16 0s12 4 16 0" stroke="currentColor" strokeWidth="2" opacity="0.7" />
      <path d="M8 36c4-4 12-4 16 0s12 4 16 0" stroke="currentColor" strokeWidth="2" opacity="0.5" />
      <circle cx="12" cy="18" r="3" fill="currentColor" opacity="0.6" />
      <circle cx="36" cy="30" r="3" fill="currentColor" opacity="0.6" />
      <circle cx="24" cy="38" r="2" fill="currentColor" opacity="0.4" />
    </svg>
  );
}

const PRINT_TYPES: { 
  value: PrintType; 
  label: string; 
  description: string;
  example: string;
  Icon: React.ComponentType<{ className?: string }>;
}[] = [
  {
    value: 'seamless',
    label: '无缝图案',
    description: '重复平铺无缝拼接的图案，适合布料印花',
    example: '格子、条纹、碎花、几何纹理',
    Icon: SeamlessIcon,
  },
  {
    value: 'standalone',
    label: '独立设计',
    description: '单独的设计元素，可放置在特定位置',
    example: 'Logo、徽章、胸前图案',
    Icon: StandaloneIcon,
  },
  {
    value: 'full',
    label: '全覆盖',
    description: '填充整个服装的完整大面积设计',
    example: '渐变、泼墨、抽象艺术',
    Icon: FullCoverIcon,
  },
];

export default function PrintTypeSelector({
  selected,
  onChange,
  suggestedType,
}: PrintTypeSelectorProps) {
  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium text-zinc-950 dark:text-zinc-50">
        印刷类型
      </label>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PRINT_TYPES.map((type) => {
          const isSelected = selected === type.value;
          const isSuggested = suggestedType === type.value;
          const Icon = type.Icon;
          return (
            <button
              key={type.value}
              onClick={() => onChange(type.value)}
              className={`
                relative text-left p-4 rounded-lg border-2 transition-all
                ${
                  isSelected
                    ? 'border-zinc-950 dark:border-zinc-50 bg-zinc-100 dark:bg-zinc-800'
                    : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600'
                }
              `}
            >
              {isSuggested && (
                <span className="absolute -top-2 -right-2 text-xs bg-emerald-500 text-white px-2 py-0.5 rounded-full">
                  推荐
                </span>
              )}
              
              <div className="flex flex-col items-center text-center">
                <div className={`
                  w-16 h-16 mb-3 rounded-lg flex items-center justify-center
                  ${isSelected 
                    ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950' 
                    : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400'
                  }
                `}>
                  <Icon className="w-10 h-10" />
                </div>
                
                <div className="flex items-center gap-2 mb-1">
                  <div
                    className={`
                      w-4 h-4 rounded-full border-2 flex items-center justify-center
                      ${
                        isSelected
                          ? 'border-zinc-950 dark:border-zinc-50'
                          : 'border-zinc-300 dark:border-zinc-700'
                      }
                    `}
                  >
                    {isSelected && (
                      <div className="w-2 h-2 rounded-full bg-zinc-950 dark:bg-zinc-50" />
                    )}
                  </div>
                  <span className="font-medium text-zinc-950 dark:text-zinc-50">
                    {type.label}
                  </span>
                </div>
                
                <p className="text-xs text-zinc-600 dark:text-zinc-400 mb-2">
                  {type.description}
                </p>
                
                <p className="text-xs text-zinc-500 dark:text-zinc-500 italic">
                  例：{type.example}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
