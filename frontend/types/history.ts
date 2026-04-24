export interface Design {
  id: number;
  user_id: number | null;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface DesignVersion {
  id: number;
  design_id: number;
  version: number;
  data: {
    pattern_url?: string;
    template_id?: number;
    position?: {
      x: number;
      y: number;
      scale: number;
      rotation: number;
      opacity?: number;
    };
    colors?: {
      hue: number;
      saturation: number;
      brightness: number;
    };
  } | null;
  created_at: string;
}

export interface PaginatedDesignsResponse {
  items: Design[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface VersionsListResponse {
  versions: DesignVersion[];
}

export interface RollbackResponse {
  id: number;
  version: number;
  message: string;
}
