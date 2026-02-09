/**
 * Global discussion composable for single shared discussion.
 *
 * All users share the same discussion. This composable handles:
 * - WebSocket connection to /ws/discussion
 * - Automatic sync of discussion state and messages
 * - Creating and joining discussions
 * - Real-time viewer count updates
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import api from '@/api';
import { useAgentsStore } from '@/stores/agents';
import type {
  Discussion,
  Message,
  DiscussionStatus,
  ConnectionStatus,
  ServerMessage,
  ClientMessage,
  AttachmentInfo,
  AgentStatus,
  Agenda,
  AgendaItem,
  AgendaEvent,
} from '@/types';

// WebSocket configuration
function getWsBaseUrl(): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
}

const RECONNECT_INTERVAL = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 10;
const PING_INTERVAL = 25000; // 25 seconds

// Extended types for global discussion
export interface GlobalDiscussion {
  id: string;
  topic: string;
  rounds: number;
  status: DiscussionStatus;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  result?: string | null;
  error?: string | null;
}

export interface SyncMessage {
  type: 'sync';
  data: {
    discussion: GlobalDiscussion | null;
    messages: Message[];
  };
}

export interface ViewersMessage {
  type: 'viewers';
  data: {
    count: number;
  };
}

export interface AgendaMessage {
  type: 'agenda';
  data: {
    event_type: 'agenda_init' | 'item_start' | 'item_complete' | 'item_skip' | 'item_add';
    item_id?: string;
    title?: string;
    summary?: string;
    current_index?: number;
    agenda?: Agenda;
  };
}

export type GlobalServerMessage = SyncMessage | ViewersMessage | AgendaMessage | ServerMessage;

export interface CreateCurrentDiscussionRequest {
  topic: string;
  rounds?: number;
  auto_pause_interval?: number;
  attachment?: AttachmentInfo | null;
}

export interface CreateCurrentDiscussionResponse {
  id: string;
  topic: string;
  rounds: number;
  status: DiscussionStatus;
  created_at: string;
  message?: string | null;
}

export interface JoinDiscussionResponse {
  discussion: GlobalDiscussion | null;
  messages: Message[];
}

export function useGlobalDiscussion() {
  // Agents store for status updates
  const agentsStore = useAgentsStore();

  // Connection state
  const socket = ref<WebSocket | null>(null);
  const connectionStatus = ref<ConnectionStatus>('disconnected');
  const reconnectAttempts = ref(0);
  const shouldReconnect = ref(false);

  // Discussion state
  const discussion = ref<GlobalDiscussion | null>(null);
  const messages = ref<Message[]>([]);
  const viewerCount = ref(0);

  // Pause/resume state
  const isPaused = ref(false);
  const autoPauseMessage = ref('');

  // Agenda state
  const agenda = ref<Agenda | null>(null);

  // Timers
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;

  // Computed properties
  const isConnected = computed(() => connectionStatus.value === 'connected');
  const isDiscussionActive = computed(() =>
    discussion.value?.status === 'running'
  );
  const hasDiscussion = computed(() => discussion.value !== null);

  // Connect to global WebSocket
  function connect() {
    if (socket.value?.readyState === WebSocket.OPEN) {
      console.log('Global WebSocket already connected');
      return;
    }

    connectionStatus.value = 'connecting';
    shouldReconnect.value = true;

    const wsUrl = `${getWsBaseUrl()}/ws/discussion`;
    console.log(`Connecting to global WebSocket: ${wsUrl}`);

    try {
      socket.value = new WebSocket(wsUrl);

      socket.value.onopen = () => {
        console.log('Global WebSocket connected');
        connectionStatus.value = 'connected';
        reconnectAttempts.value = 0;
        startPingInterval();
      };

      socket.value.onclose = (event) => {
        console.log(`Global WebSocket closed: code=${event.code}, reason=${event.reason}`);
        connectionStatus.value = 'disconnected';
        stopPingInterval();

        if (shouldReconnect.value && reconnectAttempts.value < MAX_RECONNECT_ATTEMPTS) {
          scheduleReconnect();
        } else if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
          connectionStatus.value = 'error';
          console.warn('Max reconnect attempts reached for global WebSocket.');
        }
      };

      socket.value.onerror = (error) => {
        console.error('Global WebSocket error:', error);
        connectionStatus.value = 'error';
      };

      socket.value.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleMessage(message);
        } catch (e) {
          console.error('Failed to parse global WebSocket message:', e);
        }
      };
    } catch (error) {
      console.error('Failed to create global WebSocket:', error);
      connectionStatus.value = 'error';
    }
  }

  // Handle incoming messages
  function handleMessage(message: GlobalServerMessage) {
    switch (message.type) {
      case 'sync':
        // Initial sync or state update
        discussion.value = message.data.discussion;
        if (message.data.messages) {
          messages.value = message.data.messages.map(normalizeMessage);
        }
        // Fallback: if sync returns no discussion, double-check via REST API.
        // This handles edge cases like server restart where WebSocket state
        // may not be populated yet but the API can still return the discussion.
        if (!message.data.discussion) {
          fetchCurrentDiscussionFallback();
        }
        break;

      case 'viewers':
        viewerCount.value = message.data.count;
        break;

      case 'message':
        // New message from an agent
        if (message.data) {
          const newMessage: Message = {
            id: message.data.agent_id + '-' + Date.now(),
            agentId: message.data.agent_id || 'unknown',
            agentRole: message.data.agent_role || 'Unknown',
            content: message.data.content || '',
            timestamp: message.data.timestamp,
            sequence: (message.data as any).sequence,
          };
          messages.value.push(newMessage);
        }
        break;

      case 'status':
        // Discussion-level events (completion, failure, pause, resume)
        if (message.data?.agent_role === 'discussion' || message.data?.agent_id === 'discussion') {
          const content = message.data.content || '';
          if (content === 'discussion_completed') {
            isPaused.value = false;
            if (discussion.value) {
              discussion.value = { ...discussion.value, status: 'completed' as any };
            }
          } else if (content === 'discussion_failed') {
            isPaused.value = false;
            if (discussion.value) {
              discussion.value = { ...discussion.value, status: 'failed' as any };
            }
          } else if (content.startsWith('discussion_auto_paused')) {
            isPaused.value = true;
            // Extract message after colon: "discussion_auto_paused:已完成第5轮讨论，等待继续"
            const colonIdx = content.indexOf(':');
            autoPauseMessage.value = colonIdx >= 0 ? content.substring(colonIdx + 1) : '讨论已自动暂停';
          } else if (content === 'discussion_paused') {
            isPaused.value = true;
            autoPauseMessage.value = '讨论已暂停';
          } else if (content === 'discussion_resumed') {
            isPaused.value = false;
            autoPauseMessage.value = '';
          }
          break;
        }
        // Agent status update - update agents store
        if (message.data?.agent_id && message.data?.status) {
          agentsStore.setAgentStatus(
            message.data.agent_id,
            message.data.status as AgentStatus
          );
        }
        break;

      case 'error':
        console.error('Global discussion error:', message.data?.content);
        break;

      case 'pong':
        // Heartbeat response
        break;

      case 'agenda':
        // Agenda update
        handleAgendaEvent(message as AgendaMessage);
        break;

      default:
        console.debug('Unknown global message type:', (message as any).type);
    }
  }

  // Normalize message format (snake_case to camelCase)
  function normalizeMessage(msg: any): Message {
    return {
      id: msg.id,
      agentId: msg.agent_id || msg.agentId,
      agentRole: msg.agent_role || msg.agentRole,
      content: msg.content,
      timestamp: msg.timestamp,
      sequence: msg.sequence,
    };
  }

  // Fallback: fetch current discussion via REST API when WebSocket sync returns null.
  // Handles edge cases like server restart, race conditions, or stale WebSocket state.
  let fallbackPending = false;
  async function fetchCurrentDiscussionFallback() {
    if (fallbackPending) return;
    fallbackPending = true;
    try {
      const response = await api.post<JoinDiscussionResponse>(
        '/api/discussions/current/join'
      );
      if (response.data?.discussion && !discussion.value) {
        console.log('REST API fallback found discussion:', response.data.discussion.id);
        discussion.value = response.data.discussion as GlobalDiscussion;
        if (response.data.messages) {
          messages.value = response.data.messages.map(normalizeMessage);
        }
      }
    } catch {
      // No discussion available - this is the expected case when truly empty
    } finally {
      fallbackPending = false;
    }
  }

  // Handle agenda events
  function handleAgendaEvent(message: AgendaMessage) {
    const { event_type, item_id, title, summary, current_index, agenda: newAgenda } = message.data;

    switch (event_type) {
      case 'agenda_init':
        // Initialize agenda with full data
        if (newAgenda) {
          agenda.value = newAgenda;
        }
        break;

      case 'item_start':
        // Update current item to in_progress
        if (agenda.value && item_id) {
          updateAgendaItem(item_id, { status: 'in_progress' });
          if (current_index !== undefined) {
            agenda.value.current_index = current_index;
          }
        }
        break;

      case 'item_complete':
        // Update item to completed with summary
        if (agenda.value && item_id) {
          updateAgendaItem(item_id, {
            status: 'completed',
            summary: summary || null,
          });
          if (current_index !== undefined) {
            agenda.value.current_index = current_index;
          }
        }
        break;

      case 'item_skip':
        // Update item to skipped
        if (agenda.value && item_id) {
          updateAgendaItem(item_id, { status: 'skipped' });
          if (current_index !== undefined) {
            agenda.value.current_index = current_index;
          }
        }
        break;

      case 'item_add':
        // Add new item to agenda (deduplicate by id)
        if (agenda.value && item_id && title) {
          const exists = agenda.value.items.some(item => item.id === item_id);
          if (!exists) {
            agenda.value.items.push({
              id: item_id,
              title: title,
              description: null,
              status: 'pending',
              summary: null,
              summary_details: null,
              started_at: null,
              completed_at: null,
            });
          }
        }
        break;
    }
  }

  // Update a specific agenda item
  function updateAgendaItem(itemId: string, updates: Partial<AgendaItem>) {
    if (!agenda.value) return;

    const itemIndex = agenda.value.items.findIndex(item => item.id === itemId);
    if (itemIndex !== -1) {
      agenda.value.items[itemIndex] = {
        ...agenda.value.items[itemIndex],
        ...updates,
      };
    }
  }

  // Fetch agenda from API
  async function fetchAgenda(): Promise<Agenda | null> {
    try {
      const response = await api.get<Agenda>('/api/discussions/current/agenda');
      agenda.value = response.data;
      return response.data;
    } catch (error) {
      console.error('Failed to fetch agenda:', error);
      return null;
    }
  }

  // Add new agenda item via API
  async function addAgendaItem(title: string, description?: string): Promise<AgendaItem | null> {
    try {
      const response = await api.post<{ item: AgendaItem; message: string }>(
        '/api/discussions/current/agenda/items',
        { title, description }
      );
      // Update local state
      if (agenda.value) {
        agenda.value.items.push(response.data.item);
      }
      return response.data.item;
    } catch (error) {
      console.error('Failed to add agenda item:', error);
      return null;
    }
  }

  // Skip agenda item via API
  async function skipAgendaItem(itemId: string): Promise<boolean> {
    try {
      await api.post(`/api/discussions/current/agenda/items/${itemId}/skip`);
      // Update local state
      updateAgendaItem(itemId, { status: 'skipped' });
      return true;
    } catch (error) {
      console.error('Failed to skip agenda item:', error);
      return false;
    }
  }

  // Get agenda item summary via API
  async function getAgendaItemSummary(itemId: string): Promise<{ summary: string | null; details: any } | null> {
    try {
      const response = await api.get(`/api/discussions/current/agenda/items/${itemId}/summary`);
      return {
        summary: response.data.summary,
        details: response.data.summary_details,
      };
    } catch (error) {
      console.error('Failed to get agenda item summary:', error);
      return null;
    }
  }

  // Disconnect
  function disconnect() {
    shouldReconnect.value = false;
    clearReconnectTimer();
    stopPingInterval();

    if (socket.value) {
      socket.value.close();
      socket.value = null;
    }
    connectionStatus.value = 'disconnected';
  }

  // Send message
  function send(message: ClientMessage) {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(message));
    } else {
      console.warn('Cannot send message: Global WebSocket is not connected');
    }
  }

  // Send ping
  function sendPing() {
    send({ type: 'ping' });
  }

  // Schedule reconnection
  function scheduleReconnect() {
    clearReconnectTimer();
    reconnectAttempts.value++;
    console.log(`Scheduling global reconnect attempt ${reconnectAttempts.value}/${MAX_RECONNECT_ATTEMPTS}`);

    reconnectTimer = setTimeout(() => {
      if (shouldReconnect.value) {
        connect();
      }
    }, RECONNECT_INTERVAL);
  }

  // Clear reconnect timer
  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  // Start ping interval
  function startPingInterval() {
    stopPingInterval();
    pingTimer = setInterval(() => {
      sendPing();
    }, PING_INTERVAL);
  }

  // Stop ping interval
  function stopPingInterval() {
    if (pingTimer) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  // API Methods

  /**
   * Create a new global discussion.
   * If a discussion is already running, this will return the existing one.
   */
  async function createDiscussion(
    topic: string,
    rounds: number = 10,
    attachment?: AttachmentInfo | null,
    autoPauseInterval: number = 5,
  ): Promise<CreateCurrentDiscussionResponse> {
    const request: CreateCurrentDiscussionRequest = {
      topic,
      rounds,
      auto_pause_interval: autoPauseInterval,
      attachment: attachment || null,
    };

    const response = await api.post<CreateCurrentDiscussionResponse>(
      '/api/discussions/current',
      request
    );

    // Update local state
    isPaused.value = false;
    autoPauseMessage.value = '';
    discussion.value = {
      id: response.data.id,
      topic: response.data.topic,
      rounds: response.data.rounds,
      status: response.data.status,
      created_at: response.data.created_at,
    };

    // Clear messages for new discussion
    if (!response.data.message) {
      messages.value = [];
    }

    return response.data;
  }

  /**
   * Resume a paused discussion.
   */
  async function resumeDiscussion(): Promise<void> {
    if (!discussion.value?.id) return;
    await api.post(`/api/discussions/${discussion.value.id}/resume`);
    isPaused.value = false;
    autoPauseMessage.value = '';
  }

  /**
   * Join the current discussion and get historical messages.
   */
  async function joinDiscussion(): Promise<JoinDiscussionResponse> {
    const response = await api.post<JoinDiscussionResponse>(
      '/api/discussions/current/join'
    );

    discussion.value = response.data.discussion;
    if (response.data.messages) {
      messages.value = response.data.messages.map(normalizeMessage);
    }

    return response.data;
  }

  /**
   * Get the current discussion state without joining.
   */
  async function getCurrentDiscussion(): Promise<GlobalDiscussion | null> {
    const response = await api.get<GlobalDiscussion | null>(
      '/api/discussions/current'
    );
    discussion.value = response.data;
    return response.data;
  }

  // Auto-connect on mount
  onMounted(() => {
    connect();
  });

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect();
  });

  return {
    // Connection state
    socket,
    connectionStatus,
    isConnected,
    reconnectAttempts,

    // Discussion state
    discussion,
    messages,
    viewerCount,
    isDiscussionActive,
    hasDiscussion,

    // Pause/resume state
    isPaused,
    autoPauseMessage,

    // Agenda state
    agenda,

    // Methods
    connect,
    disconnect,
    send,
    sendPing,
    createDiscussion,
    joinDiscussion,
    getCurrentDiscussion,
    resumeDiscussion,

    // Agenda methods
    fetchAgenda,
    addAgendaItem,
    skipAgendaItem,
    getAgendaItemSummary,
    updateAgendaItem,
  };
}
