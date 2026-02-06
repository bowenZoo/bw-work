/**
 * Design documents API - organized discussion outputs.
 */
import api from './index';
import type { DesignDocsListResponse, DesignDocContentResponse, OrganizeResponse } from '@/types';

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
