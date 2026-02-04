import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useDiscussionStore, useAgentsStore } from '@/stores';
import { useWebSocket } from './useWebSocket';
import * as discussionApi from '@/api/discussion';
import type { Discussion, Message, ServerMessage } from '@/types';

export function useDiscussion() {
  const router = useRouter();
  const discussionStore = useDiscussionStore();
  const agentsStore = useAgentsStore();

  // Internal state
  const isCreating = ref(false);
  const isStarting = ref(false);

  // Current discussion ID
  const discussionId = computed(() => discussionStore.discussionId);

  // WebSocket connection
  const {
    connectionStatus,
    lastMessage,
    connect,
    disconnect,
  } = useWebSocket(discussionId.value);

  /**
   * Create a new discussion with the given topic
   */
  async function createDiscussion(topic: string): Promise<string | null> {
    if (isCreating.value) return null;

    isCreating.value = true;
    discussionStore.setLoading(true);
    discussionStore.setError(null);

    try {
      const response = await discussionApi.createDiscussion({ topic });

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
      const response = await discussionApi.getDiscussion(id);

      const discussion: Discussion = {
        id: response.id,
        topic: response.topic,
        messages: response.messages,
        status: response.status,
      };

      discussionStore.setDiscussion(discussion);

      // Connect WebSocket if discussion is in progress
      if (discussion.status === 'in_progress') {
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
          const newMessage: Message = {
            id: `${message.data.discussion_id}-${Date.now()}`,
            agentId: message.data.agent_id,
            agentRole: message.data.agent_role ?? '',
            content: message.data.content,
            timestamp: message.data.timestamp,
          };
          discussionStore.addMessage(newMessage);

          // Update agent status
          if (message.data.agent_role) {
            agentsStore.setAgentStatusByRole(message.data.agent_role, 'idle');
          }
        }
        break;

      case 'status':
        if (message.data.agent_role && message.data.status) {
          agentsStore.setAgentStatusByRole(message.data.agent_role, message.data.status);
        }
        break;

      case 'error':
        discussionStore.setError(message.data.content ?? 'Unknown error');
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
  }

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
    // Actions
    createDiscussion,
    startDiscussion,
    loadDiscussion,
    handleMessage,
    endDiscussion,
    reset,
    connect,
    disconnect,
  };
}
