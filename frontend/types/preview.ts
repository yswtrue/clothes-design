export interface Position {
  x: number;
  y: number;
  scale: number;
  rotation: number;
  opacity?: number;
}

export interface ColorAdjustment {
  hue: number;
  saturation: number;
  brightness: number;
}

export interface DesignPreviewState {
  pattern_url: string | null;
  template_id: number | null;
  position: Position;
  colors: ColorAdjustment;
}

export interface Design {
  id: number;
  user_id: number | null;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  preview_state: DesignPreviewState | null;
}

export interface Template {
  id: number;
  name: string;
  image_path: string;
  category: string;
  is_builtin: number;
  created_at: string;
}

export interface UpdateDesignRequest {
  template_id?: number;
  position?: Position;
  colors?: ColorAdjustment;
}

export interface PreviewResponse {
  preview_url: string;
}

export type PreviewPageState =
  | 'loading'
  | 'ready'
  | 'updating'
  | 'generating_preview'
  | 'error';
