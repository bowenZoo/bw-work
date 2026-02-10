import type {
  CreateDiscussionRequest,
  CreateDiscussionResponse,
  CreateCurrentDiscussionRequest,
  CreateCurrentDiscussionResponse,
  DiscussionStatusResponse,
  DiscussionListResponse,
  DiscussionMessagesResponse,
  RoundSummariesResponse,
  LobbyDiscussion,
  AvailableAgentsResponse,
  DiscussionStyle,
} from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

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

/**
 * Get round summaries for a discussion
 */
export async function getRoundSummaries(
  id: string
): Promise<RoundSummariesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/${id}/round-summaries`);

  if (!response.ok) {
    throw new Error(`Failed to get round summaries: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get active discussions (running/paused)
 */
export async function getActiveDiscussions(): Promise<{ discussions: LobbyDiscussion[] }> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/active`);

  if (!response.ok) {
    throw new Error(`Failed to get active discussions: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get available agents and their default configs
 */
export async function getAvailableAgents(): Promise<AvailableAgentsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/available-agents`);

  if (!response.ok) {
    throw new Error(`Failed to get available agents: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get available discussion styles
 */
export async function getDiscussionStyles(): Promise<{
  default: string;
  styles: DiscussionStyle[];
}> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/styles`);
  if (!response.ok) {
    throw new Error(`Failed to get discussion styles: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Create a new discussion via /current endpoint (starts immediately)
 */
export async function createCurrentDiscussion(
  request: CreateCurrentDiscussionRequest
): Promise<CreateCurrentDiscussionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/current`, {
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
