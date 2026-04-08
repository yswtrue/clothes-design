'use client';

interface PatternResultProps {
  patternUrl: string;
  fileName: string;
  fileSize?: number;
  dimensions?: { width: number; height: number };
  onGenerateAnother: () => void;
}

export default function PatternResult({
  patternUrl,
  fileName,
  fileSize,
  dimensions,
  onGenerateAnother,
}: PatternResultProps) {
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'Unknown';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden">
        <div className="aspect-square relative bg-zinc-100 dark:bg-zinc-800">
          <img
            src={patternUrl}
            alt={fileName}
            className="w-full h-full object-contain"
          />
        </div>
      </div>

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6">
        <h3 className="text-lg font-medium text-zinc-950 dark:text-zinc-50 mb-4">
          Pattern Details
        </h3>
        <dl className="space-y-3">
          <div className="flex justify-between">
            <dt className="text-sm text-zinc-600 dark:text-zinc-400">File Name</dt>
            <dd className="text-sm font-medium text-zinc-950 dark:text-zinc-50 font-mono">
              {fileName}
            </dd>
          </div>
          {fileSize && (
            <div className="flex justify-between">
              <dt className="text-sm text-zinc-600 dark:text-zinc-400">File Size</dt>
              <dd className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                {formatFileSize(fileSize)}
              </dd>
            </div>
          )}
          {dimensions && (
            <div className="flex justify-between">
              <dt className="text-sm text-zinc-600 dark:text-zinc-400">Dimensions</dt>
              <dd className="text-sm font-medium text-zinc-950 dark:text-zinc-50">
                {dimensions.width} × {dimensions.height} px
              </dd>
            </div>
          )}
        </dl>
      </div>

      <div className="flex gap-3">
        <a
          href={patternUrl}
          download={fileName}
          className="flex-1 rounded-md bg-zinc-950 dark:bg-zinc-50 px-4 py-2.5 text-sm font-medium text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors text-center"
        >
          Download Pattern
        </a>
        <button
          onClick={onGenerateAnother}
          className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-2.5 text-sm font-medium text-zinc-950 dark:text-zinc-50 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
        >
          Generate Another
        </button>
      </div>
    </div>
  );
}
