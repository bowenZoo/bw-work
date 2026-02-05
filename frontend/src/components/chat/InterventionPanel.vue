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
    emit('error', error instanceof Error ? error.message : 'Failed to pause discussion');
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
    emit('error', error instanceof Error ? error.message : 'Failed to resume discussion');
  } finally {
    isLoading.value = false;
  }
}

async function handleInject() {
  if (!canInject.value) return;

  const content = inputValue.value.trim();
  isLoading.value = true;
  try {
    const response = await injectMessage(props.discussionId, content);
    inputValue.value = '';
    injectedCount.value++;
    emit('messageInjected', content);
  } catch (error) {
    emit('error', error instanceof Error ? error.message : 'Failed to inject message');
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
        <span class="text-sm font-medium">Discussion paused - You can intervene</span>
        <span v-if="injectedCount > 0" class="text-xs bg-amber-100 px-2 py-0.5 rounded-full">
          {{ injectedCount }} message(s) queued
        </span>
      </div>

      <div class="flex gap-3">
        <div class="flex-1 relative">
          <MessageCircle class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            v-model="inputValue"
            type="text"
            placeholder="Enter your feedback or guidance for the discussion..."
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
          <span>Inject</span>
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
          <span>Resume Discussion</span>
        </button>
      </div>
    </div>

    <!-- Running state: show pause button -->
    <div v-else-if="isRunning" class="flex items-center justify-between">
      <span class="text-sm text-gray-500">Discussion in progress...</span>
      <button
        type="button"
        :disabled="!canPause"
        class="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        @click="handlePause"
      >
        <Pause class="w-4 h-4" />
        <span>Pause to Intervene</span>
      </button>
    </div>
  </div>
</template>
