// Agent status types
export type AgentStatus = 'thinking' | 'speaking' | 'idle';

export type AgentRole = 'lead_planner' | 'system_designer' | 'number_designer' | 'player_advocate' | 'visual_concept';

// Agent interface
export interface Agent {
  id: string;
  name: string;
  role: AgentRole;
  status: AgentStatus;
  avatarUrl?: string;
}

// Message interface
export interface Message {
  id: string;
  agentId: string;
  agentRole: string;
  content: string;
  timestamp: string;
  sequence?: number;  // Optional sequence number for ordering parallel messages
}

// Discussion status
export type DiscussionStatus = 'pending' | 'running' | 'completed' | 'failed';

// Discussion interface
export interface Discussion {
  id: string;
  topic: string;
  messages: Message[];
  status: DiscussionStatus;
  attachment?: AttachmentInfo;
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

// Attachment type
export interface AttachmentInfo {
  filename: string;
  content: string;
}

// API response types
export interface CreateDiscussionRequest {
  topic: string;
  rounds?: number;
  auto_pause_interval?: number;
  attachment?: AttachmentInfo;
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
  attachment?: AttachmentInfo | null;
  continued_from?: string | null;  // 原讨论 ID
  is_continuation?: boolean;  // 是否是续前讨论
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

// Agenda types
export type AgendaItemStatus = 'pending' | 'in_progress' | 'completed' | 'skipped';

export interface AgendaSummaryDetails {
  conclusions: string[];
  viewpoints: Record<string, string>;
  open_questions: string[];
  next_steps: string[];
}

export interface AgendaItem {
  id: string;
  title: string;
  description: string | null;
  status: AgendaItemStatus;
  summary: string | null;
  summary_details: AgendaSummaryDetails | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Agenda {
  items: AgendaItem[];
  current_index: number;
}

// Agenda API types
export interface AddAgendaItemRequest {
  title: string;
  description?: string;
}

export interface AddAgendaItemResponse {
  item: AgendaItem;
  message: string;
}

export interface AgendaItemSummaryResponse {
  item_id: string;
  title: string;
  summary: string | null;
  summary_details: AgendaSummaryDetails | null;
}

// Agenda WebSocket event types
export type AgendaEventType = 'agenda_init' | 'item_start' | 'item_complete' | 'item_skip' | 'item_add';

export interface AgendaEvent {
  type: AgendaEventType;
  data: {
    item_id?: string;
    title?: string;
    summary?: string;
    agenda?: Agenda;
  };
}

// Discussion chain types
export interface DiscussionChainItem {
  id: string;
  topic: string;
  summary: string | null;
  status: DiscussionStatus;
  created_at: string;
  is_origin: boolean;
}

export interface DiscussionChainResponse {
  chain: DiscussionChainItem[];
  current_index: number;
}

// Continue discussion types
export interface ContinueDiscussionRequest {
  follow_up: string;
  rounds?: number;
}

export interface ContinueDiscussionResponse {
  new_discussion_id: string;
  original_discussion_id: string;
  topic: string;
  status: DiscussionStatus;
  message: string;
}

// Design documents types
export interface DesignDocItem {
  filename: string;
  title: string;
  size: number;
  created_at: string;
}

export interface DesignDocsListResponse {
  discussion_id: string;
  topic: string;
  files: DesignDocItem[];
  created_at: string | null;
}

export interface DesignDocContentResponse {
  filename: string;
  title: string;
  content: string;
}

export interface OrganizeResponse {
  discussion_id: string;
  status: string;
  file_count: number;
  files: DesignDocItem[];
  message: string;
}
