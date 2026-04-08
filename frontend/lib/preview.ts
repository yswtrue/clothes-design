import { Design, Template, UpdateDesignRequest, PreviewResponse } from '@/types/preview';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchDesign(id: number): Promise<Design> {
  const response = await fetch(`${API_BASE}/api/designs/${id}`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch design: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchTemplates(): Promise<Template[]> {
  const response = await fetch(`${API_BASE}/api/templates`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch templates: ${response.statusText}`);
  }

  return response.json();
}

export async function updateDesign(
  id: number,
  updates: UpdateDesignRequest
): Promise<Design> {
  const response = await fetch(`${API_BASE}/api/designs/${id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    throw new Error(`Failed to update design: ${response.statusText}`);
  }

  return response.json();
}

export async function generatePreview(id: number): Promise<PreviewResponse> {
  const response = await fetch(`${API_BASE}/api/designs/${id}/preview`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to generate preview: ${response.statusText}`);
  }

  return response.json();
}
