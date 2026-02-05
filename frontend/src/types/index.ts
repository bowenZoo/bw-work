// Agent status types
export type AgentStatus = 'thinking' | 'speaking' | 'idle';

export type AgentRole = 'system_designer' | 'number_designer' | 'player_advocate';

// Agent interface
export interface Agent {
  id: string;
  name: string;
  role: AgentRole;
  status: AgentStatus;
}

// Message interface
export interface Message {
  id: string;
  agentId: string;
  agentRole: string;
  content: string;
  timestamp: string;
}

// Discussion status
export type DiscussionStatus = 'pending' | 'running' | 'completed' | 'failed';

// Discussion interface
export interface Discussion {
  id: string;
  topic: string;
  messages: Message[];
  status: DiscussionStatus;
}

// WebSocket message types (matching backend protocol from plan-websocket.md)

// Client -> Server
export interface ClientMessage {
  type: 'ping';
}

// Server -> Client
export type ServerMessageType = 'message' | 'status' | 'error' | 'pong';

export interface ServerMessageData {
  discussion_id: string;
  agent_id?: string;
  agent_role?: string;
  content?: string;
  status?: AgentStatus;
  timestamp: string;
}

export interface ServerMessage {
  type: ServerMessageType;
  data: ServerMessageData;
}

// Connection status
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

// API response types
export interface CreateDiscussionRequest {
  topic: string;
}

export interface CreateDiscussionResponse {
  id: string;
  topic: string;
  status: DiscussionStatus;
}

export interface DiscussionStatusResponse {
  id: string;
  topic: string;
  status: DiscussionStatus;
  rounds: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  result?: string | null;
  error?: string | null;
}

// History API types
export interface DiscussionSummary {
  id: string;
  project_id: string;
  topic: string;
  summary: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface DiscussionListResponse {
  items: DiscussionSummary[];
  hasMore: boolean;
}

// API message response (snake_case from backend)
export interface ApiMessageResponse {
  id: string;
  agent_id: string;
  agent_role: string;
  content: string;
  timestamp: string;
}

export interface DiscussionMessagesResponse {
  discussion: DiscussionSummary;
  messages: ApiMessageResponse[];
}
