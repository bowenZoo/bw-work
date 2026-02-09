/**
 * Design documents API - organized discussion outputs.
 */
import api from './index';
import type { DesignDocsListResponse, DesignDocContentResponse, OrganizeResponse, DocPlan } from '@/types';

export async function listDesignDocs(discussionId: string): Promise<DesignDocsListResponse> {
  const response = await api.get<DesignDocsListResponse>(
    `/api/discussions/${discussionId}/design-docs`
  );
  return response.data;
}

export async function getDesignDoc(
  discussionId: string,
  filename: string
): Promise<DesignDocContentResponse> {
  const response = await api.get<DesignDocContentResponse>(
    `/api/discussions/${discussionId}/design-docs/${encodeURIComponent(filename)}`
  );
  return response.data;
}

export async function organizeDiscussion(discussionId: string): Promise<OrganizeResponse> {
  const response = await api.post<OrganizeResponse>(
    `/api/discussions/${discussionId}/organize`
  );
  return response.data;
}

export async function getDocPlan(discussionId: string): Promise<DocPlan | null> {
  try {
    const response = await api.get<DocPlan>(`/api/discussions/${discussionId}/doc-plan`);
    return response.data;
  } catch {
    return null;
  }
}

export async function focusSection(discussionId: string, sectionId: string): Promise<void> {
  await api.post(`/api/discussions/${discussionId}/focus-section`, { section_id: sectionId });
}
