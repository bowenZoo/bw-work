<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue';
import type { Message } from '@/types';
import MessageBubble from './MessageBubble.vue';

const props = defineProps<{
  messages: Message[];
  isLoading?: boolean;
}>();

const containerRef = ref<HTMLElement | null>(null);

// Auto-scroll to bottom when new messages arrive
watch(
  () => props.messages.length,
  async () => {
    await nextTick();
    scrollToBottom();
  }
);

function scrollToBottom() {
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight;
  }
}

const isEmpty = computed(() => props.messages.length === 0 && !props.isLoading);
</script>

<template>
  <div
    ref="containerRef"
    class="flex-1 overflow-y-auto bg-white"
  >
    <!-- Loading state -->
    <div v-if="isLoading && messages.length === 0" class="flex items-center justify-center h-full">
      <div class="text-center">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p class="text-gray-500">Loading discussion...</p>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="isEmpty" class="flex items-center justify-center h-full">
      <div class="text-center text-gray-500">
        <svg
          class="w-16 h-16 mx-auto mb-4 text-gray-300"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
        <p class="text-lg font-medium">No messages yet</p>
        <p class="text-sm">Start a discussion to see the conversation</p>
      </div>
    </div>

    <!-- Messages list -->
    <div v-else class="divide-y divide-gray-100">
      <MessageBubble
        v-for="message in messages"
        :key="message.id"
        :message="message"
      />
    </div>

    <!-- Loading indicator at bottom -->
    <div v-if="isLoading && messages.length > 0" class="p-4 text-center">
      <div class="inline-flex items-center gap-2 text-gray-500">
        <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
        <span>Agents are thinking...</span>
      </div>
    </div>
  </div>
</template>
