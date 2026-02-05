<script setup lang="ts">
import { ref, computed } from 'vue';
import { Send, Play, Pause, MessageCircle } from 'lucide-vue-next';
import {
  pauseDiscussion,
  resumeDiscussion,
  injectMessage,
} from '@/api/intervention';

const props = defineProps<{
  discussionId: string;
  isRunning: boolean;
  isPaused: boolean;
}>();

const emit = defineEmits<{
  paused: [];
  resumed: [];
  messageInjected: [content: string];
  error: [message: string];
}>();

const inputValue = ref('');
const isLoading = ref(false);
const injectedCount = ref(0);

const canPause = computed(() => props.isRunning && !props.isPaused && !isLoading.value);
const canResume = computed(() => props.isPaused && !isLoading.value);
const canInject = computed(() => props.isPaused && inputValue.value.trim() && !isLoading.value);

async function handlePause() {
  if (!canPause.value) return;

  isLoading.value = true;
  try {
    await pauseDiscussion(props.discussionId);
    emit('paused');
  } catch (error) {
    emit('error', error instanceof Error ? error.message : '暂停讨论失败');
  } finally {
    isLoading.value = false;
  }
}

async function handleResume() {
  if (!canResume.value) return;

  isLoading.value = true;
  try {
    await resumeDiscussion(props.discussionId);
    injectedCount.value = 0;
    inputValue.value = '';
    emit('resumed');
  } catch (error) {
    emit('error', error instanceof Error ? error.message : '恢复讨论失败');
  } finally {
    isLoading.value = false;
  }
}

async function handleInject() {
  if (!canInject.value) return;

  const content = inputValue.value.trim();
  isLoading.value = true;
  try {
    await injectMessage(props.discussionId, content);
    inputValue.value = '';
    injectedCount.value++;
    emit('messageInjected', content);
  } catch (error) {
    emit('error', error instanceof Error ? error.message : '注入消息失败');
  } finally {
    isLoading.value = false;
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleInject();
  }
}
</script>

<template>
  <div class="border-t border-gray-200 bg-gray-50 p-4">
    <!-- Paused state: show input and control buttons -->
    <div v-if="isPaused" class="space-y-3">
      <div class="flex items-center gap-2 text-amber-600">
        <Pause class="w-4 h-4" />
        <span class="text-sm font-medium">讨论已暂停 - 你可以介入</span>
        <span v-if="injectedCount > 0" class="text-xs bg-amber-100 px-2 py-0.5 rounded-full">
          {{ injectedCount }} 条消息待发送
        </span>
      </div>

      <div class="flex gap-3">
        <div class="flex-1 relative">
          <MessageCircle class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            v-model="inputValue"
            type="text"
            placeholder="输入你对讨论的反馈或指导..."
            :disabled="isLoading"
            class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
            @keydown="handleKeydown"
          />
        </div>
        <button
          type="button"
          :disabled="!canInject"
          class="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          @click="handleInject"
        >
          <Send class="w-4 h-4" />
          <span>注入</span>
        </button>
      </div>

      <div class="flex justify-end">
        <button
          type="button"
          :disabled="!canResume"
          class="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          @click="handleResume"
        >
          <Play class="w-4 h-4" />
          <span>恢复讨论</span>
        </button>
      </div>
    </div>

    <!-- Running state: show pause button -->
    <div v-else-if="isRunning" class="flex items-center justify-between">
      <span class="text-sm text-gray-500">讨论进行中...</span>
      <button
        type="button"
        :disabled="!canPause"
        class="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        @click="handlePause"
      >
        <Pause class="w-4 h-4" />
        <span>暂停并介入</span>
      </button>
    </div>
  </div>
</template>
