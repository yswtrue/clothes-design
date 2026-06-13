import { apiRequest } from '@/lib/api';
import type { PrjTemplateDetail } from '@/types/preview';

export interface PrjTemplatePreviewResponse {
  template_id: number;
  generated_design_id: number;
  preview_url: string;
}

export async function fetchPrjTemplateDetail(templateId: number): Promise<PrjTemplateDetail> {
  return apiRequest<PrjTemplateDetail>(`/api/prj-templates/${templateId}`);
}

export async function fetchDxfTemplateFile(dxfUrl: string): Promise<Blob> {
  const response = await fetch(dxfUrl, { credentials: 'omit' });

  if (!response.ok) {
    throw new Error(`下载 DXF 文件失败：HTTP ${response.status}`);
  }

  return response.blob();
}

export async function createPrjTemplatePreview(
  templateId: number,
  generatedDesignId: number
): Promise<PrjTemplatePreviewResponse> {
  return apiRequest<PrjTemplatePreviewResponse>(
    `/api/prj-templates/${templateId}/preview`,
    {
      method: 'POST',
      body: JSON.stringify({ generated_design_id: generatedDesignId }),
    }
  );
}
