import type {
  CreateDiscussionRequest,
  CreateDiscussionResponse,
  DiscussionStatusResponse,
  DiscussionListResponse,
  DiscussionMessagesResponse,
} from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:18000';

/**
 * Create a new discussion
 */
export async function createDiscussion(
  request: CreateDiscussionRequest
): Promise<CreateDiscussionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to create discussion: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get discussion status by ID
 */
export async function getDiscussionStatus(id: string): Promise<DiscussionStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/${id}`);

  if (!response.ok) {
    throw new Error(`Failed to get discussion: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Start a discussion
 */
export async function startDiscussion(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/${id}/start`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to start discussion: ${response.statusText}`);
  }
}

/**
 * Get discussion history list
 */
export async function getDiscussionHistory(
  page: number = 1,
  limit: number = 20
): Promise<DiscussionListResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/discussions?page=${page}&limit=${limit}`
  );

  if (!response.ok) {
    throw new Error(`Failed to get discussion history: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get discussion messages for playback
 */
export async function getDiscussionMessages(
  id: string
): Promise<DiscussionMessagesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/${id}/messages`);

  if (!response.ok) {
    throw new Error(`Failed to get discussion messages: ${response.statusText}`);
  }

  return response.json();
}
