import type {
  CreateDiscussionRequest,
  CreateDiscussionResponse,
  DiscussionResponse,
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
 * Get discussion by ID
 */
export async function getDiscussion(id: string): Promise<DiscussionResponse> {
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
