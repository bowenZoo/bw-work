<script setup lang="ts">
import { computed } from 'vue';
import type { DiscussionSummary } from '@/types';
import { useAgentsStore } from '@/stores';
import AgentAvatar from '@/components/agent/AgentAvatar.vue';

const props = defineProps<{
  discussion: DiscussionSummary;
}>();

const emit = defineEmits<{
  click: [];
  continue: [];
}>();

const agentsStore = useAgentsStore();

// Handle card click (navigate to playback)
function handleClick() {
  emit('click');
}

// Handle continue button click
function handleContinue(event: MouseEvent) {
  event.stopPropagation();
  emit('continue');
}

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
    return '昨天';
  } else if (diffDays < 7) {
    return `${diffDays} 天前`;
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

const agentList = computed(() => agentsStore.agents);
</script>

<template>
  <div
    class="p-4 hover:bg-gray-50 cursor-pointer transition-colors duration-150"
    @click="handleClick"
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
        <AgentAvatar
          v-for="agent in agentList"
          :key="agent.id"
          :agent="agent"
          size="sm"
        />
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-3">
        <!-- Continue button -->
        <button
          class="continue-btn"
          title="继续讨论"
          @click="handleContinue"
        >
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
              d="M17 8l4 4m0 0l-4 4m4-4H3"
            />
          </svg>
          <span class="ml-1">继续</span>
        </button>

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
  </div>
</template>

<style scoped>
.continue-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 500;
  color: #10b981;
  background-color: #ecfdf5;
  border: 1px solid #d1fae5;
  border-radius: 6px;
  transition: all 0.2s;
}

.continue-btn:hover {
  background-color: #d1fae5;
  color: #059669;
}
</style>
