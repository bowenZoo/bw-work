<script setup lang="ts">
import { computed } from 'vue';
import { useAgentsStore } from '@/stores';
import AgentAvatar from './AgentAvatar.vue';

const agentsStore = useAgentsStore();

// Status text mapping
function getStatusText(status: string): string {
  switch (status) {
    case 'speaking':
      return 'Speaking';
    case 'thinking':
      return 'Thinking...';
    default:
      return 'Idle';
  }
}

// Status color class
function getStatusTextClass(status: string): string {
  switch (status) {
    case 'speaking':
      return 'text-green-600';
    case 'thinking':
      return 'text-yellow-600';
    default:
      return 'text-gray-500';
  }
}

const speakingAgent = computed(() => agentsStore.speakingAgent);
</script>

<template>
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
    <h3 class="text-sm font-semibold text-gray-900 mb-4">Participants</h3>

    <!-- Current speaker indicator -->
    <div v-if="speakingAgent" class="mb-4 p-3 bg-green-50 rounded-lg border border-green-200">
      <p class="text-xs text-green-600 font-medium mb-2">Currently Speaking</p>
      <div class="flex items-center gap-3">
        <AgentAvatar :agent="speakingAgent" size="sm" />
        <span class="font-medium text-gray-900">{{ speakingAgent.name }}</span>
      </div>
    </div>

    <!-- Agent list -->
    <div class="space-y-3">
      <div
        v-for="agent in agentsStore.agents"
        :key="agent.id"
        class="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 transition-colors"
      >
        <AgentAvatar :agent="agent" size="sm" />
        <div class="flex-1 min-w-0">
          <p class="font-medium text-gray-900 text-sm truncate">{{ agent.name }}</p>
          <p :class="['text-xs', getStatusTextClass(agent.status)]">
            {{ getStatusText(agent.status) }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
