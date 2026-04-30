import { Design, Template, UpdateDesignRequest, PreviewResponse } from '@/types/preview';
import { apiRequest } from './api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchDesign(id: number): Promise<Design> {
  return apiRequest<Design>(`${API_BASE}/api/designs/${id}`);
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export async function fetchTemplates(): Promise<Template[]> {
  const response = await apiRequest<PaginatedResponse<Template>>(
    `${API_BASE}/api/prj-templates?size=100`
  );
  return response.items;
}

export async function updateDesign(
  id: number,
  updates: UpdateDesignRequest
): Promise<Design> {
  return apiRequest<Design>(
    `${API_BASE}/api/designs/${id}`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    }
  );
}

export async function generatePreview(id: number): Promise<PreviewResponse> {
  return apiRequest<PreviewResponse>(`${API_BASE}/api/designs/${id}/preview`);
}
