import type {
  DesignVersion,
  PaginatedDesignsResponse,
  RollbackResponse,
  VersionsListResponse,
} from '@/types/history';
import { apiRequest } from './api';

export async function fetchDesigns(
  page: number = 1,
  size: number = 20
): Promise<PaginatedDesignsResponse> {
  return apiRequest<PaginatedDesignsResponse>(
    `/api/designs?page=${page}&size=${size}`
  );
}

export async function fetchVersions(designId: number): Promise<DesignVersion[]> {
  const data = await apiRequest<VersionsListResponse>(
    `/api/designs/${designId}/versions`
  );
  return data.versions;
}

export async function rollbackVersion(
  designId: number,
  version: number
): Promise<RollbackResponse> {
  return apiRequest<RollbackResponse>(
    `/api/designs/${designId}/rollback`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ version }),
    }
  );
}

export async function deleteDesign(designId: number): Promise<void> {
  await apiRequest<void>(
    `/api/designs/${designId}`,
    {
      method: 'DELETE',
    }
  );
}
