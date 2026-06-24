export interface FabricPatch {
  index: number;
  url: string;
  width: number;
  height: number;
}

export interface SegmentResponse {
  task_id: string;
}

export interface SegmentTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result: {
    total_patches: number;
    patches: FabricPatch[];
  } | null;
  error: string | null;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}
