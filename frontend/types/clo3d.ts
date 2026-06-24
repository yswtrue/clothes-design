export interface Clo3dPiece {
  name: string;
  label: string | null;
}

export interface Clo3dProject {
  id: number;
  name: string;
  category: string;
  preview_url: string | null;
  pieces: Clo3dPiece[] | null;
  piece_count: number;
  status: string;
  created_at: string | null;
}

export interface Clo3dRenderRequest {
  project_id: number;
  material_assignments: Record<string, number | string>;
  // number = material_id from library
  // string = "data:image/png;base64,..." from screenshot extraction
}

export interface Clo3dRenderSubmitResponse {
  task_id: string;
  render_task_id: number;
  status: string;
}

export interface Clo3dRenderTaskStatus {
  task_id: string;
  render_task_id: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  front_url: string | null;
  back_url: string | null;
  error: string | null;
}
