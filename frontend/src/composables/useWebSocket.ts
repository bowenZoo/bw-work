import { ref, onUnmounted, watch } from 'vue';
import type { ConnectionStatus, ServerMessage, ClientMessage } from '@/types';

const WS_BASE_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:18000';
const RECONNECT_INTERVAL = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 5;
const PING_INTERVAL = 25000; // 25 seconds

export function useWebSocket(discussionId: string | null) {
  // State
  const socket = ref<WebSocket | null>(null);
  const connectionStatus = ref<ConnectionStatus>('disconnected');
  const lastMessage = ref<ServerMessage | null>(null);
  const reconnectAttempts = ref(0);
  const shouldReconnect = ref(false);

  // Private state
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;

  // Connect to WebSocket
  function connect() {
    if (!discussionId) {
      console.warn('Cannot connect: discussionId is null');
      return;
    }

    if (socket.value?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    connectionStatus.value = 'connecting';
    shouldReconnect.value = true;

    const wsUrl = `${WS_BASE_URL}/ws/${discussionId}`;
    console.log(`Connecting to WebSocket: ${wsUrl}`);

    try {
      socket.value = new WebSocket(wsUrl);

      socket.value.onopen = () => {
        console.log('WebSocket connected');
        connectionStatus.value = 'connected';
        reconnectAttempts.value = 0;
        startPingInterval();
      };

      socket.value.onclose = (event) => {
        console.log(`WebSocket closed: code=${event.code}, reason=${event.reason}`);
        connectionStatus.value = 'disconnected';
        stopPingInterval();

        if (shouldReconnect.value && reconnectAttempts.value < MAX_RECONNECT_ATTEMPTS) {
          scheduleReconnect();
        } else if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
          connectionStatus.value = 'error';
          console.warn('Max reconnect attempts reached. Please refresh the page.');
        }
      };

      socket.value.onerror = (error) => {
        console.error('WebSocket error:', error);
        connectionStatus.value = 'error';
      };

      socket.value.onmessage = (event) => {
        try {
          const message: ServerMessage = JSON.parse(event.data);
          lastMessage.value = message;
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      connectionStatus.value = 'error';
    }
  }

  // Disconnect from WebSocket
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
      console.warn('Cannot send message: WebSocket is not connected');
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
    console.log(`Scheduling reconnect attempt ${reconnectAttempts.value}/${MAX_RECONNECT_ATTEMPTS}`);

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

  // Watch for discussionId changes
  watch(() => discussionId, (newId, oldId) => {
    if (oldId !== newId) {
      disconnect();
      if (newId) {
        connect();
      }
    }
  }, { immediate: false });

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect();
  });

  return {
    socket,
    connectionStatus,
    lastMessage,
    reconnectAttempts,
    connect,
    disconnect,
    send,
    sendPing,
  };
}
