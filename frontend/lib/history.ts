import type {
  DesignVersion,
  PaginatedDesignsResponse,
  RollbackResponse,
  VersionsListResponse,
} from '@/types/history';

export async function fetchDesigns(
  page: number = 1,
  limit: number = 20
): Promise<PaginatedDesignsResponse> {
  const response = await fetch(`/api/designs?page=${page}&limit=${limit}`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to fetch designs');
  }

  return response.json();
}

export async function fetchVersions(designId: number): Promise<DesignVersion[]> {
  const response = await fetch(`/api/designs/${designId}/versions`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to fetch versions');
  }

  const data: VersionsListResponse = await response.json();
  return data.versions;
}

export async function rollbackVersion(
  designId: number,
  version: number
): Promise<RollbackResponse> {
  const response = await fetch(`/api/designs/${designId}/rollback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ version }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to rollback version');
  }

  return response.json();
}

export async function deleteDesign(designId: number): Promise<void> {
  const response = await fetch(`/api/designs/${designId}`, {
    method: 'DELETE',
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to delete design');
  }
}
