<script setup lang="ts">
import { watch, onMounted, onUnmounted, computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ChatContainer, InputBox } from '@/components/chat';
import { Header } from '@/components/layout';
import { PlaybackControl } from '@/components/history';
import {
  AttachmentPreview,
  UserInputBox,
  AgendaPanel,
  CompactAgentBar,
  AgendaSummaryModal,
  RightPanel,
  InterventionDigestCard,
  HolisticReviewCard,
  PasswordVerifyModal,
} from '@/components/discussion';
import { usePlayback } from '@/composables/usePlayback';
import { useDiscussion } from '@/composables/useDiscussion';
import { useAgentsStore } from '@/stores/agents';
import api from '@/api';
import { getDiscussionStyles } from '@/api/discussion';
import type { AgendaItem, AgentStatus, DiscussionStyle, DiscussionStyleFull, DiscussionStyleOverrides } from '@/types';

// Props for playback mode
const props = defineProps<{
  mode?: 'live' | 'playback';
}>();

const route = useRoute();
const router = useRouter();
const agentsStore = useAgentsStore();

// Playback mode is no longer used — completed discussions show all messages directly
const isPlaybackMode = computed(() => false);

// Get discussion ID from route
const discussionId = computed(() => route.params.id as string | undefined);

// Password verification state
const needsPassword = ref(false);
const passwordVerified = ref(false);

// Continue discussion state
const continueFollowUp = ref('');
const continueRounds = ref(5);
const showContinuePopup = ref(false);
const isContinuing = ref(false);
const continueStyle = ref('');
const discussionStyles = ref<DiscussionStyle[]>([]);

// Enhanced continue: full style data with overrides for prompt editing
const discussionStylesFull = ref<DiscussionStyleFull[]>([]);
const continueOverrides = ref<Partial<DiscussionStyleOverrides> | null>(null);
const showPromptEditor = ref(false);
const overridesModified = ref(false);

// Attachment preview modal state
const showAttachmentPreview = ref(false);

// Agenda summary modal state
const showSummaryModal = ref(false);
const selectedAgendaItem = ref<AgendaItem | null>(null);

// Agent filter (for CompactAgentBar click)
const agentFilter = ref<string | null>(null);

// Per-discussion composable (unified)
const {
  discussion,
  messages,
  isLoading: liveLoading,
  error: liveError,
  isInProgress,
  isPaused,
  autoPauseMessage,
  connectionStatus,
  setError,
  startDiscussion,
  loadDiscussion: loadLiveDiscussion,
  reset: resetLiveDiscussion,
  setPaused,
  resumeDiscussion,
  pauseDiscussion,
  focusSection,
  agenda,
  fetchAgenda,
  addAgendaItem,
  skipAgendaItem,
  getAgendaItemSummary,
  roundSummaries,
  latestDocUpdate,
  docPlan,
  docContents,
  currentSectionId,
  leadPlannerDigests,
  interventionAssessments,
  holisticReviews,
} = useDiscussion();

const isRunning = computed(() => discussion.value?.status === 'running');
const isFinished = computed(() => discussion.value?.status === 'completed' || discussion.value?.status === 'failed');

