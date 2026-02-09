<script setup lang="ts">
import { watch, onMounted, onUnmounted, computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ChatContainer, InputBox } from '@/components/chat';
import { Header } from '@/components/layout';
import { PlaybackControl } from '@/components/history';
import {
  TopicCard,
  AttachmentPreview,
  UserInputBox,
  AgendaPanel,
  CompactAgentBar,
  StageSummaryPanel,
  AgendaSummaryModal,
  DiscussionChain,
  DesignDocsPanel,
} from '@/components/discussion';
import { usePlayback } from '@/composables/usePlayback';
import { useDiscussion } from '@/composables/useDiscussion';
import { useGlobalDiscussion } from '@/composables/useGlobalDiscussion';
import { useAgentsStore } from '@/stores/agents';
import api from '@/api';
import type { AgendaItem, AgentStatus, DiscussionChainItem } from '@/types';

// Props for playback mode
const props = defineProps<{
  mode?: 'live' | 'playback';
}>();

const route = useRoute();
const router = useRouter();
const agentsStore = useAgentsStore();

// Playback mode is no longer used — completed discussions show all messages directly
const isPlaybackMode = computed(() => false);

// Determine if we're using global discussion mode (no :id in route)
const isGlobalMode = computed(() => {
  return route.name === 'discussion' && !route.params.id;
});

// Get discussion ID from route (for non-global mode)
const discussionId = computed(() => route.params.id as string | undefined);

// Get topic from query (for auto-start from home page)
const topicFromQuery = computed(() => route.query.topic as string | undefined);
const hasAutoStarted = ref(false);

// Continue discussion modal state
const showContinueModal = ref(false);
const continueFollowUp = ref('');
const isContinuing = ref(false);

// Attachment preview modal state
const showAttachmentPreview = ref(false);

// Agenda summary modal state
const showSummaryModal = ref(false);
const selectedAgendaItem = ref<AgendaItem | null>(null);

// Design docs panel state
const showDesignDocs = ref(false);

// Agent filter (for CompactAgentBar click)
const agentFilter = ref<string | null>(null);

// Discussion chain state
const discussionChain = ref<DiscussionChainItem[]>([]);
const chainCurrentIndex = ref(0);
const isContinuation = ref(false);
const continuedFrom = ref<string | null>(null);

// Global discussion composable (for global mode)
const {
  discussion: globalDiscussion,
  messages: globalMessages,
  viewerCount,
  connectionStatus: globalConnectionStatus,
  isDiscussionActive: globalIsActive,
  isPaused: globalIsPaused,
  autoPauseMessage: globalAutoPauseMessage,
  createDiscussion: createGlobalDiscussion,
  disconnect: disconnectGlobal,
  resumeDiscussion: resumeGlobalDiscussion,
  agenda,
  fetchAgenda,
  addAgendaItem,
  skipAgendaItem,
  getAgendaItemSummary,
} = useGlobalDiscussion();

// Per-discussion composable (for non-global mode)
const {
  discussion: perDiscussion,
  messages: perMessages,
  isLoading: liveLoading,
  error: liveError,
  isInProgress,
  isPaused: perIsPaused,
  connectionStatus: perConnectionStatus,
  setError,
  createDiscussion: createPerDiscussion,
  startDiscussion,
  loadDiscussion: loadLiveDiscussion,
  reset: resetLiveDiscussion,
  setPaused,
} = useDiscussion();

// Unified accessors based on mode
const discussion = computed(() => {
  if (isGlobalMode.value) {
    return globalDiscussion.value ? {
      id: globalDiscussion.value.id,
      topic: globalDiscussion.value.topic,
      messages: [],
      status: globalDiscussion.value.status,
      attachment: undefined,
    } : null;
  }
  return perDiscussion.value;
});

const messages = computed(() => {
  if (isGlobalMode.value) {
    return globalMessages.value;
  }
  return perMessages.value;
});

const connectionStatus = computed(() => {
  if (isGlobalMode.value) {
    return globalConnectionStatus.value;
  }
  return perConnectionStatus.value;
});

