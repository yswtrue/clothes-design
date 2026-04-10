'use client';

import { useState } from 'react';
import { uploadFile, pollForAnalysis } from '@/lib/upload';
import DropZone from '@/components/upload/DropZone';
import UploadProgress from '@/components/upload/UploadProgress';
import AnalysisResult from '@/components/upload/AnalysisResult';
import type { UploadProgress as UploadProgressType, Material, StyleAnalysis } from '@/types/upload';

type UploadState = 'idle' | 'uploading' | 'analyzing' | 'complete' | 'error';

interface UploadTabProps {
  onUploadSuccess?: () => void;
}

export default function UploadTab({ onUploadSuccess }: UploadTabProps) {
  const [state, setState] = useState<UploadState>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgressType>({ loaded: 0, total: 0, percentage: 0 });
  const [material, setMaterial] = useState<Material | null>(null);
  const [analysis, setAnalysis] = useState<StyleAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileAccepted = async (file: File) => {
    setSelectedFile(file);
    setError(null);
    setState('uploading');

    try {
      const uploadResponse = await uploadFile(file, setUploadProgress);
      
      setState('analyzing');
      
      const materialResult = await pollForAnalysis(uploadResponse.id);
      
      setMaterial(materialResult);
      setAnalysis(materialResult.meta?.style_analysis || null);
      setState('complete');
      
      if (onUploadSuccess) {
        onUploadSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败，请重试。');
      setState('error');
    }
  };

  const handleReset = () => {
    setState('idle');
    setSelectedFile(null);
    setUploadProgress({ loaded: 0, total: 0, percentage: 0 });
    setMaterial(null);
    setAnalysis(null);
    setError(null);
  };

  return (
    <div>
      {state === 'idle' && (
        <DropZone onFileAccepted={handleFileAccepted} />
      )}

      {state === 'uploading' && selectedFile && (
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
          <h2 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50 mb-4">
            上传中...
          </h2>
          <UploadProgress progress={uploadProgress} filename={selectedFile.name} />
        </div>
      )}

      {state === 'analyzing' && (
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
          <div className="flex items-center space-x-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-zinc-950 dark:border-zinc-50 border-t-transparent" />
            <div>
              <h2 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50">
                分析风格中...
              </h2>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                这可能需要最多 60 秒
              </p>
            </div>
          </div>
        </div>
      )}

      {state === 'complete' && analysis && material && (
        <div className="space-y-6">
          <AnalysisResult analysis={analysis} />
          
          <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
            <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">
              文件详情
            </h3>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-zinc-500 dark:text-zinc-500">文件名</dt>
                <dd className="text-zinc-950 dark:text-zinc-50 font-medium mt-1">
                  {material.original_filename}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500 dark:text-zinc-500">文件大小</dt>
                <dd className="text-zinc-950 dark:text-zinc-50 font-medium mt-1">
                  {(material.file_size / 1024 / 1024).toFixed(2)} MB
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500 dark:text-zinc-500">类型</dt>
                <dd className="text-zinc-950 dark:text-zinc-50 font-medium mt-1">
                  {material.mime_type}
                </dd>
              </div>
              <div>
                <dt className="text-zinc-500 dark:text-zinc-500">素材 ID</dt>
                <dd className="text-zinc-950 dark:text-zinc-50 font-medium mt-1">
                  {material.id}
                </dd>
              </div>
            </dl>
          </div>

          <button
            onClick={handleReset}
            className="w-full py-2 px-4 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 rounded-md font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
          >
            上传其他文件
          </button>
        </div>
      )}

      {state === 'error' && error && (
        <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 p-6">
          <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 text-sm">
            {error}
          </div>
          <button
            onClick={handleReset}
            className="w-full py-2 px-4 bg-zinc-950 dark:bg-zinc-50 text-white dark:text-zinc-950 rounded-md font-medium hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors"
          >
            重试
          </button>
        </div>
      )}
    </div>
  );
}