// Show round table layout when discussion has messages (running, completed, or failed)
const showRoundTableLayout = computed(() => {
  if (!discussion.value) return false;
  if (isRunning.value) return true;
  return displayMessages.value.length > 0;
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

const statusLabel = computed(() => {
  switch (discussionStatus.value) {
    case 'running': return '进行中';
    case 'completed': return '已完成';
    case 'failed': return '已中断';
    default: return '待开始';
  }
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


// Load discussion when route changes
watch(
  [discussionId, isPlaybackMode],
  async ([newId, isPlayback]) => {
    if (!newId) return;
    if (isPlayback) {
      loadPlaybackDiscussion(newId);
      return;
    }

    // Check password before loading data
    const verified = JSON.parse(sessionStorage.getItem('verified_discussions') || '{}');
    if (verified[newId]) {
      passwordVerified.value = true;
    } else {
      // Lightweight request to check if password is needed
      try {
        const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';
        const res = await fetch(`${API_BASE_URL}/api/discussions/${newId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.has_password) {
            needsPassword.value = true;
            return; // Don't load data, wait for password verification
          }
        }
      } catch {
        // Don't block on error
      }
      passwordVerified.value = true;
    }

    // Password verified or not needed — load data
    loadLiveDiscussion(newId);
  },
  { immediate: true }
);

onMounted(async () => {
  // Fetch agenda if discussion is loaded
  if (discussionId.value) {
    await fetchAgenda();
  }
  // Load discussion styles for continue popup
  loadDiscussionStyles();
});

function onPasswordVerified() {
  needsPassword.value = false;
  passwordVerified.value = true;
  // Load discussion data after password verification
  const id = discussionId.value || (route.params.id as string);
  if (id) {
    loadLiveDiscussion(id);
  }
}

function onPasswordCancel() {
  router.push('/');
}

// Handle topic submission (live mode only — creates a new discussion)
async function handleSubmit(topic: string) {
  if (isPlaybackMode.value) return;
  // This path is for the footer input box when no discussion exists yet
  // In the new flow, discussions are created from HomeView and we navigate here
  // But keep this for backward compat
  const { createCurrentDiscussion } = await import('@/api/discussion');
  try {
    const response = await createCurrentDiscussion({ topic });
    router.push({ name: 'discussion-by-id', params: { id: response.id } });
  } catch (e) {
    console.error('Failed to create discussion:', e);
    setError(e instanceof Error ? e.message : '创建讨论失败');
  }
}

function handlePaused() {
  setPaused(true);
}

function handleResumed() {
  setPaused(false);
}

async function handleManualPause() {
  if (discussion.value?.id) {
    try {
      await pauseDiscussion();
    } catch (e) {
      console.error('Failed to pause discussion:', e);
      setError(e instanceof Error ? e.message : '暂停讨论失败');
    }
  }
}

async function handleResume() {
  try {
    await resumeDiscussion();
  } catch (e) {
    console.error('Failed to resume discussion:', e);
    setError(e instanceof Error ? e.message : '恢复讨论失败');
  }
}

function handleUserMessageSent(content: string) {
  console.log('User message sent:', content);
}

function handleUserInputError(message: string) {
  setError(message);
}

function handleInterventionError(message: string) {
  console.error('Intervention error:', message);
  setError(message);
}

function clearError() {
  setError(null);
}

// Handle playback controls
function handlePlay() { play(); }
function handlePause() { pause(); }
function handleSeek(index: number) { seek(index); }
function handleSpeedChange(newSpeed: number) { setSpeed(newSpeed); }

// Navigate back to home
function goBackToHome() {
  router.push({ name: 'home' });
}

async function submitContinue() {
  const discId = discussionId.value || discussion.value?.id;
  if (!discId) return;
  const followUp = continueFollowUp.value.trim();

  isContinuing.value = true;
  try {
    const payload: Record<string, any> = {
      follow_up: followUp,
      additional_rounds: continueRounds.value,
    };
    if (continueStyle.value) {
      payload.discussion_style = continueStyle.value;
    }
    // If user has modified prompt overrides, send agent_configs
    if (overridesModified.value && continueOverrides.value) {
      payload.agent_configs = {
        lead_planner: continueOverrides.value,
      };
    }
    await api.post(`/api/discussions/${discId}/extend`, payload);
    continueFollowUp.value = '';
    showContinuePopup.value = false;
    showPromptEditor.value = false;
    continueOverrides.value = null;
    overridesModified.value = false;
  } catch (error: any) {
    console.error('Failed to extend discussion:', error);
    setError(error.response?.data?.detail || '继续讨论失败');
  } finally {
    isContinuing.value = false;
  }
}

// Open continue popup and use already-loaded discussion data for style
function openContinuePopup() {
  showContinuePopup.value = true;
  showPromptEditor.value = false;
  overridesModified.value = false;

  // Use style from already-loaded discussion data instead of extra API request
  const currentStyle = (discussion.value as any)?.discussion_style;
  if (currentStyle && discussionStyles.value.some(s => s.id === currentStyle)) {
    continueStyle.value = currentStyle;
  }

  if (continueStyle.value) {
    loadOverridesForStyle(continueStyle.value);
  }
}

// Load overrides when a style is selected in continue popup
function loadOverridesForStyle(styleId: string) {
  const full = discussionStylesFull.value.find(s => s.id === styleId);
  if (full?.overrides) {
    continueOverrides.value = { ...full.overrides };
    overridesModified.value = false;
  } else {
    continueOverrides.value = null;
    overridesModified.value = false;
  }
}

// Handle style change in continue popup
function handleContinueStyleChange(styleId: string) {
  continueStyle.value = styleId;
  loadOverridesForStyle(styleId);
}

// Reset overrides to the style default
function resetContinueOverrides() {
  loadOverridesForStyle(continueStyle.value);
}

// Load discussion styles for continue popup
async function loadDiscussionStyles() {
  try {
    const data = await getDiscussionStyles();
    discussionStyles.value = data.styles;
    discussionStylesFull.value = data.styles;
    continueStyle.value = data.default;
  } catch {
    discussionStyles.value = [
      { id: 'socratic', name: '苏格拉底式', description: '不断追问「为什么」，逼迫每个决策回到第一性原理' },
      { id: 'directive', name: '主策划主导制', description: '主策划提出框架，团队挑战补充，主策划有否决权' },
      { id: 'debate', name: '辩论制', description: '各策划独立提案，互相质疑辩论，主策划裁决' },
    ];
    discussionStylesFull.value = [];
    continueStyle.value = 'socratic';
  }
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

// Handle focus section request
async function handleFocusSection(sectionId: string) {
  await focusSection(sectionId);
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
    <!-- Password verification modal -->
    <PasswordVerifyModal
      v-if="needsPassword && !passwordVerified"
      :discussion-id="discussionId || (route.params.id as string)"
      :topic="discussion?.topic"
      @verified="onPasswordVerified"
      @cancel="onPasswordCancel"
    />

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
        </div>
      </template>
    </Header>

    <!-- Compact Topic Bar -->
    <div v-if="topicDisplay" class="topic-bar">
      <div class="topic-bar-left">
        <span class="topic-text" :title="topicDisplay">{{ topicDisplay }}</span>
        <span class="status-badge" :class="`status-${discussionStatus}`">{{ statusLabel }}</span>
      </div>
      <div class="topic-bar-right">
        <button
          v-if="currentAttachment"
          class="action-btn-sm"
          @click="handlePreviewAttachment"
          title="查看附件"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
        </button>
        <button
          v-if="isRunning"
          class="action-btn-sm"
          :class="{ 'is-paused': isPaused }"
          @click="isPaused ? handleResume() : handleManualPause()"
          :title="isPaused ? '继续讨论' : '暂停讨论'"
        >
          <svg v-if="isPaused" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Auto-pause banner -->
    <div v-if="isPaused && isRunning" class="auto-pause-banner">
      <div class="auto-pause-content">
        <svg class="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="auto-pause-text">{{ autoPauseMessage || '讨论已暂停' }}</span>
      </div>
      <button
        class="auto-pause-resume-btn"
        @click="handleResume"
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

        <!-- Lead Planner Digest Card -->
        <InterventionDigestCard
          v-if="leadPlannerDigests.length > 0 || interventionAssessments.length > 0"
          :digests="leadPlannerDigests"
          :assessments="interventionAssessments"
        />

        <!-- Holistic Review Card -->
        <HolisticReviewCard
          v-if="holisticReviews.length > 0"
          :reviews="holisticReviews"
        />

        <!-- Waiting hint when discussion just started, no messages yet -->
        <div v-if="isRunning && displayMessages.length === 0" class="waiting-placeholder">
          <div class="thinking-dots">
            <span class="dot" />
            <span class="dot" />
            <span class="dot" />
          </div>
          <p class="waiting-text">主策划正在思考中...</p>
          <p class="waiting-subtext">讨论即将开始</p>
        </div>

        <!-- Message Feed -->
        <ChatContainer
          v-else
          :messages="filteredMessages"
          :is-loading="isLoading"
          class="message-feed"
        />
      </div>

      <!-- Right Panel: Tabs (Round Summaries / Design Docs) + Input -->
      <section class="right-panel">
        <RightPanel
          :round-summaries="roundSummaries"
          :discussion-id="discussion?.id ?? ''"
          :latest-doc-update="latestDocUpdate"
          :doc-plan="docPlan"
          :doc-contents="docContents"
          :current-section-id="currentSectionId"
          @focus-section="handleFocusSection"
        />
        <!-- User input box embedded in right panel (running) -->
        <UserInputBox
          v-if="isRunning && discussion?.id"
          :discussion-id="discussion.id"
          :disabled="!isRunning"
          placeholder="发表你的观点（会自动暂停、注入、恢复）..."
          @send="handleUserMessageSent"
          @error="handleUserInputError"
        />
        <!-- Continue trigger for completed/failed discussions -->
        <div v-if="isFinished && (discussionId || discussion?.id)" class="continue-area">
          <button
            v-if="!showContinuePopup"
            class="continue-trigger-btn"
            @click="openContinuePopup"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            </svg>
            <span>继续讨论</span>
          </button>
          <!-- Expanded continue panel -->
          <div v-else class="continue-panel">
            <!-- Follow-up input -->
            <div class="continue-popup-row">
              <input
                v-model="continueFollowUp"
                type="text"
                class="continue-text-input"
                placeholder="可选：输入追加方向..."
                :disabled="isContinuing"
                @keydown.enter="submitContinue"
              />
            </div>

            <!-- Rounds + Style row -->
            <div class="continue-row-split">
              <div class="continue-popup-row">
                <label class="continue-label">追加轮次</label>
                <div class="rounds-stepper">
                  <button class="stepper-btn" @click="continueRounds = Math.max(1, continueRounds - 1)">-</button>
                  <input
                    v-model.number="continueRounds"
                    type="number"
                    class="rounds-input"
                    min="1"
                    max="100"
                  />
                  <button class="stepper-btn" @click="continueRounds = Math.min(100, continueRounds + 1)">+</button>
                </div>
              </div>
            </div>

            <!-- Discussion style selector -->
            <div v-if="discussionStyles.length > 0" class="continue-style-row">
              <label class="continue-label">讨论风格</label>
              <div class="continue-style-chips">
                <button
                  v-for="style in discussionStyles"
                  :key="style.id"
                  class="style-chip"
                  :class="{ 'style-chip-active': continueStyle === style.id }"
                  :title="style.description"
                  @click="handleContinueStyleChange(style.id)"
                >
                  {{ style.name }}
                </button>
              </div>
            </div>

            <!-- Prompt editor toggle -->
            <button class="prompt-editor-toggle" @click="showPromptEditor = !showPromptEditor">
              <svg class="prompt-editor-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              <span>自定义 Prompt</span>
              <svg class="toggle-chevron" :class="{ 'is-open': showPromptEditor }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
              <span v-if="overridesModified" class="modified-dot" />
            </button>

            <!-- Prompt editor content -->
            <div v-if="showPromptEditor && continueOverrides" class="prompt-editor">
              <div class="prompt-editor-header">
                <span class="prompt-editor-hint">编辑主策划的提示词（基于当前风格预设）</span>
                <button
                  v-if="overridesModified"
                  class="prompt-reset-btn"
                  @click="resetContinueOverrides"
                >
                  <svg class="prompt-reset-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  恢复预设
                </button>
              </div>
              <div class="prompt-field">
                <label class="prompt-field-label">目标 (Goal)</label>
                <textarea
                  class="prompt-textarea"
                  rows="2"
                  :value="continueOverrides.goal || ''"
                  placeholder="主策划的目标..."
                  @input="continueOverrides!.goal = ($event.target as HTMLTextAreaElement).value; overridesModified = true"
                />
              </div>
              <div class="prompt-field">
                <label class="prompt-field-label">背景 (Backstory)</label>
                <textarea
                  class="prompt-textarea"
                  rows="3"
                  :value="continueOverrides.backstory || ''"
                  placeholder="主策划的背景设定..."
                  @input="continueOverrides!.backstory = ($event.target as HTMLTextAreaElement).value; overridesModified = true"
                />
              </div>
              <div class="prompt-field">
                <label class="prompt-field-label">沟通风格 (Communication Style)</label>
                <textarea
                  class="prompt-textarea"
                  rows="2"
                  :value="continueOverrides.communication_style || ''"
                  placeholder="沟通和表达方式..."
                  @input="continueOverrides!.communication_style = ($event.target as HTMLTextAreaElement).value; overridesModified = true"
                />
              </div>
            </div>

            <!-- No overrides hint (when style has no override data) -->
            <div v-else-if="showPromptEditor && !continueOverrides" class="prompt-editor-empty">
              <span>当前风格暂无可编辑的 Prompt 数据</span>
            </div>

            <!-- Actions -->
            <div class="continue-popup-actions">
              <button class="continue-cancel-btn" @click="showContinuePopup = false; showPromptEditor = false" :disabled="isContinuing">取消</button>
              <button class="continue-confirm-btn" :disabled="isContinuing" @click="submitContinue">
                <svg v-if="isContinuing" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>{{ isContinuing ? '创建中...' : `继续 ${continueRounds} 轮` }}</span>
              </button>
            </div>
          </div>
        </div>
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

    <!-- Footer (only when no discussion yet) -->
    <footer v-if="!discussion && !isRunning" class="discussion-footer">
      <InputBox
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
    </footer>

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

  </div>
</template>

<style scoped>
.discussion-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
}

/* Compact topic bar */
.topic-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  gap: 12px;
}

.topic-bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.topic-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 400px;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
}

.status-running {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.status-completed {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.status-failed {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.status-pending {
  background: rgba(156, 163, 175, 0.1);
  color: #6b7280;
}

.topic-bar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.action-btn-sm {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn-sm:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.action-btn-sm.is-paused {
  background: var(--warning-color);
  border-color: var(--warning-color);
  color: white;
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


/* Main content - Two Column Layout */
.discussion-main {
  flex: 1;
  display: grid;
  grid-template-columns: 55% 45%;
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

/* Continue discussion area (in right panel) */
.continue-area {
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.continue-trigger-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--primary-color, #0A0A0A);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}

.continue-trigger-btn:hover {
  background: var(--bg-hover, rgba(0, 0, 0, 0.04));
}

.continue-panel {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 60vh;
  overflow-y: auto;
}

.continue-row-split {
  display: flex;
  align-items: center;
  gap: 12px;
}

.continue-style-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.continue-style-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.style-chip {
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.15s;
}

.style-chip:hover {
  border-color: #d1d5db;
  background: var(--bg-hover, #f9fafb);
}

.style-chip-active {
  color: var(--primary-color, #3b82f6);
  background: #eff6ff;
  border-color: var(--primary-color, #3b82f6);
}

.style-chip-active:hover {
  background: #eff6ff;
  border-color: var(--primary-color, #3b82f6);
}

.continue-popup-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.continue-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

.rounds-stepper {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  overflow: hidden;
}

.stepper-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-primary);
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}

.stepper-btn:hover {
  background: var(--bg-tertiary, #e5e7eb);
  color: var(--text-primary);
}

.rounds-input {
  width: 40px;
  height: 28px;
  text-align: center;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: none;
  border-left: 1px solid var(--border-color);
  border-right: 1px solid var(--border-color);
  -moz-appearance: textfield;
}

.rounds-input::-webkit-inner-spin-button,
.rounds-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.continue-text-input {
  flex: 1;
  padding: 7px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--bg-primary);
  transition: border-color 0.2s;
}

.continue-text-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.continue-text-input::placeholder {
  color: var(--text-secondary);
}

.continue-text-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.continue-popup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.continue-cancel-btn {
  padding: 6px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.continue-cancel-btn:hover:not(:disabled) {
  background: var(--bg-tertiary, #e5e7eb);
}

.continue-confirm-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  color: white;
  background: var(--primary-color, #0A0A0A);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.continue-confirm-btn:hover:not(:disabled) {
  background: #171717;
}

.continue-confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Prompt editor toggle */
.prompt-editor-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 0;
  transition: color 0.15s;
  align-self: flex-start;
  position: relative;
}

.prompt-editor-toggle:hover {
  color: var(--primary-color, #0A0A0A);
}

.prompt-editor-icon {
  width: 13px;
  height: 13px;
}

.toggle-chevron {
  width: 13px;
  height: 13px;
  transition: transform 0.2s;
}

.toggle-chevron.is-open {
  transform: rotate(180deg);
}

.modified-dot {
  width: 6px;
  height: 6px;
  background: var(--primary-color, #3b82f6);
  border-radius: 50%;
  flex-shrink: 0;
}

/* Prompt editor panel */
.prompt-editor {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--bg-primary);
}

.prompt-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.prompt-editor-hint {
  font-size: 11px;
  color: var(--text-weak);
}

.prompt-reset-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--text-secondary);
  padding: 2px 7px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--bg-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.prompt-reset-btn:hover {
  color: var(--primary-color, #0A0A0A);
  border-color: var(--primary-color, #0A0A0A);
}

.prompt-reset-icon {
  width: 11px;
  height: 11px;
}

.prompt-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.prompt-field-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
}

.prompt-textarea {
  padding: 6px 10px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-secondary);
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color 0.2s;
}

.prompt-textarea:focus {
  outline: none;
  border-color: var(--primary-color, #0A0A0A);
  box-shadow: 0 0 0 2px rgba(10, 10, 10, 0.06);
}

.prompt-textarea::placeholder {
  color: var(--text-weak);
}

.prompt-editor-empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text-weak);
  border: 1px dashed var(--border-color);
  border-radius: 8px;
}

/* Waiting placeholder */
.waiting-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  min-height: 0;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-secondary);
}

.thinking-dots {
  display: flex;
  gap: 6px;
}

.thinking-dots .dot {
  width: 8px;
  height: 8px;
  background: var(--primary-color, #3b82f6);
  border-radius: 50%;
  animation: thinking-bounce 1.4s infinite ease-in-out both;
}

.thinking-dots .dot:nth-child(1) {
  animation-delay: -0.32s;
}

.thinking-dots .dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes thinking-bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.waiting-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-secondary);
}

.waiting-subtext {
  font-size: 13px;
  color: var(--text-weak);
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
