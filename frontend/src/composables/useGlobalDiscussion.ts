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
        // Add new item to agenda
        if (agenda.value && item_id && title) {
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
    rounds: number = 3,
    attachment?: AttachmentInfo | null
  ): Promise<CreateCurrentDiscussionResponse> {
    const request: CreateCurrentDiscussionRequest = {
      topic,
      rounds,
      attachment: attachment || null,
    };

    const response = await api.post<CreateCurrentDiscussionResponse>(
      '/api/discussions/current',
      request
    );

    // Update local state
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

    // Agenda methods
    fetchAgenda,
    addAgendaItem,
    skipAgendaItem,
    getAgendaItemSummary,
    updateAgendaItem,
  };
}
