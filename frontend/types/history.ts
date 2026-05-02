export interface GeneratedDesign {
  id: number;
  material_id: number;
  status: string;
  image_url: string | null;
  thumbnail_url: string | null;
  upscaled_url: string | null;
  vector_url: string | null;
  variant_index: number;
  prompt_used: string | null;
  seed: number | null;
  is_selected: boolean;
  created_at: string | null;
  exported_at: string | null;
}

export interface MaterialWithDesigns {
  id: number;
  original_filename: string | null;
  thumbnail_url: string | null;
  created_at: string | null;
  designs_count: number;
  designs: GeneratedDesign[];
}

export interface PaginatedHistoryResponse {
  items: MaterialWithDesigns[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
