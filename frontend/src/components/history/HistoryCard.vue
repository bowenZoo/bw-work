<script setup lang="ts">
import { computed } from 'vue';
import type { DiscussionSummary } from '@/types';

const props = defineProps<{
  discussion: DiscussionSummary;
}>();

// Format date
const formattedDate = computed(() => {
  const date = new Date(props.discussion.created_at);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } else if (diffDays === 1) {
    return 'Yesterday';
  } else if (diffDays < 7) {
    return `${diffDays} days ago`;
  } else {
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
    });
  }
});

// Truncated summary
const truncatedSummary = computed(() => {
  const summary = props.discussion.summary;
  if (!summary) return null;
  if (summary.length <= 100) return summary;
  return summary.slice(0, 100) + '...';
});

// Agent avatars - mock data for now (in real app, would get from discussion metadata)
const agentRoles = ['system_designer', 'number_designer', 'player_advocate'];

// Get avatar color
function getAvatarColor(role: string): string {
  switch (role) {
    case 'system_designer':
      return 'bg-blue-500';
    case 'number_designer':
      return 'bg-green-500';
    case 'player_advocate':
      return 'bg-orange-500';
    default:
      return 'bg-gray-500';
  }
}

// Get avatar initial
function getAvatarInitial(role: string): string {
  switch (role) {
    case 'system_designer':
      return 'S';
    case 'number_designer':
      return 'N';
    case 'player_advocate':
      return 'P';
    default:
      return '?';
  }
}
</script>

<template>
  <div
    class="p-4 hover:bg-gray-50 cursor-pointer transition-colors duration-150"
  >
    <!-- Header row -->
    <div class="flex items-start justify-between gap-4">
      <h3 class="font-medium text-gray-900 line-clamp-2 flex-1">
        {{ discussion.topic }}
      </h3>
      <span class="text-xs text-gray-400 flex-shrink-0">
        {{ formattedDate }}
      </span>
    </div>

    <!-- Summary -->
    <p
      v-if="truncatedSummary"
      class="mt-2 text-sm text-gray-600 line-clamp-2"
    >
      {{ truncatedSummary }}
    </p>

    <!-- Footer row -->
    <div class="mt-3 flex items-center justify-between">
      <!-- Agent avatars -->
      <div class="flex -space-x-2">
        <div
          v-for="role in agentRoles"
          :key="role"
          :class="[
            'w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-medium ring-2 ring-white',
            getAvatarColor(role),
          ]"
          :title="role"
        >
          {{ getAvatarInitial(role) }}
        </div>
      </div>

      <!-- Message count -->
      <div class="flex items-center gap-1 text-sm text-gray-500">
        <svg
          class="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
        <span>{{ discussion.message_count }}</span>
      </div>
    </div>
  </div>
</template>
