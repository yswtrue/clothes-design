export interface ExportResponse {
  task_id: string;
  design_id: number;
  status: 'pending';
}

export interface ExportStatusResponse {
  task_id: string;
  design_id: number | null;
  status: 'pending' | 'processing' | 'complete' | 'failed';
  progress: number;
  current_step: string | null;
  download_url: string | null;
  error: string | null;
}
