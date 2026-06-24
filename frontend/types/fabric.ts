export interface FabricPatch {
  index: number;
  url: string;
  width: number;
  height: number;
}

export interface SegmentResponse {
  total_patches: number;
  patches: FabricPatch[];
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}
