<script setup lang="ts">
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue';
import type { Message, Checkpoint } from '@/types';
import MessageBubble from './MessageBubble.vue';
import DecisionCard from './DecisionCard.vue';
import ProgressNotice from './ProgressNotice.vue';

const props = defineProps<{
  messages: Message[];
  checkpoints?: Checkpoint[];
  isLoading?: boolean;
  maxMessages?: number;
}>();

const emit = defineEmits<{
  'respond-checkpoint': [checkpointId: string, optionId: string | null, freeInput: string]
}>();

const containerRef = ref<HTMLElement | null>(null);

const showAll = ref(false);
const maxMessages = computed(() => props.maxMessages ?? 300);
const isTruncated = computed(() => props.messages.length > maxMessages.value && !showAll.value);

// Smart scroll: track whether user is near bottom
const isNearBottom = ref(true);
const NEAR_BOTTOM_THRESHOLD = 80; // px

function checkNearBottom() {
  if (!containerRef.value) return;
  const { scrollTop, scrollHeight, clientHeight } = containerRef.value;
  isNearBottom.value = scrollHeight - scrollTop - clientHeight < NEAR_BOTTOM_THRESHOLD;
}

function handleScroll() {
  checkNearBottom();
}

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

// Merged timeline: messages + non-silent checkpoints, sorted by time
// Pending decision checkpoints are excluded and shown at bottom
type TimelineItem =
  | { kind: 'message'; data: Message }
  | { kind: 'checkpoint'; data: Checkpoint }

// Decision cards are shown in the right panel (ProducerDecisionStack), not in chat
const pendingDecisions = computed<Checkpoint[]>(() => [])

const timelineItems = computed<TimelineItem[]>(() => {
  const items: TimelineItem[] = []

  for (const msg of renderedMessages.value) {
    items.push({ kind: 'message', data: msg })
  }

  if (props.checkpoints) {
    for (const cp of props.checkpoints) {
      if (cp.type === 'silent') continue
      // Decision cards are handled in the right panel; only show responded ones here as log
      if (cp.type === 'decision' && cp.response === null) continue
      if (cp.type === 'decision' && cp.response !== null) continue  // also hide from chat
      items.push({ kind: 'checkpoint', data: cp })
    }
  }

  items.sort((a, b) => {
    const ta = a.kind === 'message' ? a.data.timestamp : a.data.created_at
    const tb = b.kind === 'message' ? b.data.timestamp : b.data.created_at
    return new Date(ta).getTime() - new Date(tb).getTime()
  })

  return items
})

const hasCheckpoints = computed(() => (props.checkpoints?.length ?? 0) > 0)

function handleRespondCheckpoint(checkpointId: string, optionId: string | null, freeInput: string) {
  emit('respond-checkpoint', checkpointId, optionId, freeInput)
}

// Auto-scroll only when user is near bottom
watch(
  () => props.messages.length + (props.checkpoints?.length ?? 0),
  async () => {
    await nextTick();
    if (!showAll.value && isNearBottom.value) {
      scrollToBottom();
    }
  }
);

function scrollToBottom() {
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight;
    isNearBottom.value = true;
  }
}

const isEmpty = computed(() => timelineItems.value.length === 0 && !props.isLoading);

// Show "scroll to bottom" button when not near bottom and has messages
const showScrollBtn = computed(() => !isNearBottom.value && renderedMessages.value.length > 0);
</script>

<template>
  <div class="chat-outer-wrapper">
    <div
      ref="containerRef"
      class="flex-1 overflow-y-auto bg-white chat-container-wrapper"
      @scroll="handleScroll"
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

      <!-- Messages + Checkpoints timeline -->
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
        <template v-for="item in timelineItems" :key="item.kind === 'message' ? item.data.id : item.data.id">
          <MessageBubble
            v-if="item.kind === 'message'"
            :message="item.data"
          />
          <div v-else-if="item.kind === 'checkpoint' && item.data.type === 'decision'" class="checkpoint-item" :data-checkpoint-id="item.data.id">
            <DecisionCard
              :checkpoint="item.data"
              :discussion-id="item.data.discussion_id"
              @respond="handleRespondCheckpoint"
            />
          </div>
          <div v-else-if="item.kind === 'checkpoint' && item.data.type === 'progress'" class="checkpoint-item">
            <ProgressNotice :checkpoint="item.data" />
          </div>
        </template>
      </div>

      <!-- Loading indicator at bottom -->
      <div v-if="isLoading && messages.length > 0" class="p-4 text-center">
        <div class="inline-flex items-center gap-2 text-gray-500">
          <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
          <span>智能体思考中...</span>
        </div>
      </div>

      <!-- Scroll to bottom button -->
      <button
        v-if="showScrollBtn"
        class="scroll-bottom-btn"
        @click="scrollToBottom"
        title="滚动到底部"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
    </div>

    <!-- Pending decisions pinned to the bottom -->
    <div v-if="pendingDecisions.length > 0" class="pending-decisions-bar">
      <DecisionCard
        v-for="cp in pendingDecisions"
        :key="cp.id"
        :checkpoint="cp"
        :discussion-id="cp.discussion_id"
        @respond="handleRespondCheckpoint"
      />
    </div>
  </div>
</template>

<style scoped>
.chat-outer-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.chat-container-wrapper {
  position: relative;
  flex: 1;
  min-height: 0;
}

.scroll-bottom-btn {
  position: sticky;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--bg-secondary, #f3f4f6);
  border: 1px solid var(--border-color, #e5e7eb);
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.2s;
  z-index: 5;
}

.scroll-bottom-btn:hover {
  background: var(--bg-tertiary, #e5e7eb);
  color: var(--text-primary, #111827);
}

.checkpoint-item {
  padding: 8px 16px;
  margin: 4px 0;
}

/* Pending decisions bar pinned to the bottom */
.pending-decisions-bar {
  flex-shrink: 0;
  border-top: 2px solid #f59e0b;
  background: #fffbeb;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
