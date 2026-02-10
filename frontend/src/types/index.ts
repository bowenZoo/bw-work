// Agent status types
export type AgentStatus = 'thinking' | 'speaking' | 'idle' | 'writing';

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
  doc_count: number;
  status: string | null;
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
  related_sections: string[];
  priority: number;   // -1=low, 0=normal, 1=high
  source: string;     // "initial" | "discovered" | "intervention"
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
export type AgendaEventType = 'agenda_init' | 'item_start' | 'item_complete' | 'item_skip' | 'item_add' | 'mapping_update';

export interface AgendaEvent {
  type: AgendaEventType;
  data: {
    item_id?: string;
    title?: string;
    summary?: string;
    agenda?: Agenda;
    mappings?: Record<string, string[]>;  // item_id -> section_ids
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

// Round summary types
export interface RoundSummary {
  round: number;
  content: string;
  key_points: string[];
  open_questions: string[];
  generated_at: string;
}

export interface RoundSummariesResponse {
  discussion_id: string;
  summaries: RoundSummary[];
}

// Doc update WebSocket event
export interface DocUpdateEvent {
  discussion_id: string;
  round: number;
  file_count: number;
  files: { filename: string; title: string }[];
  generated_at: string;
}

// Document-centric discussion types
export type SectionStatus = 'pending' | 'in_progress' | 'completed'

export interface SectionPlan {
  id: string
  title: string
  description: string
  status: SectionStatus
  related_agenda_items: string[]
  revision_count: number
  reopened_reason: string | null
}

export interface FilePlan {
  filename: string
  title: string
  sections: SectionPlan[]
}

export interface DocPlan {
  discussion_id: string
  topic: string
  files: FilePlan[]
  current_section_id: string | null
}

// Document-centric WebSocket events
export interface DocPlanWsEvent {
  type: 'doc_plan'
  data: {
    discussion_id: string
    doc_plan: DocPlan
    timestamp: string
  }
}

export interface SectionFocusWsEvent {
  type: 'section_focus'
  data: {
    discussion_id: string
    section_id: string
    section_title: string
    filename: string
    timestamp: string
  }
}

export interface SectionUpdateWsEvent {
  type: 'section_update'
  data: {
    discussion_id: string
    filename: string
    section_id: string
    content: string
    timestamp: string
  }
}

// Agent configuration for customization
export interface AgentConfig {
  role: string
  goal: string
  backstory: string
  focus_areas: string[]
  communication_style?: string
}

// Lobby (active discussions list)
export interface LobbyDiscussion {
  id: string
  topic: string
  rounds: number
  status: DiscussionStatus
  created_at: string
  agents: string[]
}

// Discussion style
export interface DiscussionStyle {
  id: string
  name: string
  description: string
}

// Create discussion request with agent customization
export interface CreateCurrentDiscussionRequest {
  topic: string
  rounds?: number
  auto_pause_interval?: number
  attachment?: AttachmentInfo | null
  agents?: string[]
  agent_configs?: Record<string, Partial<AgentConfig>>
  discussion_style?: string
}

// Create discussion response (from POST /current)
export interface CreateCurrentDiscussionResponse {
  id: string
  topic: string
  rounds: number
  status: DiscussionStatus
  created_at: string
  message?: string | null
}

// Available agents response
export interface AvailableAgentsResponse {
  agents: Record<string, AgentConfig>
}

// Dynamic discussion event data types

export interface DocRestructureEventData {
  discussion_id: string
  operation: string  // "split" | "merge" | "add_section" | "add_file"
  details: Record<string, any>
  updated_doc_plan: DocPlan
  timestamp: string
}

export interface DocRestructureWsEvent {
  type: 'doc_restructure'
  data: DocRestructureEventData
}

export interface SectionReopenedEventData {
  discussion_id: string
  section_id: string
  title: string
  filename: string
  reason: string
  timestamp: string
}

export interface SectionReopenedWsEvent {
  type: 'section_reopened'
  data: SectionReopenedEventData
}

export interface LeadPlannerDigestEventData {
  discussion_id: string
  digest_summary: string
  key_points: string[]
  guidance: string
  timestamp: string
}

export interface LeadPlannerDigestWsEvent {
  type: 'lead_planner_digest'
  data: LeadPlannerDigestEventData
}

export interface InterventionAssessmentEventData {
  discussion_id: string
  impact_level: string  // "ABSORB" | "ADJUST" | "REOPEN"
  affected_sections: string[]
  reason: string
  action_plan: string
  timestamp: string
}

export interface InterventionAssessmentWsEvent {
  type: 'intervention_assessment'
  data: InterventionAssessmentEventData
}

export interface ReviewDimension {
  name: string
  score: string  // "pass" | "warning" | "fail"
  notes: string
}

export interface HolisticReviewEventData {
  discussion_id: string
  review_round: number
  conclusion: string  // "APPROVED" | "NEEDS_REVISION" | "NEEDS_NEW_TOPIC"
  review_dimensions: ReviewDimension[]
  revisions_needed: Array<{ section_id: string; reason: string; [key: string]: any }>
  new_topics: Array<{ title: string; description?: string }>
  timestamp: string
}

export interface HolisticReviewWsEvent {
  type: 'holistic_review'
  data: HolisticReviewEventData
}
