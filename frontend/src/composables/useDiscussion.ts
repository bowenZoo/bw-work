import { ref, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useDiscussionStore, useAgentsStore } from '@/stores';
import { useWebSocket } from './useWebSocket';
import * as discussionApi from '@/api/discussion';
import { getInterventionStatus } from '@/api/intervention';
import type { Discussion, Message, ServerMessage } from '@/types';
import { normalizeAgentRole } from '@/utils/agents';

export function useDiscussion() {
  const router = useRouter();
  const discussionStore = useDiscussionStore();
  const agentsStore = useAgentsStore();

  // Internal state
  const isCreating = ref(false);
  const isStarting = ref(false);
  const isPaused = ref(false);

  // Current discussion ID
  const discussionId = computed(() => discussionStore.discussionId);

  // WebSocket connection
  const {
    connectionStatus,
    lastMessage,
    connect,
    disconnect,
  } = useWebSocket(discussionId);

  /**
   * Create a new discussion with the given topic
   */
  async function createDiscussion(topic: string): Promise<string | null> {
    if (isCreating.value) return null;

    isCreating.value = true;
    discussionStore.setLoading(true);
    discussionStore.setError(null);

    try {
      // Read attachment from sessionStorage
      let attachment: { filename: string; content: string } | undefined;
      const storedAttachment = sessionStorage.getItem('discussion_attachment');
      if (storedAttachment) {
        try {
          attachment = JSON.parse(storedAttachment);
          sessionStorage.removeItem('discussion_attachment'); // Clean up
        } catch {
          // Ignore invalid JSON
        }
      }

      const response = await discussionApi.createDiscussion({ topic, attachment });

      const discussion: Discussion = {
        id: response.id,
        topic: response.topic,
        messages: [],
        status: response.status,
      };

      discussionStore.setDiscussion(discussion);

      // Navigate to discussion page
      router.push({
        name: 'discussion',
        params: { id: response.id },
      });

      return response.id;
    } catch (error) {
      console.error('Failed to create discussion:', error);
      discussionStore.setError(
        error instanceof Error ? error.message : 'Failed to create discussion'
      );
      return null;
    } finally {
      isCreating.value = false;
      discussionStore.setLoading(false);
    }
  }

  /**
   * Start the current discussion
   */
  async function startDiscussion(): Promise<boolean> {
    if (!discussionId.value || isStarting.value) return false;

    isStarting.value = true;
    discussionStore.setLoading(true);
    isPaused.value = false;

    try {
      await discussionApi.startDiscussion(discussionId.value);
      discussionStore.startDiscussion();

      // Connect WebSocket to receive real-time updates
      connect();

      return true;
    } catch (error) {
      console.error('Failed to start discussion:', error);
      discussionStore.setError(
        error instanceof Error ? error.message : 'Failed to start discussion'
      );
      return false;
    } finally {
      isStarting.value = false;
      discussionStore.setLoading(false);
    }
  }

  /**
   * Load an existing discussion by ID
   */
  async function loadDiscussion(id: string): Promise<boolean> {
    discussionStore.setLoading(true);
    discussionStore.setError(null);

    try {
      const [statusResponse, messagesResponse, interventionStatus] = await Promise.all([
        discussionApi.getDiscussionStatus(id),
        discussionApi.getDiscussionMessages(id).catch(() => null),
        getInterventionStatus(id).catch(() => null),
      ]);

      const messages: Message[] = (messagesResponse?.messages ?? []).map((msg) => {
        const normalizedRole =
          normalizeAgentRole(msg.agent_id) ?? normalizeAgentRole(msg.agent_role);
        return {
          id: msg.id,
          agentId: normalizedRole ?? msg.agent_id,
          agentRole: normalizedRole ?? msg.agent_role,
          content: msg.content,
          timestamp: msg.timestamp,
        };
      });

      const topic = messagesResponse?.discussion.topic ?? statusResponse.topic;

      const discussion: Discussion = {
        id: statusResponse.id,
        topic,
        messages,
        status: statusResponse.status,
      };

      discussionStore.setDiscussion(discussion);
      isPaused.value = Boolean(interventionStatus?.is_paused);

      // Connect WebSocket if discussion is in progress
      if (discussion.status === 'running') {
        connect();
      }

      return true;
    } catch (error) {
      console.error('Failed to load discussion:', error);
      discussionStore.setError(
        error instanceof Error ? error.message : 'Failed to load discussion'
      );
      return false;
    } finally {
      discussionStore.setLoading(false);
    }
  }

  /**
   * Handle incoming WebSocket message
   */
  function handleMessage(message: ServerMessage) {
    switch (message.type) {
      case 'message':
        if (message.data.agent_id && message.data.content) {
          const normalizedRole =
            normalizeAgentRole(message.data.agent_id) ??
            normalizeAgentRole(message.data.agent_role);
          const agentRole = normalizedRole ?? message.data.agent_role ?? message.data.agent_id;
          const newMessage: Message = {
            id: `${message.data.discussion_id}-${Date.now()}`,
            agentId: agentRole,
            agentRole,
            content: message.data.content,
            timestamp: message.data.timestamp,
          };
          discussionStore.addMessage(newMessage);
        }
        break;

      case 'status':
        if (message.data.agent_role === 'discussion' || message.data.agent_id === 'discussion') {
          if (message.data.content === 'discussion_completed') {
            discussionStore.endDiscussion();
            isPaused.value = false;
          }
          if (message.data.content === 'discussion_failed') {
            discussionStore.setStatus('failed');
            isPaused.value = false;
          }
          if (message.data.content === 'discussion_paused') {
            isPaused.value = true;
          }
          if (message.data.content === 'discussion_resumed') {
            isPaused.value = false;
          }
          break;
        }

        if (message.data.agent_role && message.data.status) {
          const normalizedRole =
            normalizeAgentRole(message.data.agent_role) ??
            normalizeAgentRole(message.data.agent_id);
          if (normalizedRole) {
            agentsStore.setAgentStatusByRole(normalizedRole, message.data.status);
          }
        }
        break;

      case 'error':
        discussionStore.setError(message.data.content ?? 'Unknown error');
        discussionStore.setStatus('failed');
        isPaused.value = false;
        break;
    }
  }

  /**
   * End the current discussion
   */
  function endDiscussion() {
    disconnect();
    agentsStore.resetAllAgentsStatus();
    discussionStore.endDiscussion();
  }

  /**
   * Clear and reset everything
   */
  function reset() {
    disconnect();
    agentsStore.resetAllAgentsStatus();
    discussionStore.clearDiscussion();
    isPaused.value = false;
  }

  function setPaused(value: boolean) {
    isPaused.value = value;
  }

  watch(lastMessage, (message) => {
    if (message) {
      handleMessage(message);
    }
  });

  return {
    // State
    discussionId,
    connectionStatus,
    lastMessage,
    isCreating,
    isStarting,
    // Discussion store proxies
    discussion: computed(() => discussionStore.currentDiscussion),
    messages: computed(() => discussionStore.messages),
    topic: computed(() => discussionStore.topic),
    status: computed(() => discussionStore.status),
    isLoading: computed(() => discussionStore.isLoading),
    error: computed(() => discussionStore.error),
    isInProgress: computed(() => discussionStore.isInProgress),
    isCompleted: computed(() => discussionStore.isCompleted),
    isPaused: computed(() => isPaused.value),
    setError: discussionStore.setError,
    // Actions
    createDiscussion,
    startDiscussion,
    loadDiscussion,
    handleMessage,
    endDiscussion,
    reset,
    setPaused,
    connect,
    disconnect,
  };
}
