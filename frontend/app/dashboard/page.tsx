'use client';

import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import { logout } from '@/lib/auth';
import { useState, useEffect } from 'react';
import UploadTab from '@/components/dashboard/UploadTab';
import GenerateTab from '@/components/dashboard/GenerateTab';
import HistoryTab from '@/components/dashboard/HistoryTab';
import TemplatesTab from '@/components/dashboard/TemplatesTab';
import OverviewTab from '@/components/dashboard/OverviewTab';
import VariantsWorkflowTab from '@/components/dashboard/VariantsWorkflowTab';
import { apiRequest } from '@/lib/api';

type TabType = 'overview' | 'upload' | 'generate' | 'variants' | 'history' | 'templates';

interface QuickStats {
  designs: number;
  materials: number;
  templates: number;
}

export default function DashboardPage() {
  const { user, isAuthenticated } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [stats, setStats] = useState<QuickStats>({ designs: 0, materials: 0, templates: 0 });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  async function loadStats() {
    setIsLoading(true);
    try {
      const [designs, materials, templates] = await Promise.all([
        apiRequest<{ total: number }>('/api/designs?size=1').catch(() => ({ total: 0 })),
        apiRequest<{ total: number }>('/api/materials?size=1').catch(() => ({ total: 0 })),
        apiRequest<unknown[]>('/api/prj-templates').catch(() => []),
      ]);

      setStats({
        designs: designs.total || 0,
        materials: materials.total || 0,
        templates: Array.isArray(templates) ? templates.length : 0,
      });
    } catch (error) {
      console.error('加载统计数据失败:', error);
    } finally {
      setIsLoading(false);
    }
  }

  const handleLogout = async () => {
    await logout();
    router.replace('/login');
  };

  const tabs: { id: TabType; label: string; icon: string }[] = [
    { id: 'overview' as const, label: '概览', icon: '🏠' },
    { id: 'upload' as const, label: '上传素材', icon: '📤' },
    { id: 'generate' as const, label: '生成图案', icon: '✨' },
    { id: 'variants' as const, label: '布料变体', icon: '🎨' },
    { id: 'history' as const, label: '设计历史', icon: '📋' },
    { id: 'templates' as const, label: '服装模板', icon: '👔' },
  ];

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <header className="sticky top-0 z-50 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-zinc-950 dark:bg-zinc-50 flex items-center justify-center">
                <span className="text-2xl">👗</span>
              </div>
              <div>
                <h1 className="text-xl font-semibold text-zinc-950 dark:text-zinc-50">
                  服装设计平台
                </h1>
                {isAuthenticated && user && (
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    欢迎，{user.username}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-sm border border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              退出登录
            </button>
          </div>

          <nav className="flex gap-2 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors
                  ${activeTab === tab.id
                    ? 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950'
                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                  }
                `}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && <OverviewTab stats={stats} isLoading={isLoading} onTabChange={setActiveTab} />}
        {activeTab === 'upload' && <UploadTab onUploadSuccess={loadStats} />}
        {activeTab === 'generate' && <GenerateTab />}
        {activeTab === 'variants' && <VariantsWorkflowTab />}
        {activeTab === 'history' && <HistoryTab />}
        {activeTab === 'templates' && <TemplatesTab />}
      </main>
    </div>
  );
}
