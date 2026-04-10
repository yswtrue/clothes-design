'use client';

import { useDropzone } from 'react-dropzone';
import { validateFile } from '@/lib/upload';
import type { UploadError } from '@/types/upload';

interface DropZoneProps {
  onFileAccepted: (file: File) => void;
  disabled?: boolean;
}

export default function DropZone({ onFileAccepted, disabled = false }: DropZoneProps) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
    },
    maxSize: 50 * 1024 * 1024,
    multiple: false,
    disabled,
    onDrop: (acceptedFiles, rejectedFiles) => {
      if (rejectedFiles.length > 0) {
        const rejection = rejectedFiles[0];
        const error = rejection.errors[0];
        
        let errorMessage = '上传失败';
        if (error.code === 'file-too-large') {
          errorMessage = '文件大小超过 50MB 限制';
        } else if (error.code === 'file-invalid-type') {
          errorMessage = '不支持的文件类型。请上传 JPG、PNG 或 WebP 图片。';
        }
        
        alert(errorMessage);
        return;
      }

      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        const validationError = validateFile(file);
        
        if (validationError) {
          alert(validationError.message);
          return;
        }

        onFileAccepted(file);
      }
    },
  });

  return (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
        transition-colors
        ${isDragActive 
          ? 'border-zinc-950 dark:border-zinc-50 bg-zinc-100 dark:bg-zinc-800' 
          : 'border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-600'
        }
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    >
      <input {...getInputProps()} />
      
      <svg
        className="mx-auto h-12 w-12 text-zinc-400 dark:text-zinc-500 mb-4"
        stroke="currentColor"
        fill="none"
        viewBox="0 0 48 48"
        aria-hidden="true"
      >
        <path
          d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {isDragActive ? (
        <p className="text-lg font-medium text-zinc-950 dark:text-zinc-50">
          放在这里
        </p>
      ) : (
        <div>
          <p className="text-lg font-medium text-zinc-950 dark:text-zinc-50 mb-1">
            拖放图片到这里
          </p>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            或点击选择文件
          </p>
          <p className="text-xs text-zinc-500 dark:text-zinc-500 mt-2">
            支持 JPG、PNG 或 WebP，最大 50MB
          </p>
        </div>
      )}
    </div>
  );
}
