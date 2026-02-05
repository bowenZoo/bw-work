const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:18000';

export interface PauseResponse {
  id: string;
  status: string;
  message: string;
  paused_at: string;
}

export interface InjectMessageRequest {
  content: string;
}

export interface InjectMessageResponse {
  id: string;
  status: 'success' | 'failed';
  message: string;
  injected_at: string;
}

export interface ResumeResponse {
  id: string;
  status: string;
  message: string;
  resumed_at: string;
}

export interface InterventionStatus {
  discussion_id: string;
  is_paused: boolean;
  crew_state: string | null;
  injected_messages_count: number;
  discussion_status: string;
}

/**
 * Pause a running discussion
 */
export async function pauseDiscussion(discussionId: string): Promise<PauseResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/${discussionId}/pause`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to pause discussion: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Inject a message into a paused discussion
 */
export async function injectMessage(
  discussionId: string,
  content: string
): Promise<InjectMessageResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/${discussionId}/inject`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to inject message: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Resume a paused discussion
 */
export async function resumeDiscussion(discussionId: string): Promise<ResumeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/discussions/${discussionId}/resume`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to resume discussion: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get the intervention status of a discussion
 */
export async function getInterventionStatus(discussionId: string): Promise<InterventionStatus> {
  const response = await fetch(
    `${API_BASE_URL}/api/discussions/${discussionId}/intervention-status`
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to get intervention status: ${response.statusText}`);
  }

  return response.json();
}
