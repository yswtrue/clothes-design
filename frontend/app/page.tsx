'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getAccessToken } from '@/lib/token';
import Link from 'next/link';

export default function Home() {
  const router = useRouter();
  const isAuthenticated = getAccessToken();

  useEffect(() => {
    if (isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, router]);

  if (isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="text-zinc-600 dark:text-zinc-400">加载中...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black px-4">
      <div className="text-center max-w-2xl">
        <h1 className="text-4xl font-bold text-zinc-950 dark:text-zinc-50 mb-4">
          服装设计平台
        </h1>
        <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-8">
          AI 驱动的服装设计平台，帮助您快速创作独特的设计
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/login"
            className="px-6 py-3 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 rounded-md font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
          >
            登录
          </Link>
          <Link
            href="/register"
            className="px-6 py-3 border border-zinc-300 dark:border-zinc-700 text-zinc-950 dark:text-zinc-50 rounded-md font-medium hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors"
          >
            注册
          </Link>
        </div>
      </div>
    </div>
  );
}
