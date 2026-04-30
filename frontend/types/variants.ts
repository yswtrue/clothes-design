export interface GeneratedVariant {
  id: number;
  material_id: number;
  image_url: string | null;
  thumbnail_url: string | null;
  variant_index: number;
  is_selected: boolean;
  created_at: string | null;
}

export interface PrjTemplate {
  id: number;
  name: string;
  description: string | null;
  file_path: string;
  thumbnail_url: string | null;
  piece_count: number;
  pieces_metadata: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface GenerateVariantsRequest {
  material_id: number;
  count?: number;
}

export interface GenerateVariantsResponse {
  task_id: string;
  material_id: number;
  status: 'pending';
}

export interface VariantsTaskStatusResponse {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: {
    variants: GeneratedVariant[];
    count: number;
  };
  error?: string;
}

export interface ComposeRequest {
  generated_design_id: number;
  prj_template_id: number;
}

export interface ComposeResponse {
  task_id: string;
  design_id: number;
  status: 'pending';
}

export interface ComposeTaskStatusResponse {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: {
    tif_url: string;
    file_name: string;
    file_size: number;
    piece_count: number;
  };
  error?: string;
}
