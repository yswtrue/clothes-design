export interface GenerateRequest {
  material_id: number;
  pattern_type: 'seamless' | 'standalone' | 'full';
  prompt?: string;
  colors?: string[];
  generate_vector?: boolean;
}

export interface GenerateResponse {
  task_id: string;
  design_id: number;
  status: 'pending';
}

export interface TaskStatusResponse {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: {
    pattern_url: string;
    file_name: string;
    file_size: number;
    dimensions?: { width: number; height: number };
    vector_url?: string;
  };
  error?: string;
}
