const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

export interface CostResponse {
  discussion_id: string;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  model_breakdown: Record<string, number>;
  source: string;
  error?: string;
}

export interface MonitoringHealth {
  status: string;
  langfuse: string;
}

/**
 * Get token usage statistics for a discussion
 */
export async function getDiscussionCost(discussionId: string): Promise<CostResponse> {
  const response = await fetch(`${API_BASE_URL}/api/monitoring/cost/${discussionId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to get cost data: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Check monitoring system health
 */
export async function getMonitoringHealth(): Promise<MonitoringHealth> {
  const response = await fetch(`${API_BASE_URL}/api/monitoring/health`);

  if (!response.ok) {
    throw new Error(`Failed to get monitoring health: ${response.statusText}`);
  }

  return response.json();
}
