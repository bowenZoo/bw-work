import { ref, onMounted, onUnmounted } from 'vue';

export interface GddParsingProgressEvent {
  type: 'gdd_parsing_progress';
  data: {
    project_id: string;
    gdd_id: string;
    status: string;
    message?: string;
  };
}

export interface ProjectDiscussionStartEvent {
  type: 'project_discussion_start';
  data: {
    project_id: string;
    discussion_id: string;
    total_modules: number;
    module_order: string[];
  };
}

export interface ModuleDiscussionStartEvent {
  type: 'module_discussion_start';
  data: {
    project_id: string;
    discussion_id: string;
    module_id: string;
    module_name: string;
    module_index: number;
    total_modules: number;
  };
}

export interface ModuleDiscussionProgressEvent {
  type: 'module_discussion_progress';
  data: {
    project_id: string;
    discussion_id: string;
    module_id: string;
    round: number;
    speaker: string;
    summary: string;
    message?: string;
    message_id?: string;
  };
}

export interface ModuleDiscussionCompleteEvent {
  type: 'module_discussion_complete';
  data: {
    project_id: string;
    discussion_id: string;
    module_id: string;
    design_doc_path: string;
    key_decisions: string[];
  };
}

export interface ProjectDiscussionCompleteEvent {
  type: 'project_discussion_complete';
  data: {
    project_id: string;
    discussion_id: string;
    total_duration_minutes: number;
    design_docs: string[];
    summary_path: string;
  };
}

export interface DiscussionPausedEvent {
  type: 'discussion_paused';
  data: {
    project_id: string;
    discussion_id: string;
    checkpoint_id: string;
    module_id?: string;
    completed_modules: number;
  };
}

export type ProjectWebSocketEvent =
  | GddParsingProgressEvent
  | ProjectDiscussionStartEvent
  | ModuleDiscussionStartEvent
  | ModuleDiscussionProgressEvent
  | ModuleDiscussionCompleteEvent
  | ProjectDiscussionCompleteEvent
  | DiscussionPausedEvent;

export interface UseProjectWebSocketOptions {
  projectId: string;
  onGddParsingProgress?: (event: GddParsingProgressEvent) => void;
  onProjectDiscussionStart?: (event: ProjectDiscussionStartEvent) => void;
  onModuleDiscussionStart?: (event: ModuleDiscussionStartEvent) => void;
  onModuleDiscussionProgress?: (event: ModuleDiscussionProgressEvent) => void;
  onModuleDiscussionComplete?: (event: ModuleDiscussionCompleteEvent) => void;
  onProjectDiscussionComplete?: (event: ProjectDiscussionCompleteEvent) => void;
  onDiscussionPaused?: (event: DiscussionPausedEvent) => void;
  onError?: (error: Error) => void;
}

export function useProjectWebSocket(options: UseProjectWebSocketOptions) {
  const connected = ref(false);
  const error = ref<Error | null>(null);

  let ws: WebSocket | null = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  let reconnectTimer: number | null = null;

  function connect() {
    if (ws?.readyState === WebSocket.OPEN) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/projects/${options.projectId}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      connected.value = true;
      error.value = null;
      reconnectAttempts = 0;
    };

    ws.onclose = () => {
      connected.value = false;
      attemptReconnect();
    };

    ws.onerror = (_e) => {
      error.value = new Error('WebSocket connection error');
      options.onError?.(error.value);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as ProjectWebSocketEvent;
        handleMessage(message);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
  }

  function handleMessage(message: ProjectWebSocketEvent) {
    switch (message.type) {
      case 'gdd_parsing_progress':
        options.onGddParsingProgress?.(message);
        break;
      case 'project_discussion_start':
        options.onProjectDiscussionStart?.(message);
        break;
      case 'module_discussion_start':
        options.onModuleDiscussionStart?.(message);
        break;
      case 'module_discussion_progress':
        options.onModuleDiscussionProgress?.(message);
        break;
      case 'module_discussion_complete':
        options.onModuleDiscussionComplete?.(message);
        break;
      case 'project_discussion_complete':
        options.onProjectDiscussionComplete?.(message);
        break;
      case 'discussion_paused':
        options.onDiscussionPaused?.(message);
        break;
    }
  }

  function attemptReconnect() {
    if (reconnectAttempts >= maxReconnectAttempts) {
      error.value = new Error('Max reconnect attempts reached');
      options.onError?.(error.value);
      return;
    }

    reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);

    reconnectTimer = window.setTimeout(() => {
      connect();
    }, delay);
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    if (ws) {
      ws.close();
      ws = null;
    }

    connected.value = false;
  }

  onMounted(() => {
    connect();
  });

  onUnmounted(() => {
    disconnect();
  });

  return {
    connected,
    error,
    connect,
    disconnect,
  };
}
