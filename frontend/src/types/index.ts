// Agent status types
export type AgentStatus = 'thinking' | 'speaking' | 'idle';

// Agent interface
export interface Agent {
  id: string;
  name: string;
  role: 'system_designer' | 'number_designer' | 'player_advocate';
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
export type DiscussionStatus = 'idle' | 'in_progress' | 'completed' | 'error';

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

export interface DiscussionResponse {
  id: string;
  topic: string;
  status: DiscussionStatus;
  messages: Message[];
}
