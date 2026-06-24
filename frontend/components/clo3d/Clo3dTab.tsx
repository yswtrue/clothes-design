'use client';

import { useState, useEffect, useCallback } from 'react';
import type { Clo3dProject, Clo3dRenderTaskStatus } from '@/types/clo3d';
import type { Material } from '@/types/upload';
import PieceSelector from '@/components/clo3d/PieceSelector';
import RenderPreview from '@/components/clo3d/RenderPreview';
import { fetchClo3dProjects } from '@/lib/clo3d';
import { apiRequest } from '@/lib/api';

export default function Clo3dTab() {
  const [projects, setProjects] = useState<Clo3dProject[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [selectedProject, setSelectedProject] = useState<Clo3dProject | null>(null);
  const [renderTask, setRenderTask] = useState<Clo3dRenderTaskStatus | null>(null);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isLoadingMaterials, setIsLoadingMaterials] = useState(true);

  useEffect(() => {
    loadProjects();
    loadMaterials();
  }, []);

  async function loadProjects() {
    setIsLoadingProjects(true);
    try {
      const data = await fetchClo3dProjects();
      setProjects(data.items);
    } catch {
      // ignore
    } finally {
      setIsLoadingProjects(false);
    }
  }

  async function loadMaterials() {
    setIsLoadingMaterials(true);
    try {
      const data = await apiRequest<{ items: Material[]; total: number }>('/api/materials?size=100');
      setMaterials(data.items || []);
    } catch {
      // ignore
    } finally {
      setIsLoadingMaterials(false);
    }
  }

  const handleRenderComplete = useCallback((task: Clo3dRenderTaskStatus) => {
    setRenderTask(task);
  }, []);

  const loading = isLoadingProjects || isLoadingMaterials;

  return (
    <div className="flex flex-col gap-6">
      {!selectedProject ? (
        /* ── Project list ── */
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">CLO3D 项目</h2>
            <button
              onClick={loadProjects}
              className="px-3 py-1.5 text-xs border border-zinc-300 dark:border-zinc-700 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              刷新
            </button>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-48 rounded-xl bg-zinc-100 dark:bg-zinc-800 animate-pulse" />
              ))}
            </div>
          ) : projects.length === 0 ? (
            <div className="text-center py-16 text-zinc-400">
              <p className="text-lg mb-2">暂无 CLO3D 项目</p>
              <p className="text-sm">在 Admin 面板上传 .zprj 项目文件</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedProject(p)}
                  className="group relative rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-zinc-400 dark:hover:border-zinc-600 transition-all text-left"
                >
                  {p.preview_url ? (
                    <div className="aspect-[3/4] bg-zinc-100 dark:bg-zinc-800">
                      <img src={p.preview_url} alt={p.name} className="w-full h-full object-cover" />
                    </div>
                  ) : (
                    <div className="aspect-[3/4] flex items-center justify-center bg-zinc-100 dark:bg-zinc-800 text-zinc-400">
                      <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                  )}
                  <div className="p-3">
                    <p className="font-medium text-sm text-zinc-950 dark:text-zinc-50 truncate">{p.name}</p>
                    <p className="text-xs text-zinc-500">{p.category} · {p.piece_count} 个衣片</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* ── Selected project view ── */
        <div>
          <button
            onClick={() => { setSelectedProject(null); setRenderTask(null); }}
            className="mb-4 text-sm text-zinc-500 hover:text-zinc-950 dark:hover:text-zinc-50 flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回项目列表
          </button>

          <PieceSelector
            project={selectedProject}
            materials={materials}
            onRenderComplete={handleRenderComplete}
          />

          {renderTask && (
            <div className="mt-6">
              <RenderPreview task={renderTask} isLoading={false} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
