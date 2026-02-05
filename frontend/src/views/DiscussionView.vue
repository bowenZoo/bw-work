<script setup lang="ts">
import { watch, onUnmounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ChatContainer, InputBox } from '@/components/chat';
import { Header, Sidebar } from '@/components/layout';
import { PlaybackControl } from '@/components/history';
import { usePlayback } from '@/composables/usePlayback';
import { useDiscussion } from '@/composables/useDiscussion';

// Props for playback mode
const props = defineProps<{
  mode?: 'live' | 'playback';
}>();

const route = useRoute();
const router = useRouter();
// Determine if we're in playback mode
const isPlaybackMode = computed(() => {
  return props.mode === 'playback' || route.name === 'discussion-playback';
});

// Get discussion ID from route
const discussionId = computed(() => route.params.id as string | undefined);

const {
  discussion,
  messages,
  isLoading: liveLoading,
  error: liveError,
  isInProgress,
  isPaused,
  connectionStatus,
  setError,
  createDiscussion,
  startDiscussion,
  loadDiscussion: loadLiveDiscussion,
  reset: resetLiveDiscussion,
  setPaused,
} = useDiscussion();

const isRunning = computed(() => discussion.value?.status === 'running');

// Playback composable (only used in playback mode)
const {
  discussion: playbackDiscussion,
  visibleMessages,
  currentIndex,
  isPlaying,
  speed,
  isLoading: playbackLoading,
  error: playbackError,
  totalMessages,
  loadDiscussion: loadPlaybackDiscussion,
  play,
  pause,
  seek,
  setSpeed,
} = usePlayback();

// Messages to display - depends on mode
const displayMessages = computed(() => {
  if (isPlaybackMode.value) {
    return visibleMessages.value;
  }
  return messages.value;
});

// Loading state
const isLoading = computed(() => {
  if (isPlaybackMode.value) {
    return playbackLoading.value;
  }
  return liveLoading.value;
});

// Error state
const errorMessage = computed(() => {
  if (isPlaybackMode.value) {
    return playbackError.value;
  }
  return liveError.value;
});

// Topic display
const topicDisplay = computed(() => {
  if (isPlaybackMode.value && playbackDiscussion.value) {
    return playbackDiscussion.value.topic;
  }
  return discussion.value?.topic ?? '';
});

// Load playback data when entering playback mode
watch(
  [discussionId, isPlaybackMode],
  ([newId, isPlayback]) => {
    if (isPlayback && newId) {
      loadPlaybackDiscussion(newId);
    }
    if (!isPlayback && newId) {
      loadLiveDiscussion(newId);
    }
  },
  { immediate: true }
);

// Handle topic submission (live mode only)
async function handleSubmit(topic: string) {
  if (isPlaybackMode.value) return;
  const newId = await createDiscussion(topic);
  if (newId) {
    setPaused(false);
    await startDiscussion();
  }
}

function handlePaused() {
  setPaused(true);
}

function handleResumed() {
  setPaused(false);
}

function handleInterventionError(message: string) {
  // Surface intervention errors in the same toast channel
  console.error('Intervention error:', message);
  setError(message);
}

// Handle playback controls
function handlePlay() {
  play();
}

function handlePause() {
  pause();
}

function handleSeek(index: number) {
  seek(index);
}

function handleSpeedChange(newSpeed: number) {
  setSpeed(newSpeed);
}

// Navigate back to history
function goBackToHistory() {
  router.push({ name: 'history' });
}

// Cleanup on unmount
onUnmounted(() => {
  if (!isPlaybackMode.value) {
    resetLiveDiscussion();
  }
});
</script>

<template>
  <div class="h-screen flex flex-col bg-gray-100">
    <!-- Header -->
    <Header :connection-status="isPlaybackMode ? 'disconnected' : connectionStatus">
      <!-- Playback mode indicator -->
      <template #extra v-if="isPlaybackMode">
        <div class="flex items-center gap-2">
          <button
            class="flex items-center gap-1 text-gray-600 hover:text-gray-800"
            @click="goBackToHistory"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
            <span>Back to History</span>
          </button>
          <span class="px-2 py-1 bg-purple-100 text-purple-700 text-sm rounded">
            Playback Mode
          </span>
        </div>
      </template>
    </Header>

    <!-- Topic display (playback mode) -->
    <div
      v-if="isPlaybackMode && topicDisplay"
      class="bg-white border-b border-gray-200 px-4 py-3"
    >
      <h2 class="text-lg font-medium text-gray-900">{{ topicDisplay }}</h2>
    </div>

    <!-- Main content -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Chat area -->
      <main class="flex-1 flex flex-col">
        <ChatContainer
          :messages="displayMessages"
          :is-loading="isLoading"
          class="flex-1"
        />

        <!-- Playback controls (playback mode) -->
        <PlaybackControl
          v-if="isPlaybackMode && totalMessages > 0"
          :current-index="currentIndex"
          :total-messages="totalMessages"
          :is-playing="isPlaying"
          :speed="speed"
          @play="handlePlay"
          @pause="handlePause"
          @seek="handleSeek"
          @speed-change="handleSpeedChange"
        />

        <!-- Input box (live mode only) -->
        <InputBox
          v-if="!isPlaybackMode"
          :disabled="isInProgress"
          :discussion-id="discussion?.id ?? undefined"
          :is-running="isRunning"
          :is-paused="isPaused"
          placeholder="Enter a topic for discussion..."
          @submit="handleSubmit"
          @paused="handlePaused"
          @resumed="handleResumed"
          @error="handleInterventionError"
        />
      </main>

      <!-- Sidebar -->
      <Sidebar :is-open="true" />
    </div>

    <!-- Error toast -->
    <div
      v-if="errorMessage"
      class="fixed bottom-4 right-4 bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg"
    >
      {{ errorMessage }}
    </div>
  </div>
</template>
