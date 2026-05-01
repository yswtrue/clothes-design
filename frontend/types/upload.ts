export interface UploadResponse {
  id: number;
  uploaded_by: number | null;
  original_filename: string;
  stored_filename: string;
  file_size: number;
  mime_type: string;
  storage_path: string;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export interface StyleAnalysis {
  style_description: string;
  color_palette: string[];
  pattern_type: 'seamless' | 'standalone' | 'full';
  suggested_params: Record<string, unknown>;
}

export interface Material {
  id: number;
  uploaded_by: number | null;
  original_filename: string;
  stored_filename: string;
  file_size: number;
  mime_type: string;
  storage_path: string;
  thumbnail_url: string | null;
  meta: {
    style_analysis?: StyleAnalysis;
  } | null;
  created_at: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export interface UploadError {
  message: string;
  code?: string;
}
