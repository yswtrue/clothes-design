'use client';

import { useEffect } from 'react';

interface ImagePreviewModalProps {
  isOpen: boolean;
  imageUrl: string;
  version: number;
  onClose: () => void;
}

export default function ImagePreviewModal({
  isOpen,
  imageUrl,
  version,
  onClose,
}: ImagePreviewModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative flex flex-col items-center max-w-[90vw] max-h-[90vh]">
        <button
          onClick={onClose}
          className="absolute -top-10 right-0 sm:-right-10 p-2 text-zinc-400 hover:text-white transition-colors"
          aria-label="Close preview"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
        
        <div className="bg-transparent rounded-lg overflow-hidden relative">
          <img
            src={imageUrl}
            alt={`Version ${version} preview`}
            className="w-full h-full object-contain max-w-[90vw] max-h-[85vh] rounded-md"
          />
        </div>
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/60 text-white px-4 py-1.5 rounded-full text-sm font-medium backdrop-blur-md">
          Version {version}
        </div>
      </div>
    </div>
  );
}
