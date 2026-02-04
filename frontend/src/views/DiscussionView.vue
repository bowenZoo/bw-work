<script setup lang="ts">
import { watch, onUnmounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { ChatContainer, InputBox } from '@/components/chat';
import { Header, Sidebar } from '@/components/layout';
import { useDiscussionStore, useAgentsStore } from '@/stores';
import { useWebSocket } from '@/composables/useWebSocket';
import type { ServerMessage, Message } from '@/types';

const route = useRoute();
const discussionStore = useDiscussionStore();
const agentsStore = useAgentsStore();

// Get discussion ID from route
const discussionId = computed(() => route.params.id as string | undefined);

// WebSocket connection
const {
  connectionStatus,
  lastMessage,
  connect,
  disconnect,
} = useWebSocket(discussionId.value ?? null);

// Handle incoming WebSocket messages
watch(lastMessage, (message: ServerMessage | null) => {
  if (!message) return;

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

        // Reset agent status to idle after speaking
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
      console.error('WebSocket error:', message.data.content);
      discussionStore.setError(message.data.content ?? 'Unknown error');
      break;

    case 'pong':
      // Heartbeat response, no action needed
      break;
  }
});

// Connect when discussion ID is available
watch(discussionId, (newId) => {
  if (newId) {
    connect();
  } else {
    disconnect();
  }
}, { immediate: true });

// Handle topic submission
async function handleSubmit(topic: string) {
  discussionStore.setLoading(true);

  try {
    // TODO: Call API to create discussion
    // For now, create a mock discussion
    const mockDiscussion = {
      id: `discussion-${Date.now()}`,
      topic,
      messages: [],
      status: 'in_progress' as const,
    };
    discussionStore.setDiscussion(mockDiscussion);

    // Connect WebSocket for the new discussion
    // Note: In real implementation, this would happen after API returns the discussion ID
    console.log('Discussion created:', mockDiscussion.id);
  } catch (error) {
    console.error('Failed to create discussion:', error);
    discussionStore.setError('Failed to create discussion');
  } finally {
    discussionStore.setLoading(false);
  }
}

// Cleanup on unmount
onUnmounted(() => {
  disconnect();
  agentsStore.resetAllAgentsStatus();
});
</script>

<template>
  <div class="h-screen flex flex-col bg-gray-100">
    <!-- Header -->
    <Header :connection-status="connectionStatus" />

    <!-- Main content -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Chat area -->
      <main class="flex-1 flex flex-col">
        <ChatContainer
          :messages="discussionStore.messages"
          :is-loading="discussionStore.isLoading"
        />
        <InputBox
          :disabled="discussionStore.isInProgress"
          placeholder="Enter a topic for discussion..."
          @submit="handleSubmit"
        />
      </main>

      <!-- Sidebar -->
      <Sidebar :is-open="true" />
    </div>

    <!-- Error toast -->
    <div
      v-if="discussionStore.error"
      class="fixed bottom-4 right-4 bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg"
    >
      {{ discussionStore.error }}
    </div>
  </div>
</template>
