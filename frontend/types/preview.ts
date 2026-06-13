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

export interface Template {
  id: number;
  name: string;
  preview_url: string | null;
  category: string;
  is_builtin: boolean;
}

export interface PrjTemplateDetail extends Template {
  prj_path: string | null;
  regions: unknown;
}
