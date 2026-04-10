'use client';

import type { StyleAnalysis } from '@/types/upload';

interface AnalysisResultProps {
  analysis: StyleAnalysis;
}

export default function AnalysisResult({ analysis }: AnalysisResultProps) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6 space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50 mb-4">
          风格分析完成
        </h2>
      </div>

      <div>
        <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          描述
        </h3>
        <p className="text-zinc-950 dark:text-zinc-50">
          {analysis.style_description}
        </p>
      </div>

      <div>
        <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
          图案类型
        </h3>
        <span className="inline-block px-3 py-1 bg-zinc-100 dark:bg-zinc-800 text-zinc-950 dark:text-zinc-50 rounded-full text-sm capitalize">
          {analysis.pattern_type}
        </span>
      </div>

      {analysis.color_palette.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">
            色彩方案
          </h3>
          <div className="flex flex-wrap gap-3">
            {analysis.color_palette.map((color, index) => (
              <div key={index} className="flex items-center gap-2">
                <div
                  className="w-10 h-10 rounded-md border border-zinc-300 dark:border-zinc-700"
                  style={{ backgroundColor: color }}
                  title={color}
                />
                <span className="text-xs font-mono text-zinc-600 dark:text-zinc-400">
                  {color.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {Object.keys(analysis.suggested_params).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
            建议参数
          </h3>
          <div className="bg-zinc-50 dark:bg-zinc-950 rounded-md p-4 font-mono text-xs">
            <pre className="text-zinc-700 dark:text-zinc-300 overflow-x-auto">
              {JSON.stringify(analysis.suggested_params, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
