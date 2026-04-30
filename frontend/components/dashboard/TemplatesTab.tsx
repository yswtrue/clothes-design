'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { apiRequest } from '@/lib/api';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Template {
  id: number;
  name: string;
  image_path: string;
  category: string;
  is_builtin: number;
  created_at: string;
}

type PageState = 'loading' | 'idle' | 'error';

export default function TemplatesTab() {
  const [state, setState] = useState<PageState>('loading');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadTemplates() {
      setState('loading');
      setError(null);

      try {
        const data = await apiRequest<Template[]>(`${API_URL}/api/prj-templates`);
        setTemplates(data);
        setState('idle');
      } catch (err) {
        console.error('获取模板时出错:', err);
        setError(err instanceof Error ? err.message : '获取模板失败');
        setState('error');
      }
    }

    loadTemplates();
  }, []);
  
  return (
    <div className="py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {state === 'loading' && (
          <div className="flex items-center justify-center py-12">
            <div className="relative h-12 w-12">
              <div className="absolute inset-0 rounded-full border-4 border-zinc-200 dark:border-zinc-800"></div>
              <div className="absolute inset-0 rounded-full border-4 border-zinc-950 dark:border-zinc-50 border-t-transparent animate-spin"></div>
            </div>
          </div>
        )}

        {state === 'error' && error && (
          <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4">
            <div className="flex items-start gap-3">
              <svg
                className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <div className="flex-1">
                <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                  错误
                </h3>
                <p className="mt-1 text-sm text-red-700 dark:text-red-300">{error}</p>
              </div>
            </div>
          </div>
        )}

        {state === 'idle' && templates.length === 0 && (
          <div className="text-center py-12 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800">
            <p className="text-zinc-600 dark:text-zinc-400">暂无可用模板。</p>
          </div>
        )}

        {state === 'idle' && templates.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {templates.map((template) => (
              <div 
                key={template.id} 
                className="border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 rounded-lg p-4 hover:shadow-lg dark:hover:shadow-zinc-800/50 transition-shadow"
              >
                <div className="relative w-full h-64 bg-zinc-50 dark:bg-zinc-800 rounded mb-3">
                  <Image
                    src={`${API_URL}${template.image_path}`}
                    alt={template.name}
                    fill
                    className="object-contain"
                    sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                  />
                </div>
                <h3 className="mt-3 font-medium text-lg text-zinc-950 dark:text-zinc-50">{template.name}</h3>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 capitalize">{template.category}</p>
                {template.is_builtin === 1 && (
                  <span className="inline-block mt-2 px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded">
                    内置模板
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
