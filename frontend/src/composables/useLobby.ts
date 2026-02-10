/**
 * Lobby composable for the home page.
 *
 * Connects to /ws/discussion (global WebSocket) in "lobby" mode:
 * - Receives lobby_sync with the list of active discussions
 * - Receives lobby-level events (discussion created/completed/failed)
 * - Provides createDiscussion() that creates + starts a discussion
 */
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { createCurrentDiscussion, getActiveDiscussions } from '@/api/discussion';
import type {
  LobbyDiscussion,
  ConnectionStatus,
  AttachmentInfo,
  AgentConfig,
  CreateCurrentDiscussionResponse,
} from '@/types';

// WebSocket configuration
function getWsBaseUrl(): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
}

const RECONNECT_INTERVAL = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;
const PING_INTERVAL = 25000;

// Lobby WebSocket message types
interface LobbySyncMessage {
  type: 'lobby_sync';
  data: {
    discussions: LobbyDiscussion[];
  };
}

interface LobbyEventMessage {
  type: 'status';
  data: {
    agent_id?: string;
    agent_role?: string;
    content?: string;
    discussion_id?: string;
    topic?: string;
    rounds?: number;
    status?: string;
    agents?: string[];
    timestamp?: string;
  };
}

interface ViewersMessage {
  type: 'viewers';
  data: {
    count: number;
  };
}

type LobbyMessage = LobbySyncMessage | LobbyEventMessage | ViewersMessage | { type: string; data: any };

