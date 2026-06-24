'use client';

import { useState, useMemo, useCallback, useEffect } from 'react';
import Image from 'next/image';
import type { Clo3dProject, Clo3dRenderTaskStatus } from '@/types/clo3d';
import type { Material } from '@/types/upload';
import { submitClo3dRender, pollClo3dTask } from '@/lib/clo3d';

// ---------------------------------------------------------------------------
// Piece region — normalized (%) overlay coordinates on the pattern image
// ---------------------------------------------------------------------------
interface PieceRegionData {
  name: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface PieceSelectorProps {
  project: Clo3dProject;
  materials: Material[];
  onRenderComplete: (task: Clo3dRenderTaskStatus) => void;
}

// ---------------------------------------------------------------------------
// Default grid layout generator (used when pieces lack absolute coordinates)
// ---------------------------------------------------------------------------
const GRID_COLS = 2;
const GRID_GAP_PCT = 2;

function generateGridRegions(
  pieces: { name: string; label: string | null }[],
): PieceRegionData[] {
  if (pieces.length === 0) return [];

  const cols = Math.min(GRID_COLS, pieces.length);
  const rows = Math.ceil(pieces.length / cols);
  const cellW = (100 - GRID_GAP_PCT * (cols + 1)) / cols;
  const cellH = (100 - GRID_GAP_PCT * (rows + 1)) / rows;

  return pieces.map((piece, idx) => {
    const col = idx % cols;
    const row = Math.floor(idx / cols);
    return {
      name: piece.name,
      label: piece.label ?? piece.name,
      x: GRID_GAP_PCT + col * (cellW + GRID_GAP_PCT),
      y: GRID_GAP_PCT + row * (cellH + GRID_GAP_PCT),
      width: cellW,
      height: cellH,
    };
  });
}

// ---------------------------------------------------------------------------
// SVG spinner reused across states
// ---------------------------------------------------------------------------
function Spinner({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Material grid panel (reuses MaterialSelector's visual pattern)
// ---------------------------------------------------------------------------
function MaterialGridPanel({
  materials,
  selectedMaterial,
  onSelectMaterial,
  onClose,
}: {
  materials: Material[];
  selectedMaterial: Material | null;
  onSelectMaterial: (material: Material) => void;
  onClose: () => void;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      {/* backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* side panel */}
      <div
        className={`relative w-full max-w-sm bg-white dark:bg-zinc-900 shadow-2xl flex flex-col transition-transform duration-200 ease-out ${
          visible ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200 dark:border-zinc-800">
          <h3 className="text-base font-semibold text-zinc-950 dark:text-zinc-50">
            选择材质
          </h3>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {materials.length === 0 ? (
            <div className="text-center py-12 text-zinc-500 dark:text-zinc-400 text-sm">
              暂无可用素材
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              {materials.map((material) => {
                const isSelected = selectedMaterial?.id === material.id;
                return (
                  <button
                    key={material.id}
                    onClick={() => onSelectMaterial(material)}
                    className={`
                      relative rounded-lg border-2 overflow-hidden text-left transition-all
                      ${
                        isSelected
                          ? 'border-zinc-950 dark:border-zinc-50 ring-2 ring-zinc-950/20 dark:ring-zinc-50/20'
                          : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600'
                      }
                    `}
                  >
                    <div className="aspect-square bg-zinc-100 dark:bg-zinc-800">
                      {material.thumbnail_url ? (
                        <img
                          src={material.thumbnail_url}
                          alt={material.original_filename}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-zinc-400">
                          <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                      )}
                      {isSelected && (
                        <div className="absolute top-2 right-2 w-6 h-6 bg-zinc-950 dark:bg-zinc-50 rounded-full flex items-center justify-center">
                          <svg className="w-4 h-4 text-white dark:text-zinc-950" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      )}
                    </div>
                    <div className="p-2">
                      <p className="text-xs font-medium text-zinc-950 dark:text-zinc-50 truncate">
                        {material.original_filename}
                      </p>
                      <p className="text-[10px] text-zinc-500 dark:text-zinc-400">
                        {(material.file_size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PieceSelector — main component
// ---------------------------------------------------------------------------
export default function PieceSelector({
  project,
  materials,
  onRenderComplete,
}: PieceSelectorProps) {
  const pieces = project.pieces ?? [];
  const regions = useMemo(() => generateGridRegions(pieces), [pieces]);

  const [selectedPieceName, setSelectedPieceName] = useState<string | null>(null);
  const [materialAssignments, setMaterialAssignments] = useState<Record<string, Material>>({});
  const [isRendering, setIsRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePieceClick = useCallback((pieceName: string) => {
    setSelectedPieceName((prev) => (prev === pieceName ? null : pieceName));
  }, []);

  const handleSelectMaterial = useCallback(
    (material: Material) => {
      if (!selectedPieceName) return;
      setMaterialAssignments((prev) => ({
        ...prev,
        [selectedPieceName]: material,
      }));
      setSelectedPieceName(null);
    },
    [selectedPieceName],
  );

  const handleStartRender = useCallback(async () => {
    setIsRendering(true);
    setError(null);

    // Build material_assignments map: piece_name → material_id
    const assignments: Record<string, number> = {};
    for (const [pieceName, material] of Object.entries(materialAssignments)) {
      assignments[pieceName] = material.id;
    }

    try {
      const { task_id } = await submitClo3dRender({
        project_id: project.id,
        material_assignments: assignments,
      });
      const result = await pollClo3dTask(task_id);
      onRenderComplete(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : '渲染请求失败');
    } finally {
      setIsRendering(false);
    }
  }, [materialAssignments, project.id, onRenderComplete]);

  const renderCount = Object.keys(materialAssignments).length;
  const totalCount = pieces.length;
  const allAssigned = renderCount > 0 && renderCount >= totalCount;
  const hasPieces = pieces.length > 0;

  const selectedMaterial = selectedPieceName
    ? materialAssignments[selectedPieceName] ?? null
    : null;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">
            {project.name}
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {totalCount} 个衣片
            {renderCount > 0 && (
              <span className="ml-2 text-zinc-500">
                ({renderCount}/{totalCount} 已分配材质)
              </span>
            )}
          </p>
        </div>

        <button
          onClick={handleStartRender}
          disabled={isRendering || !allAssigned}
          className={`
            px-5 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2
            ${
              isRendering || !allAssigned
                ? 'bg-zinc-200 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 cursor-not-allowed'
                : 'bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 hover:opacity-85'
            }
          `}
        >
          {isRendering && <Spinner />}
          {isRendering ? '渲染中...' : '开始渲染'}
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Pattern layout canvas with piece overlays */}
      <div className="relative w-full rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900">
        {project.preview_url ? (
          <div className="relative w-full" style={{ aspectRatio: '3 / 4' }}>
            <Image
              src={project.preview_url}
              alt={`${project.name} 版片布局`}
              fill
              className="object-contain"
              sizes="(max-width: 768px) 100vw, 60vw"
              priority
            />

            {/* Piece overlay regions */}
            {hasPieces && (
              <div className="absolute inset-0">
                {regions.map((region) => {
                  const assignedMat = materialAssignments[region.name];
                  const isActive = selectedPieceName === region.name;

                  return (
                    <button
                      key={region.name}
                      onClick={() => handlePieceClick(region.name)}
                      className="absolute outline-none"
                      style={{
                        left: `${region.x}%`,
                        top: `${region.y}%`,
                        width: `${region.width}%`,
                        height: `${region.height}%`,
                      }}
                    >
                      <div
                        className={`
                          w-full h-full rounded-md border-2 flex flex-col items-center justify-center
                          transition-all duration-150
                          ${
                            isActive
                              ? 'border-zinc-950 dark:border-zinc-50 bg-zinc-950/15 dark:bg-zinc-50/15'
                              : 'border-transparent hover:border-zinc-950/40 dark:hover:border-zinc-50/40 hover:bg-zinc-950/10 dark:hover:bg-zinc-50/10'
                          }
                        `}
                      >
                        {/* Assigned material thumbnail */}
                        {assignedMat?.thumbnail_url && (
                          <div className="absolute inset-0 rounded-md overflow-hidden opacity-40">
                            <img
                              src={assignedMat.thumbnail_url}
                              alt=""
                              className="w-full h-full object-cover"
                            />
                          </div>
                        )}

                        {/* Piece label */}
                        <span
                          className={`
                            relative px-2 py-0.5 rounded text-xs font-medium
                            ${
                              isActive
                                ? 'bg-zinc-950 text-white dark:bg-zinc-50 dark:text-zinc-950'
                                : 'bg-black/50 text-white dark:bg-white/80 dark:text-zinc-950'
                            }
                          `}
                        >
                          {region.label}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center py-24 text-zinc-400 dark:text-zinc-500">
            <div className="text-center">
              <svg className="w-16 h-16 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              </svg>
              <p className="text-sm">暂无版片布局预览</p>
            </div>
          </div>
        )}
      </div>

      {/* Assigned materials summary strip */}
      {renderCount > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
            已分配材质:
          </span>
          {pieces.slice(0, 6).map((piece) => {
            const mat = materialAssignments[piece.name];
            return (
              <div
                key={piece.name}
                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800 text-xs text-zinc-700 dark:text-zinc-300"
              >
                {mat?.thumbnail_url && (
                  <img
                    src={mat.thumbnail_url}
                    alt=""
                    className="w-4 h-4 rounded object-cover"
                  />
                )}
                <span>{piece.label ?? piece.name}</span>
              </div>
            );
          })}
          {pieces.length > 6 && (
            <span className="text-xs text-zinc-400">+{pieces.length - 6}</span>
          )}
        </div>
      )}

      {/* Material selection side panel */}
      {selectedPieceName !== null && (
        <MaterialGridPanel
          materials={materials}
          selectedMaterial={selectedMaterial}
          onSelectMaterial={handleSelectMaterial}
          onClose={() => setSelectedPieceName(null)}
        />
      )}

    </div>
  );
}

// Export supplementary interfaces for consumers
export type { PieceRegionData, PieceSelectorProps };
