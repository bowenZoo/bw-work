<script setup lang="ts">
import { computed } from 'vue';
import type { Message } from '@/types';
import { useAgentsStore } from '@/stores';
import { normalizeAgentRole } from '@/utils/agents';

const props = defineProps<{
  message: Message;
}>();

const agentsStore = useAgentsStore();

const normalizedRole = computed(() => normalizeAgentRole(props.message.agentRole));

// Get agent info based on role
const agent = computed(() => {
  const role = normalizedRole.value ?? props.message.agentRole;
  return role ? agentsStore.getAgentByRole(role) : undefined;
});

const displayName = computed(() => agent.value?.name ?? props.message.agentRole ?? 'Unknown');

// Format timestamp
const formattedTime = computed(() => {
  const date = new Date(props.message.timestamp);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
});

// Get color class based on agent role
const roleColorClass = computed(() => {
  switch (normalizedRole.value) {
    case 'system_designer':
      return 'bg-blue-100 border-blue-300';
    case 'number_designer':
      return 'bg-green-100 border-green-300';
    case 'player_advocate':
      return 'bg-orange-100 border-orange-300';
    default:
      return 'bg-gray-100 border-gray-300';
  }
});

const roleBadgeClass = computed(() => {
  switch (normalizedRole.value) {
    case 'system_designer':
      return 'bg-blue-500';
    case 'number_designer':
      return 'bg-green-500';
    case 'player_advocate':
      return 'bg-orange-500';
    default:
      return 'bg-gray-500';
  }
});
</script>

<template>
  <div class="flex gap-3 p-4">
    <!-- Avatar -->
    <div class="flex-shrink-0">
      <div
        :class="[
          'w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm overflow-hidden',
          roleBadgeClass,
        ]"
      >
        <img
          v-if="agent?.avatarUrl"
          :src="agent.avatarUrl"
          :alt="displayName"
          class="w-full h-full object-cover"
        />
        <span v-else>{{ displayName.charAt(0) ?? '?' }}</span>
      </div>
    </div>

    <!-- Message content -->
    <div class="flex-1 min-w-0">
      <!-- Header -->
      <div class="flex items-center gap-2 mb-1">
        <span class="font-medium text-gray-900">{{ displayName }}</span>
        <span class="text-xs text-gray-500">{{ formattedTime }}</span>
      </div>

      <!-- Message body -->
      <div
        :class="[
          'rounded-lg p-3 border whitespace-pre-wrap break-words',
          roleColorClass,
        ]"
      >
        {{ message.content }}
      </div>
    </div>
  </div>
</template>