export function useLobby() {
  // Connection state
  const socket = ref<WebSocket | null>(null);
  const connectionStatus = ref<ConnectionStatus>('disconnected');
  const reconnectAttempts = ref(0);
  const shouldReconnect = ref(false);

  // Lobby state
  const activeDiscussions = ref<LobbyDiscussion[]>([]);
  const viewerCount = ref(0);

  // Timers
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;

  // Computed
  const isConnected = computed(() => connectionStatus.value === 'connected');
  const hasActiveDiscussions = computed(() => activeDiscussions.value.length > 0);

  // Connect to lobby WebSocket
  function connect() {
    if (socket.value?.readyState === WebSocket.OPEN) return;

    connectionStatus.value = 'connecting';
    shouldReconnect.value = true;

    const wsUrl = `${getWsBaseUrl()}/ws/discussion`;

    try {
      socket.value = new WebSocket(wsUrl);

      socket.value.onopen = () => {
        connectionStatus.value = 'connected';
        reconnectAttempts.value = 0;
        startPingInterval();
      };

      socket.value.onclose = (event) => {
        connectionStatus.value = 'disconnected';
        stopPingInterval();

        if (shouldReconnect.value && reconnectAttempts.value < MAX_RECONNECT_ATTEMPTS) {
          scheduleReconnect();
        } else if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
          connectionStatus.value = 'error';
        }
      };

      socket.value.onerror = () => {
        connectionStatus.value = 'error';
      };

      socket.value.onmessage = (event) => {
        try {
          const message: LobbyMessage = JSON.parse(event.data);
          handleMessage(message);
        } catch (e) {
          console.error('Failed to parse lobby WebSocket message:', e);
        }
      };
    } catch {
      connectionStatus.value = 'error';
    }
  }

  // Handle incoming messages
  function handleMessage(message: LobbyMessage) {
    switch (message.type) {
      case 'lobby_sync':
        activeDiscussions.value = (message as LobbySyncMessage).data.discussions;
        break;

      case 'viewers':
        viewerCount.value = (message as ViewersMessage).data.count;
        break;

      case 'status': {
        const data = (message as LobbyEventMessage).data;
        if (data.agent_id === 'discussion' || data.agent_role === 'discussion') {
          const content = data.content || '';
          const discId = data.discussion_id;

          if (content === 'discussion_completed' || content === 'discussion_failed') {
            // Remove from active list
            activeDiscussions.value = activeDiscussions.value.filter(d => d.id !== discId);
          } else if (content === 'discussion_queued' && discId) {
            // Update status to queued
            const existing = activeDiscussions.value.find(d => d.id === discId);
            if (existing) {
              existing.status = 'queued';
            }
          } else if (content === 'discussion_running' && discId) {
            // Update status to running (transitioned from queued)
            const existing = activeDiscussions.value.find(d => d.id === discId);
            if (existing) {
              existing.status = 'running';
            }
          } else if (content === 'discussion_created' && discId) {
            // Add to active list (if not already there)
            if (!activeDiscussions.value.some(d => d.id === discId)) {
              activeDiscussions.value.push({
                id: discId,
                topic: data.topic || '',
                rounds: data.rounds || 0,
                status: 'running',
                created_at: data.timestamp || new Date().toISOString(),
                agents: data.agents || [],
              });
            }
          }
        }
        break;
      }

      case 'sync':
        // Legacy sync message — extract discussion into active list for backward compat
        handleLegacySync(message);
        break;

      case 'pong':
        break;

      default:
        // Ignore other message types in lobby mode
        break;
    }
  }

  // Handle legacy sync message (backward compatibility when backend hasn't been updated yet)
  function handleLegacySync(message: any) {
    const data = message.data;
    if (data?.discussion) {
      const disc = data.discussion;
      if (disc.status === 'running' || disc.status === 'paused') {
        const existing = activeDiscussions.value.find(d => d.id === disc.id);
        if (!existing) {
          activeDiscussions.value = [{
            id: disc.id,
            topic: disc.topic,
            rounds: disc.rounds || 0,
            status: disc.status,
            created_at: disc.created_at || new Date().toISOString(),
            agents: [],
          }];
        }
      }
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

  // Send ping
  function sendPing() {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({ type: 'ping' }));
    }
  }

  // Schedule reconnection
  function scheduleReconnect() {
    clearReconnectTimer();
    reconnectAttempts.value++;
    reconnectTimer = setTimeout(() => {
      if (shouldReconnect.value) connect();
    }, RECONNECT_INTERVAL);
  }

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function startPingInterval() {
    stopPingInterval();
    pingTimer = setInterval(sendPing, PING_INTERVAL);
  }

  function stopPingInterval() {
    if (pingTimer) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  /**
   * Create a new discussion and add it to the active list.
   */
  async function createDiscussion(
    topic: string,
    rounds: number = 10,
    attachment?: AttachmentInfo | null,
    autoPauseInterval: number = 5,
    agents?: string[],
    agentConfigs?: Record<string, Partial<AgentConfig>>,
    discussionStyle?: string,
  ): Promise<CreateCurrentDiscussionResponse> {
    const response = await createCurrentDiscussion({
      topic,
      rounds,
      auto_pause_interval: autoPauseInterval,
      attachment: attachment || null,
      agents,
      agent_configs: agentConfigs,
      discussion_style: discussionStyle,
    });

    // Optimistically add to active list
    if (!activeDiscussions.value.some(d => d.id === response.id)) {
      activeDiscussions.value.push({
        id: response.id,
        topic: response.topic,
        rounds: response.rounds,
        status: response.status,
        created_at: response.created_at,
        agents: agents || [],
      });
    }

    return response;
  }

  /**
   * Fetch active discussions via REST API (fallback / initial load).
   */
  async function fetchActiveDiscussions() {
    try {
      const result = await getActiveDiscussions();
      activeDiscussions.value = result.discussions;
    } catch {
      // Silently fail — WebSocket will provide updates
    }
  }

  // Auto-connect on mount
  onMounted(() => {
    connect();
    fetchActiveDiscussions();
  });

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect();
  });

  return {
    // Connection state
    connectionStatus,
    isConnected,

    // Lobby state
    activeDiscussions,
    viewerCount,
    hasActiveDiscussions,

    // Methods
    connect,
    disconnect,
    createDiscussion,
    fetchActiveDiscussions,
  };
}
