<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue';
import type { Message } from '@/types';
import MessageBubble from './MessageBubble.vue';

const props = defineProps<{
  messages: Message[];
  isLoading?: boolean;
  maxMessages?: number;
}>();

const containerRef = ref<HTMLElement | null>(null);

const showAll = ref(false);
const maxMessages = computed(() => props.maxMessages ?? 300);
const isTruncated = computed(() => props.messages.length > maxMessages.value && !showAll.value);

// Sort messages by sequence (if available) or timestamp
const sortedMessages = computed(() => {
  const messagesCopy = [...props.messages];
  return messagesCopy.sort((a, b) => {
    // If both have sequence numbers, use them for ordering
    if (a.sequence !== undefined && b.sequence !== undefined) {
      return a.sequence - b.sequence;
    }
    // Otherwise, fall back to timestamp comparison
    return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
  });
});

const renderedMessages = computed(() => {
  if (!isTruncated.value) return sortedMessages.value;
  return sortedMessages.value.slice(-maxMessages.value);
});
const hiddenCount = computed(() =>
  isTruncated.value ? props.messages.length - renderedMessages.value.length : 0
);

// Auto-scroll to bottom when new messages arrive
watch(
  () => props.messages.length,
  async () => {
    await nextTick();
    if (!showAll.value) {
      scrollToBottom();
    }
  }
);

function scrollToBottom() {
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight;
  }
}

const isEmpty = computed(() => renderedMessages.value.length === 0 && !props.isLoading);
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
        <p class="text-gray-500">加载讨论中...</p>
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
        <p class="text-lg font-medium">暂无消息</p>
        <p class="text-sm">开始讨论以查看对话内容</p>
      </div>
    </div>

    <!-- Messages list -->
    <div v-else class="divide-y divide-gray-100">
      <div
        v-if="hiddenCount > 0"
        class="p-3 text-center text-xs text-gray-500 bg-gray-50 border-b border-gray-100"
      >
        为提升性能，已隐藏 {{ hiddenCount }} 条早期消息。
        <button
          class="ml-2 text-blue-600 hover:text-blue-700 underline"
          @click="showAll = true"
        >
          显示全部
        </button>
      </div>
      <MessageBubble
        v-for="message in renderedMessages"
        :key="message.id"
        :message="message"
      />
    </div>

    <!-- Loading indicator at bottom -->
    <div v-if="isLoading && messages.length > 0" class="p-4 text-center">
      <div class="inline-flex items-center gap-2 text-gray-500">
        <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
        <span>智能体思考中...</span>
      </div>
    </div>
  </div>
</template>
