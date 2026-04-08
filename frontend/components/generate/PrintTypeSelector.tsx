type PrintType = 'seamless' | 'standalone' | 'full';

interface PrintTypeSelectorProps {
  selected: PrintType;
  onChange: (type: PrintType) => void;
  suggestedType?: PrintType;
}

const PRINT_TYPES: { value: PrintType; label: string; description: string }[] = [
  {
    value: 'seamless',
    label: 'Seamless Pattern',
    description: 'Repeating pattern that tiles without visible seams',
  },
  {
    value: 'standalone',
    label: 'Standalone Design',
    description: 'Individual design element for placement',
  },
  {
    value: 'full',
    label: 'Full Coverage',
    description: 'Complete design filling the entire garment',
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
        Print Type
      </label>
      <div className="space-y-3">
        {PRINT_TYPES.map((type) => {
          const isSelected = selected === type.value;
          const isSuggested = suggestedType === type.value;
          return (
            <button
              key={type.value}
              onClick={() => onChange(type.value)}
              className={`
                w-full text-left p-4 rounded-lg border-2 transition-all
                ${
                  isSelected
                    ? 'border-zinc-950 dark:border-zinc-50 bg-zinc-100 dark:bg-zinc-800'
                    : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600'
                }
              `}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
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
                    {isSuggested && (
                      <span className="text-xs bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 px-2 py-0.5 rounded">
                        Suggested
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1 ml-6">
                    {type.description}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
