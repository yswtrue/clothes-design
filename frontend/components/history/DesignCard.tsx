import type { Design } from '@/types/history';

interface DesignCardProps {
  design: Design;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onDelete: () => void;
}

export default function DesignCard({
  design,
  isExpanded,
  onToggleExpand,
  onDelete,
}: DesignCardProps) {
  const createdDate = new Date(design.created_at).toLocaleDateString();
  const updatedDate = new Date(design.updated_at).toLocaleDateString();

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
      <button
        onClick={onToggleExpand}
        className="w-full p-6 text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50 truncate">
              {design.name}
            </h3>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-zinc-600 dark:text-zinc-400">
              <span>Created {createdDate}</span>
              <span>Updated {updatedDate}</span>
              <span>{design.versions_count} versions</span>
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  design.status === 'published'
                    ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400'
                    : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-300'
                }`}
              >
                {design.status}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="p-2 rounded-md text-zinc-600 dark:text-zinc-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 transition-colors"
              aria-label="Delete design"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
            <svg
              className={`h-5 w-5 text-zinc-600 dark:text-zinc-400 transition-transform ${
                isExpanded ? 'rotate-180' : ''
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-zinc-200 dark:border-zinc-800 p-6">
          <div className="text-sm text-zinc-600 dark:text-zinc-400">
            Expand to show version list (loaded separately)
          </div>
        </div>
      )}
    </div>
  );
}
