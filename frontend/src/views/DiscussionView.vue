<script setup lang="ts">
import { watch, onMounted, onUnmounted, computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ChatContainer, InputBox } from '@/components/chat';
import { Header, Sidebar } from '@/components/layout';
import { PlaybackControl } from '@/components/history';
import { usePlayback } from '@/composables/usePlayback';
import { useDiscussion } from '@/composables/useDiscussion';
import api from '@/api';

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

// Get topic from query (for auto-start from home page)
const topicFromQuery = computed(() => route.query.topic as string | undefined);
const hasAutoStarted = ref(false);

// Continue discussion modal state
const showContinueModal = ref(false);
const continueFollowUp = ref('');
const isContinuing = ref(false);

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
const sidebarDiscussionId = computed(() => discussionId.value ?? discussion.value?.id ?? null);

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

// Auto-start discussion if topic is provided via query parameter (from home page)
onMounted(async () => {
  if (!isPlaybackMode.value && topicFromQuery.value && !hasAutoStarted.value) {
    hasAutoStarted.value = true;
    const newId = await createDiscussion(topicFromQuery.value);
    if (newId) {
      setPaused(false);
      await startDiscussion();
      // Clear query parameter from URL
      router.replace({ name: 'discussion', params: { id: newId } });
    }
  }
});

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

function clearError() {
  setError(null);
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

// Navigate back to home
function goBackToHome() {
  router.push({ name: 'home' });
}

// Handle continue discussion
function handleContinueClick() {
  showContinueModal.value = true;
  continueFollowUp.value = '';
}

async function submitContinue() {
  if (!continueFollowUp.value.trim() || !discussionId.value) return;

  isContinuing.value = true;
  try {
    const response = await api.post(`/api/discussions/${discussionId.value}/continue`, {
      follow_up: continueFollowUp.value.trim(),
      rounds: 2,
    });

    if (response.data.new_discussion_id) {
      showContinueModal.value = false;
      // Navigate to the new discussion
      router.push({
        name: 'discussion',
        params: { id: response.data.new_discussion_id },
      });
    }
  } catch (error: any) {
    console.error('Failed to continue discussion:', error);
    setError(error.response?.data?.detail || '继续讨论失败');
  } finally {
    isContinuing.value = false;
  }
}

function cancelContinue() {
  showContinueModal.value = false;
  continueFollowUp.value = '';
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
      <!-- Navigation and mode indicator -->
      <template #extra>
        <div class="flex items-center gap-2">
          <!-- Back to home button (live mode) -->
          <button
            v-if="!isPlaybackMode"
            class="flex items-center gap-1 text-gray-600 hover:text-gray-800"
            @click="goBackToHome"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
            <span>返回主页</span>
          </button>
          <!-- Back to history button (playback mode) -->
          <button
            v-if="isPlaybackMode"
            class="flex items-center gap-1 text-gray-600 hover:text-gray-800"
            @click="goBackToHistory"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
            <span>返回历史</span>
          </button>
          <!-- Playback mode badge -->
          <span v-if="isPlaybackMode" class="px-2 py-1 bg-purple-100 text-purple-700 text-sm rounded">
            回放模式
          </span>
        </div>
      </template>
    </Header>

    <!-- Topic display -->
    <div
      v-if="topicDisplay"
      class="bg-white border-b border-gray-200 px-4 py-3"
    >
      <div class="flex items-center gap-2">
        <span class="text-gray-500 text-sm">讨论主题:</span>
        <h2 class="text-lg font-medium text-gray-900">{{ topicDisplay }}</h2>
        <span v-if="isPlaybackMode" class="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">
          回放
        </span>
      </div>
    </div>

    <!-- Main content -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Chat area -->
      <main class="flex-1 flex flex-col relative">
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
          @continue="handleContinueClick"
        />

        <!-- Error display in center -->
        <div
          v-if="errorMessage"
          class="absolute inset-0 flex items-center justify-center pointer-events-none z-10"
        >
          <div class="bg-red-50 border border-red-300 rounded-lg shadow-lg p-6 max-w-lg mx-4 pointer-events-auto">
            <div class="flex items-start gap-3">
              <svg class="w-6 h-6 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div class="flex-1">
                <h3 class="text-red-800 font-medium mb-1">讨论出错</h3>
                <p class="text-red-700 text-sm">{{ errorMessage }}</p>
              </div>
              <button
                @click="clearError"
                class="text-red-400 hover:text-red-600"
              >
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Input box (live mode only) -->
        <InputBox
          v-if="!isPlaybackMode"
          :disabled="isInProgress"
          :discussion-id="discussion?.id ?? undefined"
          :is-running="isRunning"
          :is-paused="isPaused"
          placeholder="输入讨论主题..."
          @submit="handleSubmit"
          @paused="handlePaused"
          @resumed="handleResumed"
          @error="handleInterventionError"
        />
      </main>

      <!-- Sidebar -->
      <Sidebar :is-open="true" :discussion-id="sidebarDiscussionId" />
    </div>

    <!-- Continue Discussion Modal -->
    <Teleport to="body">
      <div
        v-if="showContinueModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @click.self="cancelContinue"
      >
        <div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg mx-4">
          <h3 class="text-lg font-semibold text-gray-900 mb-4">继续讨论</h3>
          <p class="text-gray-600 text-sm mb-4">
            基于当前讨论的上下文，输入您想要继续探讨的问题或方向：
          </p>
          <textarea
            v-model="continueFollowUp"
            class="w-full h-32 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            placeholder="例如：关于战斗系统的数值平衡，需要进一步讨论伤害计算公式..."
            :disabled="isContinuing"
          />
          <div class="flex justify-end gap-3 mt-4">
            <button
              class="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              :disabled="isContinuing"
              @click="cancelContinue"
            >
              取消
            </button>
            <button
              class="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 flex items-center gap-2"
              :disabled="isContinuing || !continueFollowUp.trim()"
              @click="submitContinue"
            >
              <svg v-if="isContinuing" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>{{ isContinuing ? '正在创建...' : '开始讨论' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
