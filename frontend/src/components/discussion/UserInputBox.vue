<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import {
  pauseDiscussion,
  resumeDiscussion,
  injectMessage,
} from '@/api/intervention';

export interface UserInputBoxProps {
  discussionId: string;
  disabled?: boolean;
  placeholder?: string;
}

const props = withDefaults(defineProps<UserInputBoxProps>(), {
  disabled: false,
  placeholder: '发表你的观点...',
});

const emit = defineEmits<{
  (e: 'send', content: string): void;
  (e: 'error', message: string): void;
}>();

const MAX_LENGTH = 200;
const MAX_MESSAGES_PER_MINUTE = 2;

const inputContent = ref('');
const lastSentTimes = ref<number[]>([]);
const throttleMessage = ref<string | null>(null);
const isSending = ref(false);

const charCount = computed(() => inputContent.value.length);
const isOverLimit = computed(() => charCount.value > MAX_LENGTH);

const canSend = computed(() => {
  if (props.disabled) return false;
  if (isSending.value) return false;
  if (inputContent.value.trim().length === 0) return false;
  if (isOverLimit.value) return false;
  return checkThrottle();
});

function checkThrottle(): boolean {
  const now = Date.now();
  // Clean up entries older than 1 minute
  const validTimes = lastSentTimes.value.filter((t) => now - t <= 60000);
  lastSentTimes.value = validTimes;
  return validTimes.length < MAX_MESSAGES_PER_MINUTE;
}

function getThrottleRemainingTime(): number {
  if (lastSentTimes.value.length < MAX_MESSAGES_PER_MINUTE) return 0;
  const oldestTime = lastSentTimes.value[0];
  if (oldestTime === undefined) return 0;
  const now = Date.now();
  const remaining = 60000 - (now - oldestTime);
  return Math.max(0, Math.ceil(remaining / 1000));
}

async function handleSend() {
  if (!canSend.value) {
    const remaining = getThrottleRemainingTime();
    if (remaining > 0) {
      throttleMessage.value = `发言过于频繁，请等待 ${remaining} 秒`;
      setTimeout(() => {
        throttleMessage.value = null;
      }, 3000);
    }
    return;
  }

  const content = inputContent.value.trim();
  if (!content) return;

  isSending.value = true;

  // Optimistic update: show message immediately, before API calls
  lastSentTimes.value.push(Date.now());
  emit('send', content);
  inputContent.value = '';

  try {
    // Step 1: Pause the discussion
    await pauseDiscussion(props.discussionId);

    // Step 2: Inject the user message
    await injectMessage(props.discussionId, content);

    // Step 3: Resume the discussion
    await resumeDiscussion(props.discussionId);
  } catch (error) {
    emit('error', error instanceof Error ? error.message : '发送消息失败');
  } finally {
    isSending.value = false;
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleSend();
  }
}

// Clear throttle message when content changes
watch(inputContent, () => {
  throttleMessage.value = null;
});
</script>

<template>
  <div class="border-t border-gray-200 bg-white px-4 py-3">
    <!-- Throttle warning -->
    <div
      v-if="throttleMessage"
      class="mb-2 px-3 py-2 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-700 text-sm"
    >
      {{ throttleMessage }}
    </div>

    <!-- Input area -->
    <div class="flex items-end gap-3">
      <div class="flex-1 relative">
        <textarea
          v-model="inputContent"
          :placeholder="placeholder"
          :disabled="disabled"
          class="w-full px-4 py-2 pr-16 border border-gray-200 rounded-md resize-none focus:ring-2 focus:ring-[#0A0A0A] focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
          rows="2"
          @keydown="handleKeydown"
        />
        <!-- Character count -->
        <div
          class="absolute bottom-2 right-3 text-xs"
          :class="isOverLimit ? 'text-red-500' : 'text-gray-400'"
        >
          {{ charCount }}/{{ MAX_LENGTH }}
        </div>
      </div>

      <!-- Send button -->
      <button
        class="px-4 py-2 bg-[#0A0A0A] text-white rounded-md hover:bg-[#171717] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        :disabled="!canSend"
        @click="handleSend"
      >
        <svg v-if="isSending" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
        <span>{{ isSending ? '发送中...' : '发送' }}</span>
      </button>
    </div>

    <!-- Help text -->
    <div v-if="disabled" class="mt-2 text-xs text-gray-500">
      讨论未开始或已结束，无法发送消息
    </div>
    <div v-else class="mt-2 text-xs text-gray-500">
      按 Enter 发送，每分钟最多发送 {{ MAX_MESSAGES_PER_MINUTE }} 条消息
    </div>
  </div>
</template>
