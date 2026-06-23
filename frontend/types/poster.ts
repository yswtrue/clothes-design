export interface PosterGenerateRequest {
  material_ids: number[];
  product_type: string;
  style: string;
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
