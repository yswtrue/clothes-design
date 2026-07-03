export type ExportContentType = 'line-art' | 'pattern';

export type ExportFormat = 'svg' | 'tif';

export interface ExportResponse {
  task_id: string | null;
  generated_design_id: number;
  format: ExportFormat;
  status: 'pending' | 'exported';
  download_url: string | null;
  upscaled_url: string | null;
}

export interface ExportStatusResponse {
  task_id: string;
  generated_design_id: number | null;
  format: ExportFormat | null;
  status: 'pending' | 'processing' | 'exported' | 'failed';
  progress: number;
  current_step: string | null;
  download_url: string | null;
  upscaled_url: string | null;
  error: string | null;
}
