export interface PosterGenerateRequest {
  material_ids: number[];
  product_type: string;
  style: string;
  language: string; // 'en' | 'zh', default 'en'
  custom_prompt?: string;
  image_count: number;
  width: number;
  height: number;
}

export interface PosterGenerateResponse {
  task_id: string;
  poster_id: number;
  status: string;
}

export interface PosterTaskStatusResponse {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: {
    status: string;
    image_urls?: string[];
    poster_id?: number;
    error?: string;
  } | null;
  error?: string | null;
}

export interface PosterHistoryItem {
  id: number;
  product_type: string;
  style: string;
  language: string;
  status: string;
  image_count: number;
  width: number;
  height: number;
  custom_prompt: string | null;
  result_images: string[] | null;
  created_at: string | null;
}

export interface PosterHistoryResponse {
  items: PosterHistoryItem[];
  total: number;
  page: number;
  size: number;
}