async function createDiscussion(topic: string) {
  if (isGlobalMode.value) {
    const autoPauseStr = sessionStorage.getItem('discussion_auto_pause_interval');
    const autoPauseInterval = autoPauseStr ? parseInt(autoPauseStr, 10) : 5;
    sessionStorage.removeItem('discussion_auto_pause_interval');
    const result = await createGlobalDiscussion(topic, 10, undefined, autoPauseInterval);
    return result.id;
  }
  return createPerDiscussion(topic);
}

const isRunning = computed(() => discussion.value?.status === 'running');

// Show round table layout when discussion has messages (running, completed, or failed)
const showRoundTableLayout = computed(() => {
  if (!discussion.value) return false;
  if (isRunning.value) return true;
  return displayMessages.value.length > 0;
});

// Unified pause state (both global and per-discussion)
const isPaused = computed(() => {
  if (isGlobalMode.value) return globalIsPaused.value;
  return perIsPaused.value;
});
const autoPauseMessage = computed(() => {
  if (isGlobalMode.value) return globalAutoPauseMessage.value;
  return '';
});

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

// Filtered messages for ChatContainer (respects agent filter)
const filteredMessages = computed(() => {
  if (!agentFilter.value) return displayMessages.value;
  return displayMessages.value.filter(m => m.agentId === agentFilter.value);
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

// Current attachment
const currentAttachment = computed(() => discussion.value?.attachment);

// Discussion status for TopicCard
const discussionStatus = computed<'pending' | 'running' | 'completed' | 'failed'>(() => {
  const status = discussion.value?.status;
  if (status === 'running') return 'running';
  if (status === 'completed') return 'completed';
  if (status === 'failed') return 'failed';
  return 'pending';
});

// Agent statuses map for RoundTable
const agentStatuses = computed(() => {
  const statusMap = new Map<string, AgentStatus>();
  agentsStore.agents.forEach(agent => {
    statusMap.set(agent.id, agent.status);
  });
  return statusMap;
});

// Current speaking agent
const speakingAgentId = computed(() => {
  return agentsStore.speakingAgent?.id;
});


// Load playback data when entering playback mode
watch(
  [discussionId, isPlaybackMode],
  async ([newId, isPlayback]) => {
    if (isPlayback && newId) {
      loadPlaybackDiscussion(newId);
      // Fetch discussion chain for playback mode
      await fetchDiscussionChain(newId);
    }
    if (!isPlayback && newId) {
      loadLiveDiscussion(newId);
      // Fetch discussion chain for live mode with ID
      await fetchDiscussionChain(newId);
    }
  },
  { immediate: true }
);

// Update continuation info when discussion changes
watch(
  discussion,
  (disc) => {
    if (disc) {
      isContinuation.value = Boolean((disc as any).is_continuation);
      continuedFrom.value = (disc as any).continued_from || null;
    } else {
      isContinuation.value = false;
      continuedFrom.value = null;
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
      if (!isGlobalMode.value) {
        setPaused(false);
        await startDiscussion();
        // Clear query parameter from URL
        router.replace({ name: 'discussion-by-id', params: { id: newId } });
      } else {
        // In global mode, the discussion auto-starts, just clear the query
        router.replace({ name: 'discussion' });
      }
    }
  }

  // Fetch agenda if in global mode
  if (isGlobalMode.value) {
    await fetchAgenda();
  }
});

// Handle topic submission (live mode only)
async function handleSubmit(topic: string) {
  if (isPlaybackMode.value) return;
  const newId = await createDiscussion(topic);
  if (newId) {
    if (!isGlobalMode.value) {
      setPaused(false);
      await startDiscussion();
    }
    // In global mode, discussion auto-starts via API
  }
}

function handlePaused() {
  setPaused(true);
}

function handleResumed() {
  setPaused(false);
}

async function handleGlobalResume() {
  try {
    await resumeGlobalDiscussion();
  } catch (e) {
    console.error('Failed to resume discussion:', e);
    setError(e instanceof Error ? e.message : '恢复讨论失败');
  }
}

function handleUserMessageSent(content: string) {
  console.log('User message sent:', content);
  // The message will be included in the next agent's context after resume
}

function handleUserInputError(message: string) {
  setError(message);
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

// Navigate back to home
function goBackToHome() {
  router.push({ name: 'home' });
}

// Fetch discussion chain
async function fetchDiscussionChain(discId: string) {
  try {
    const response = await api.get(`/api/discussions/${discId}/chain`);
    discussionChain.value = response.data.chain;
    chainCurrentIndex.value = response.data.current_index;
  } catch (error) {
    console.error('Failed to fetch discussion chain:', error);
    discussionChain.value = [];
    chainCurrentIndex.value = 0;
  }
}

// Handle chain item click
function handleChainSelect(targetId: string) {
  router.push({
    name: 'discussion-by-id',
    params: { id: targetId },
  });
}

// Handle continue discussion
function handleContinueClick() {
  showContinueModal.value = true;
  continueFollowUp.value = '';
}

async function submitContinue() {
  if (!discussionId.value) return;

  isContinuing.value = true;
  try {
    const response = await api.post(`/api/discussions/${discussionId.value}/continue`, {
      follow_up: continueFollowUp.value.trim() || '',
      rounds: 2,
    });

    if (response.data.new_discussion_id) {
      showContinueModal.value = false;
      // Navigate to the new discussion
      router.push({
        name: 'discussion-by-id',
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

// Attachment preview handlers
function handlePreviewAttachment() {
  showAttachmentPreview.value = true;
}

function handleClosePreview() {
  showAttachmentPreview.value = false;
}

// Agenda handlers
async function handleViewSummary(item: AgendaItem) {
  selectedAgendaItem.value = item;
  showSummaryModal.value = true;

  // Fetch latest summary if needed
  if (!item.summary) {
    const result = await getAgendaItemSummary(item.id);
    if (result && selectedAgendaItem.value) {
      selectedAgendaItem.value = {
        ...selectedAgendaItem.value,
        summary: result.summary,
        summary_details: result.details,
      };
    }
  }
}

function handleCloseSummary() {
  showSummaryModal.value = false;
  selectedAgendaItem.value = null;
}

async function handleAddAgendaItem() {
  const title = prompt('请输入新议题标题：');
  if (title && title.trim()) {
    await addAgendaItem(title.trim());
  }
}

async function handleSkipAgendaItem(itemId: string) {
  await skipAgendaItem(itemId);
}

// CompactAgentBar agent click handler — toggle filter
function handleAgentClick(agentId: string) {
  agentFilter.value = agentFilter.value === agentId ? null : agentId;
}

// Cleanup on unmount
onUnmounted(() => {
  if (!isPlaybackMode.value) {
    resetLiveDiscussion();
  }
});
</script>

<template>
  <div class="discussion-layout">
    <!-- Header -->
    <Header :connection-status="connectionStatus">
      <template #extra>
        <div class="flex items-center gap-2">
          <button
            class="flex items-center gap-1 text-gray-600 hover:text-gray-800"
            @click="goBackToHome"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
            <span>返回主页</span>
          </button>
          <!-- Completed badge -->
          <span v-if="discussion?.status === 'completed'" class="px-2 py-1 bg-green-50 text-green-700 text-sm rounded">
            已完成
          </span>
          <!-- Global mode viewer count -->
          <span v-if="isGlobalMode" class="flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 text-sm rounded">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            <span>{{ viewerCount }} 人观看</span>
          </span>
        </div>
      </template>
    </Header>

    <!-- Topic Card Header -->
    <div v-if="topicDisplay" class="discussion-header">
      <div class="header-content">
        <TopicCard
          :topic="topicDisplay"
          :status="discussionStatus"
          :attachment="currentAttachment"
          @preview-attachment="handlePreviewAttachment"
        />
        <!-- Continuation indicator -->
        <div v-if="isContinuation" class="continuation-indicator">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
          </svg>
          <span>续前讨论</span>
          <button
            v-if="continuedFrom"
            class="view-original-btn"
            @click="router.push({ name: 'discussion-by-id', params: { id: continuedFrom } })"
          >
            查看原讨论
          </button>
        </div>
        <!-- Discussion chain -->
        <DiscussionChain
          v-if="discussionChain.length > 1"
          :chain="discussionChain"
          :current-index="chainCurrentIndex"
          @select="handleChainSelect"
        />
      </div>
      <div class="header-actions">
        <!-- Design docs button (visible when discussion has an ID) -->
        <button
          v-if="discussion?.id"
          class="action-btn"
          :class="{ 'is-active': showDesignDocs }"
          @click="showDesignDocs = true"
          title="策划文档"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </button>
        <button
          v-if="currentAttachment"
          class="action-btn"
          @click="handlePreviewAttachment"
          title="查看附件"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
        </button>
        <button
          v-if="isRunning && !isGlobalMode"
          class="action-btn"
          :class="{ 'is-paused': isPaused }"
          @click="isPaused ? handleResumed() : handlePaused()"
          :title="isPaused ? '继续讨论' : '暂停讨论'"
        >
          <svg v-if="isPaused" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Auto-pause banner (global mode) -->
    <div v-if="isPaused && isRunning" class="auto-pause-banner">
      <div class="auto-pause-content">
        <svg class="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="auto-pause-text">{{ autoPauseMessage || '讨论已暂停' }}</span>
      </div>
      <button
        v-if="isGlobalMode"
        class="auto-pause-resume-btn"
        @click="handleGlobalResume"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
        </svg>
        继续讨论
      </button>
    </div>


    <!-- Main content area -->
    <main v-if="showRoundTableLayout && !isPlaybackMode" class="discussion-main">
      <!-- Left Panel: Agent Bar + Message Feed -->
      <div class="left-panel">
        <!-- Compact Agent Bar -->
        <CompactAgentBar
          :agents="agentsStore.agents"
          :statuses="agentStatuses"
          :current-speaker="speakingAgentId"
          @select-agent="handleAgentClick"
        />

        <!-- Agent filter indicator -->
        <div v-if="agentFilter" class="filter-indicator">
          <span>筛选: {{ agentsStore.getAgentById(agentFilter)?.name || agentFilter }}</span>
          <button class="clear-filter-btn" @click="agentFilter = null">&times;</button>
        </div>

        <!-- Agenda Panel (only when agenda has items) -->
        <AgendaPanel
          v-if="agenda && agenda.items.length > 0"
          :agenda="agenda"
          @view-summary="handleViewSummary"
          @skip-item="handleSkipAgendaItem"
          @add-item="handleAddAgendaItem"
        />

        <!-- Message Feed -->
        <ChatContainer
          :messages="filteredMessages"
          :is-loading="isLoading"
          class="message-feed"
        />
      </div>

      <!-- Right Panel: Stage Summary -->
      <section class="right-panel">
        <StageSummaryPanel :messages="displayMessages" />
      </section>
    </main>

    <!-- Fallback layout (no discussion yet) -->
    <main v-else class="discussion-main-fallback">
      <ChatContainer
        :messages="displayMessages"
        :is-loading="isLoading"
        class="flex-1"
      />
    </main>

    <!-- Error display -->
    <div
      v-if="errorMessage"
      class="error-overlay"
    >
      <div class="error-card">
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

    <!-- Footer -->
    <footer class="discussion-footer">
      <!-- Input box for starting new discussions (no discussion yet) -->
      <InputBox
        v-if="!discussion && !isRunning"
        :disabled="isInProgress"
        :discussion-id="undefined"
        :is-running="false"
        :is-paused="false"
        placeholder="输入讨论主题..."
        @submit="handleSubmit"
        @paused="handlePaused"
        @resumed="handleResumed"
        @error="handleInterventionError"
      />

      <!-- User input box when discussion is running -->
      <UserInputBox
        v-if="isRunning && discussion?.id"
        :discussion-id="discussion.id"
        :disabled="!isRunning"
        placeholder="发表你的观点（会自动暂停、注入、恢复）..."
        @send="handleUserMessageSent"
        @error="handleUserInputError"
      />

      <!-- Continue button for completed discussions -->
      <div v-if="discussion?.status === 'completed' && discussionId" class="completed-footer">
        <button class="continue-discussion-btn" @click="handleContinueClick">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
          </svg>
          <span>继续讨论</span>
        </button>
      </div>
    </footer>

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
              :disabled="isContinuing"
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

    <!-- Attachment Preview Modal -->
    <AttachmentPreview
      v-if="currentAttachment"
      :visible="showAttachmentPreview"
      :filename="currentAttachment.filename"
      :content="currentAttachment.content"
      @close="handleClosePreview"
    />

    <!-- Agenda Summary Modal -->
    <AgendaSummaryModal
      :visible="showSummaryModal"
      :item="selectedAgendaItem"
      @close="handleCloseSummary"
    />

    <!-- Design Docs Panel -->
    <DesignDocsPanel
      :visible="showDesignDocs"
      :discussion-id="discussion?.id ?? ''"
      :discussion-topic="topicDisplay"
      @close="showDesignDocs = false"
    />
  </div>
</template>

<style scoped>
.discussion-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
}

.discussion-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.auto-pause-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #fef3c7;
  border-bottom: 1px solid #fcd34d;
}

.auto-pause-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.auto-pause-text {
  font-size: 14px;
  color: #92400e;
  font-weight: 500;
}

.auto-pause-resume-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  background: var(--primary-color);
  color: white;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s;
}

.auto-pause-resume-btn:hover {
  background: #171717;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.continuation-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background-color: rgba(5, 150, 105, 0.08);
  border: 1px solid rgba(5, 150, 105, 0.2);
  border-radius: 6px;
  color: var(--success-color);
  font-size: 12px;
  font-weight: 500;
  width: fit-content;
}

.view-original-btn {
  padding: 2px 8px;
  background-color: rgba(5, 150, 105, 0.1);
  border-radius: 4px;
  color: var(--success-color);
  font-size: 11px;
  transition: background-color 0.2s;
}

.view-original-btn:hover {
  background-color: rgba(5, 150, 105, 0.2);
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 6px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.action-btn.is-paused {
  background: var(--warning-color);
  border-color: var(--warning-color);
  color: white;
}

.action-btn.is-active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
}

/* Main content - Two Column Layout */
.discussion-main {
  flex: 1;
  display: grid;
  grid-template-columns: 60% 40%;
  gap: 12px;
  padding: 12px;
  overflow: hidden;
}

.left-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: hidden;
}

.message-feed {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--border-color);
  border-radius: 6px;
}

.filter-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: rgba(10, 10, 10, 0.05);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.clear-filter-btn {
  font-size: 16px;
  line-height: 1;
  color: var(--text-weak);
  cursor: pointer;
  padding: 0 4px;
}

.clear-filter-btn:hover {
  color: var(--text-primary);
}

.right-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Fallback layout for non-running or playback mode */
.discussion-main-fallback {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

/* Error overlay */
.error-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 10;
}

.error-card {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 16px 24px;
  max-width: 480px;
  margin: 16px;
  pointer-events: auto;
}

/* Footer */
.discussion-footer {
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
}

.completed-footer {
  display: flex;
  justify-content: center;
  padding: 4px 0;
}

.continue-discussion-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  background: var(--primary-color);
  color: white;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  transition: opacity 0.2s;
}

.continue-discussion-btn:hover {
  opacity: 0.85;
}

/* Responsive layout */
@media (max-width: 1024px) {
  .discussion-main {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
  }

  .right-panel {
    order: 1;
    max-height: 300px;
  }

  .left-panel {
    order: 2;
  }
}

@media (max-width: 768px) {
  .discussion-main {
    padding: 8px;
    gap: 8px;
  }

  .right-panel {
    max-height: 200px;
  }
}
</style>
