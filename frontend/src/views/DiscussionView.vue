<script setup lang="ts">
import { watch, onMounted, onUnmounted, computed, ref, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ChatContainer, InputBox } from '@/components/chat';
import { Header } from '@/components/layout';
import { PlaybackControl } from '@/components/history';
import {
  AttachmentPreview,
  AgendaPanel,
  CompactAgentBar,
  AgendaSummaryModal,
  RightPanel,
  InterventionDigestCard,
  HolisticReviewCard,
  PasswordVerifyModal,
  ProducerInput,
} from '@/components/discussion';
import { usePlayback } from '@/composables/usePlayback';
import { useDiscussion } from '@/composables/useDiscussion';
import { useAgentsStore } from '@/stores/agents';
import { useDiscussionStore } from '@/stores/discussion';
import api from '@/api';
import { useUserStore } from '@/stores/user';
import { getDiscussionStyles } from '@/api/discussion';
import type { AgendaItem, AgentStatus, DiscussionStyle, DiscussionStyleFull, DiscussionStyleOverrides } from '@/types';

// Props for playback mode
// Archive state
const showArchiveDialog = ref(false)
const archiveProjects = ref<any[]>([])
const archiveStages = ref<any[]>([])
const selectedProject = ref('')
const selectedStage = ref('')
const archiving = ref(false)
const isHallDiscussion = computed(() => {
  const pid = discussion.value?.project_id
  return !pid || pid === '' || pid === 'lobby'
})

const isConceptDiscussion = computed(() => {
  return discussion.value?.moderator_role === 'creative_director'
})

async function openArchiveDialog() {
  showArchiveDialog.value = true
  try {
    const res = await fetch('/api/hall', { headers: { Authorization: `Bearer ${userStore.accessToken}` } })
    if (res.ok) {
      const data = await res.json()
      archiveProjects.value = data.items.filter((i: any) => i.type === 'project')
    }
  } catch {}
}

async function onProjectSelected() {
  if (!selectedProject.value) { archiveStages.value = []; return }
  try {
    const res = await fetch(`/api/projects/${selectedProject.value}/stages`, { headers: { Authorization: `Bearer ${userStore.accessToken}` } })
    if (res.ok) {
      const data = await res.json()
      archiveStages.value = (data.stages || []).filter((s: any) => s.status !== 'locked')
    }
  } catch {}
}

async function doArchive() {
  if (!selectedProject.value || !selectedStage.value || archiving.value) return
  archiving.value = true
  try {
    const res = await fetch(`/api/discussions/${discussionId.value || route.params.id}/archive`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${userStore.accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: selectedProject.value, stage_id: selectedStage.value })
    })
    if (res.ok) {
      showArchiveDialog.value = false
      alert('归档成功！')
      router.push(`/project/${selectedProject.value}`)
    } else {
      const err = await res.json()
      alert(err.detail || '归档失败')
    }
  } finally { archiving.value = false }
}

const userStore = useUserStore();

// Current LLM model info
const currentModel = ref<{ model: string; profile_name: string; profile_id: string; profiles: { id: string; name: string; model: string; is_active: boolean }[] }>({ model: '', profile_name: '', profile_id: '', profiles: [] })
const showModelMenu = ref(false)
const switchingModel = ref(false)

async function fetchCurrentModel() {
  try {
    const res = await fetch('/api/config/model', { headers: { Authorization: `Bearer ${userStore.accessToken}` } })
    if (res.ok) currentModel.value = await res.json()
  } catch {}
}

async function switchModel(profileId: string) {
  if (switchingModel.value || profileId === currentModel.value.profile_id) return
  switchingModel.value = true
  try {
    const res = await fetch(`/api/admin/config/llm/profiles/${profileId}/activate`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    if (res.ok) {
      await fetchCurrentModel()
      showModelMenu.value = false
    }
  } finally { switchingModel.value = false }
}

// Close model menu on outside click
function onDocClickModelMenu(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.model-badge-area')) showModelMenu.value = false
}

const props = defineProps<{
  mode?: 'live' | 'playback';
}>();

const route = useRoute();
const router = useRouter();
const agentsStore = useAgentsStore();
const discussionStore = useDiscussionStore();

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
  isProducerTurn,
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
  checkpoints,
  isWaitingDecision,
  respondToCheckpoint,
  sendProducerMessage,
} = useDiscussion();

const isRunning = computed(() => discussion.value?.status === 'running' || discussion.value?.status === 'queued' || discussion.value?.status === 'waiting_decision');
const isFinished = computed(() => discussion.value?.status === 'completed' || discussion.value?.status === 'stopped' || discussion.value?.status === 'failed');

// Show round table layout when discussion has messages (running, queued, completed, or failed)
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
const discussionStatus = computed<'pending' | 'queued' | 'running' | 'paused' | 'waiting_decision' | 'completed' | 'stopped' | 'failed'>(() => {
  const status = discussion.value?.status;
  if (status === 'queued') return 'queued';
  if (status === 'waiting_decision') return 'waiting_decision';
  if (status === 'running' && isPaused.value) return 'paused';
  if (status === 'running') return 'running';
  if (status === 'completed') return 'completed';
  if (status === 'stopped') return 'stopped';
  if (status === 'failed') return 'failed';
  return 'pending';
});

const statusLabel = computed(() => {
  switch (discussionStatus.value) {
    case 'queued': return '排队中';
    case 'running': return '进行中';
    case 'waiting_decision': return '等待决策';
    case 'paused': return '已暂停';
    case 'completed': return '已完成';
    case 'stopped': return '已停止';
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
  // Fetch current model info
  fetchCurrentModel();
  document.addEventListener('click', onDocClickModelMenu);
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
  const pId = route.params.projectId; router.push(pId ? `/project/${pId}` : '/');
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
    router.push({ name: 'discussion-by-id', params: { projectId: route.params.projectId || 'default', id: response.id } });
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


// Checkpoint handlers
async function handleRespondCheckpoint(checkpointId: string, optionId: string | null, freeInput: string) {
  const success = await respondToCheckpoint(checkpointId, optionId, freeInput);
  if (!success) {
    setError('提交决策失败，请重试');
  }
}

async function handleProducerSend(content: string) {
  // Optimistic update: show producer message in chat
  discussionStore.addMessage({
    id: `producer-${Date.now()}`,
    agentId: 'producer',
    agentRole: '制作人',
    content,
    timestamp: new Date().toISOString(),
  });
  // Send to backend via composable
  const ok = await sendProducerMessage(content);
  if (!ok) {
    setError('发送消息失败，请重试');
  }
}

// Scroll to checkpoint in chat (from right panel)
function handleScrollToCheckpoint(checkpointId: string) {
  const el = document.querySelector(`[data-checkpoint-id="${checkpointId}"]`);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// ---- Resizable split panel ----
const splitPercent = ref(65); // left panel percentage (right = ~35%)
const isDragging = ref(false);

const leftPanelStyle = computed(() => ({
  flex: `0 0 ${splitPercent.value}%`,
}));
const rightPanelStyle = computed(() => ({
  flex: `0 0 ${100 - splitPercent.value - 0.5}%`, // 0.5% for divider
}));

function startDrag(e: MouseEvent) {
  e.preventDefault();
  isDragging.value = true;
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag);
}

function onDrag(e: MouseEvent) {
  const main = document.querySelector('.discussion-main') as HTMLElement;
  if (!main) return;
  const rect = main.getBoundingClientRect();
  const x = e.clientX - rect.left;
  let pct = (x / rect.width) * 100;
  pct = Math.max(25, Math.min(75, pct)); // clamp 25%-75%
  splitPercent.value = Math.round(pct * 10) / 10;
}

function stopDrag() {
  isDragging.value = false;
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
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

// Navigate back - to project if came from project, otherwise to hall
const cameFromProject = computed(() => {
  return route.query.from === 'project' && route.query.projectId
})
const backLabel = computed(() => cameFromProject.value ? '返回项目' : '返回大厅')

function goBackToHome() {
  if (cameFromProject.value) {
    router.push(`/project/${route.query.projectId}`)
  } else {
    const pId = route.params.projectId as string
    router.push(pId ? `/project/${pId}` : '/')
  }
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

// Textarea 自适应高度
function autoResize(event: Event) {
  const el = event.target as HTMLTextAreaElement;
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// Handle style change in continue popup
function handleContinueStyleChange(styleId: string) {
  continueStyle.value = styleId;
  loadOverridesForStyle(styleId);
}

// Auto-resize prompt textareas when overrides change or editor is toggled
watch([showPromptEditor, continueOverrides], () => {
  nextTick(() => {
    document.querySelectorAll('.prompt-editor .prompt-field-input').forEach(el => {
      const ta = el as HTMLTextAreaElement;
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    });
  });
}, { deep: false });

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
  document.removeEventListener('click', onDocClickModelMenu);
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

    <!-- Header (with topic integrated) -->
    <Header :connection-status="connectionStatus">
      <template #topic>
        <span v-if="topicDisplay" class="topic-text" :title="topicDisplay">{{ topicDisplay }}</span>
        <span v-if="topicDisplay" class="status-badge" :class="`status-${discussionStatus}`">{{ statusLabel }}</span>
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
      </template>
      <template #extra>
        <!-- Model badge -->
        <div v-if="currentModel.model" class="model-badge-area" @click.stop="showModelMenu = !showModelMenu">
          <span class="model-badge" :title="currentModel.profile_name">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
            {{ currentModel.model }}
          </span>
          <Transition name="dropdown">
            <div v-if="showModelMenu && currentModel.profiles.length > 1 && userStore.isAdmin" class="model-dropdown">
              <div class="model-dropdown-title">切换模型</div>
              <button
                v-for="p in currentModel.profiles"
                :key="p.id"
                class="model-dropdown-item"
                :class="{ active: p.is_active }"
                :disabled="switchingModel"
                @click.stop="switchModel(p.id)"
              >
                <span class="model-item-name">{{ p.name }}</span>
                <span class="model-item-model">{{ p.model }}</span>
                <svg v-if="p.is_active" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
          </Transition>
        </div>
        <button
          v-if="isHallDiscussion && discussionStatus === 'completed'"
          class="archive-btn"
          @click="openArchiveDialog"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>
          归档</button>
        <button
          class="back-btn"
          @click="goBackToHome"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          <span>{{ backLabel }}</span>
        </button>
      </template>
    </Header>


    <!-- Producer turn banner (waiting for producer to speak) -->
    <div v-if="isProducerTurn && isRunning" class="auto-pause-banner producer-turn-banner">
      <div class="auto-pause-content">
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" style="color:#16a34a">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
        <span class="auto-pause-text" style="color:#15803d">{{ autoPauseMessage || '轮到您发言了，请在下方输入您的想法' }}</span>
      </div>
    </div>

    <!-- Auto-pause banner -->
    <div v-else-if="isPaused && isRunning" class="auto-pause-banner">
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
      <div class="left-panel" :style="leftPanelStyle">
        <!-- Compact Agent Bar -->
        <CompactAgentBar
          :agents="agentsStore.activeAgents"
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

        <!-- Queued hint when waiting for concurrency slot -->
        <div v-if="discussion?.status === 'queued'" class="waiting-placeholder">
          <div class="queued-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
          <p class="waiting-text">正在排队等待...</p>
          <p class="waiting-subtext">其他讨论进行中，稍后自动开始</p>
        </div>

        <!-- Waiting hint when discussion just started, no messages yet -->
        <div v-else-if="isRunning && displayMessages.length === 0" class="waiting-placeholder">
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
          :checkpoints="checkpoints"
          :is-loading="isLoading"
          class="message-feed"
          @respond-checkpoint="handleRespondCheckpoint"
        />
      </div>

      <!-- Resizable divider -->
      <div
        class="panel-divider"
        @mousedown="startDrag"
      >
        <div class="divider-handle" />
      </div>

      <!-- Right Panel: Tabs (Round Summaries / Design Docs) + Input -->
      <section class="right-panel" :style="rightPanelStyle">
        <RightPanel
          :round-summaries="roundSummaries"
          :discussion-id="discussion?.id ?? ''"
          :latest-doc-update="latestDocUpdate"
          :doc-plan="docPlan"
          :doc-contents="docContents"
          :current-section-id="currentSectionId"
          :checkpoints="checkpoints"
          @focus-section="handleFocusSection"
          @scroll-to-checkpoint="handleScrollToCheckpoint"
        />
        <!-- Producer input (replaces UserInputBox) -->
        <ProducerInput
          v-if="isRunning && discussion?.id"
          :discussion-id="discussion.id"
          :disabled="!isRunning"
          :is-waiting-decision="isWaitingDecision"
          @send="handleProducerSend"
        />
        <!-- Concept incubation completion banner -->
        <div v-if="isConceptDiscussion && isFinished && discussion?.project_id" class="concept-done-banner">
          <div class="concept-done-icon">✨</div>
          <div class="concept-done-content">
            <div class="concept-done-title">概念孵化完成！</div>
            <div class="concept-done-desc">创意点文档已生成，准备好进入下一阶段了吗？</div>
          </div>
          <div class="concept-done-actions">
            <button class="concept-btn concept-btn-secondary" @click="router.push(`/project/${discussion.project_id}`)">
              回到项目
            </button>
            <button class="concept-btn concept-btn-primary" @click="router.push(`/project/${discussion.project_id}?next=core-gdd`)">
              开始核心 GDD →
            </button>
          </div>
        </div>
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
                <label class="prompt-field-label">目标</label>
                <textarea
                  class="prompt-field-input"
                  :value="continueOverrides.goal || ''"
                  placeholder="主策划的目标..."
                  @input="continueOverrides!.goal = ($event.target as HTMLTextAreaElement).value; overridesModified = true; autoResize($event)"
                />
              </div>
              <div class="prompt-field">
                <label class="prompt-field-label">背景设定</label>
                <textarea
                  class="prompt-field-input"
                  :value="continueOverrides.backstory || ''"
                  placeholder="主策划的背景设定..."
                  @input="continueOverrides!.backstory = ($event.target as HTMLTextAreaElement).value; overridesModified = true; autoResize($event)"
                />
              </div>
              <div class="prompt-field">
                <label class="prompt-field-label">沟通风格</label>
                <textarea
                  class="prompt-field-input"
                  :value="continueOverrides.communication_style || ''"
                  placeholder="沟通和表达方式..."
                  @input="continueOverrides!.communication_style = ($event.target as HTMLTextAreaElement).value; overridesModified = true; autoResize($event)"
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

    <!-- Archive Dialog -->
    <Transition name="fade">
      <div v-if="showArchiveDialog" class="dialog-overlay" @click.self="showArchiveDialog = false">
        <div class="archive-dialog">
          <h3>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>
            归档讨论到项目
          </h3>
          <div class="archive-field">
            <label>选择项目</label>
            <select v-model="selectedProject" @change="onProjectSelected" class="archive-select">
              <option value="">请选择项目...</option>
              <option v-for="p in archiveProjects" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <div class="archive-field" v-if="archiveStages.length">
            <label>选择阶段</label>
            <select v-model="selectedStage" class="archive-select">
              <option value="">请选择阶段...</option>
              <option v-for="s in archiveStages" :key="s.id" :value="s.id">{{ s.name }} ({{ s.status === 'completed' ? '已完成' : '进行中' }})</option>
            </select>
          </div>
          <div class="archive-actions">
            <button class="btn btn-secondary" @click="showArchiveDialog = false">取消</button>
            <button class="btn btn-primary" @click="doArchive" :disabled="!selectedProject || !selectedStage || archiving">{{ archiving ? '归档中...' : '确认归档' }}</button>
          </div>
        </div>
      </div>
    </Transition>
</template>

<style scoped>
/* ===== Style C — Design Token Aligned ===== */

/* Shared base: 运行中 (SNYpS) + 已完成 (7uLZE) */
.discussion-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #FFFBF5;
}

.topic-text {
  font-size: 16px;
  font-weight: 700;
  color: #18181B;
  font-family: Inter, sans-serif;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  background: none;
  border: none;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.15s, color 0.15s;
}

.back-btn:hover {
  background: #F0EDE8;
  color: #18181B;
}

/* Status badges — token-aligned */
.status-badge {
  padding: 4px 10px;
  border-radius: 100px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
  font-family: Inter, sans-serif;
}

.status-queued    { background: #FEF3C7; color: #92400E; }
.status-running   { background: #F0FDF4; color: #16A34A; }
.status-active    { background: #F0FDF4; color: #16A34A; }
.status-completed { background: #D1FAE5; color: #16A34A; }
.status-paused    { background: #FEF3C7; color: #92400E; }
.status-waiting_decision { background: #FEF3C7; color: #92400E; }
.status-waiting   { background: #FEF3C7; color: #92400E; }
.status-stopped   { background: #FEF3C7; color: #92400E; }
.status-failed    { background: rgba(239, 68, 68, 0.1); color: #DC2626; }
.status-pending   { background: #F4F4F5; color: #71717A; }
.status-archived  { background: #F4F4F5; color: #71717A; }

.action-btn-sm {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: #FFFBF5;
  border: 1px solid #F0EBE4;
  color: #71717A;
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn-sm:hover {
  background: #EDE9FE;
  color: #7C3AED;
  border-color: #7C3AED;
}

.action-btn-sm.is-paused {
  background: #FEF3C7;
  border-color: #D97706;
  color: #D97706;
}

/* Auto-pause banner — token: #FEF3C7, 44px, padding 0 20px */
.auto-pause-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #FEF3C7;
  height: 44px;
  flex-shrink: 0;
}

.auto-pause-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.auto-pause-text {
  font-size: 13px;
  color: #92400E;
  font-weight: 500;
  font-family: Inter, sans-serif;
}

.auto-pause-resume-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  background: #7C3AED;
  color: #FFFFFF;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: background 0.2s;
}

.auto-pause-resume-btn:hover {
  background: #6D28D9;
}

/* Producer turn banner — green highlight */
.producer-turn-banner {
  background: #F0FDF4;
  border-bottom: 1px solid #86EFAC;
}

/* Main content - Two Column Layout */
.discussion-main {
  flex: 1;
  display: flex;
  gap: 0;
  padding: 12px;
  overflow: hidden;
}

.left-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

/* Resizable divider — token: surface-drag-handle #D4D4D8, 6px wide */
.panel-divider {
  flex: 0 0 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: col-resize;
  position: relative;
  z-index: 10;
}

.panel-divider:hover .divider-handle,
.panel-divider:active .divider-handle {
  background: #7C3AED;
  opacity: 0.6;
}

.divider-handle {
  width: 3px;
  height: 40px;
  border-radius: 2px;
  background: #D4D4D8;
  transition: background 0.15s, opacity 0.15s, height 0.15s;
}

.panel-divider:hover .divider-handle {
  height: 56px;
}

.panel-divider:active .divider-handle {
  opacity: 0.9;
  height: 56px;
}

/* Message feed — white card, shadow-color-bar */
.message-feed {
  flex: 1;
  min-height: 0;
  border: none;
  border-radius: 12px;
  background: #FFFFFF;
  box-shadow: 0 1px 3px #0000000A;
}

.filter-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: #F0EDE8;
  border-radius: 8px;
  font-size: 12px;
  color: #52525B;
  flex-shrink: 0;
}

.clear-filter-btn {
  font-size: 16px;
  line-height: 1;
  color: #71717A;
  cursor: pointer;
  padding: 0 4px;
}

.clear-filter-btn:hover {
  color: #18181B;
}

/* Right panel — white card, border #F0EBE4 */
.right-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  background: #FFFFFF;
  border-radius: 12px;
  box-shadow: 0 1px 3px #0000000A;
  border: 1px solid #F0EBE4;
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
  background: #FEF2F2;
  border: 1px solid #FECACA;
  border-radius: 12px;
  padding: 16px 24px;
  max-width: 480px;
  margin: 16px;
  pointer-events: auto;
}

/* Footer */
.discussion-footer {
  padding: 12px 16px;
  background: #FFFFFF;
  border-top: 1px solid #F0EBE4;
}

/* Concept incubation completion banner */
.concept-done-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%);
  border-top: 2px solid #7C3AED;
  flex-shrink: 0;
}
.concept-done-icon {
  font-size: 24px;
  flex-shrink: 0;
}
.concept-done-content {
  flex: 1;
  min-width: 0;
}
.concept-done-title {
  font-size: 14px;
  font-weight: 700;
  color: #5B21B6;
  margin-bottom: 2px;
}
.concept-done-desc {
  font-size: 12px;
  color: #6D28D9;
}
.concept-done-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.concept-btn {
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  white-space: nowrap;
  transition: opacity 0.15s;
}
.concept-btn:hover { opacity: 0.85; }
.concept-btn-secondary {
  background: #EDE9FE;
  color: #5B21B6;
}
.concept-btn-primary {
  background: #7C3AED;
  color: #FFFFFF;
}

/* Continue discussion area */
.continue-area {
  border-top: 1px solid #F0EBE4;
  background: #FFFFFF;
  flex-shrink: 0;
}

/* Continue trigger — primary button token */
.continue-trigger-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #FFFFFF;
  background: #7C3AED;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.continue-trigger-btn:hover {
  background: #6D28D9;
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

/* Style chips — pill shape, brand colors */
.style-chip {
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: #374151;
  background: #FFFBF5;
  border: 1px solid #F0EBE4;
  border-radius: 100px;
  cursor: pointer;
  transition: all 0.15s;
}

.style-chip:hover {
  border-color: #7C3AED;
  background: #EDE9FE;
  color: #7C3AED;
}

.style-chip-active {
  color: #FFFFFF;
  background: #7C3AED;
  border-color: #7C3AED;
}

.style-chip-active:hover {
  background: #6D28D9;
  border-color: #6D28D9;
}

.style-pill {
  border-radius: 100px;
  transition: all 0.15s;
}

.continue-popup-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.continue-label {
  font-size: 13px;
  color: #6B7280;
  white-space: nowrap;
  flex-shrink: 0;
}

.rounds-stepper {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
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
  color: #374151;
  background: #FFFBF5;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}

.stepper-btn:hover {
  background: #F0EDE8;
  color: #18181B;
}

.rounds-input {
  width: 40px;
  height: 28px;
  text-align: center;
  font-size: 14px;
  font-weight: 500;
  color: #18181B;
  background: #FFFFFF;
  border: none;
  border-left: 1px solid #D1D5DB;
  border-right: 1px solid #D1D5DB;
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
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  font-size: 13px;
  color: #18181B;
  background: #FFFFFF;
  transition: border-color 0.2s;
}

.continue-text-input:focus {
  outline: none;
  border-color: #7C3AED;
  box-shadow: 0 0 0 3px #7C3AED20;
}

.continue-text-input::placeholder {
  color: #9CA3AF;
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

/* Outline button token */
.continue-cancel-btn {
  padding: 6px 14px;
  font-size: 13px;
  color: #374151;
  background: transparent;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.continue-cancel-btn:hover:not(:disabled) {
  background: #F0EDE8;
}

/* Primary button token */
.continue-confirm-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #FFFFFF;
  background: #7C3AED;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.continue-confirm-btn:hover:not(:disabled) {
  background: #6D28D9;
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
  color: #6B7280;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 0;
  transition: color 0.15s;
  align-self: flex-start;
  position: relative;
}

.prompt-editor-toggle:hover {
  color: #7C3AED;
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
  background: #7C3AED;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Prompt editor panel */
.prompt-editor {
  border: 1px solid #F0EBE4;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #FFFBF5;
}

.prompt-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.prompt-editor-hint {
  font-size: 11px;
  color: #9CA3AF;
}

.prompt-reset-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #6B7280;
  padding: 2px 7px;
  border: 1px solid #F0EBE4;
  border-radius: 4px;
  background: #FFFFFF;
  cursor: pointer;
  transition: all 0.15s;
}

.prompt-reset-btn:hover {
  color: #7C3AED;
  border-color: #7C3AED;
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
  font-weight: 600;
  color: #52525B;
  letter-spacing: 0.3px;
}

.prompt-field-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  font-size: 13px;
  color: #18181B;
  background: #FFFFFF;
  resize: none;
  overflow: hidden;
  font-family: inherit;
  line-height: 1.8;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
}

.prompt-field-input:hover {
  border-color: #F0EBE4;
}

.prompt-field-input:focus {
  outline: none;
  border-color: #7C3AED;
  background: #FFFFFF;
  box-shadow: 0 0 0 3px #7C3AED20;
}

.prompt-field-input::placeholder {
  color: #9CA3AF;
}

.prompt-editor-empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: #9CA3AF;
  border: 1px dashed #F0EBE4;
  border-radius: 8px;
}

/* Waiting placeholder — white card */
.waiting-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  min-height: 0;
  border: none;
  border-radius: 12px;
  background: #FFFFFF;
  box-shadow: 0 1px 3px #0000000A;
}

.thinking-dots {
  display: flex;
  gap: 6px;
}

.thinking-dots .dot {
  width: 8px;
  height: 8px;
  background: #7C3AED;
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
  color: #374151;
  font-family: Inter, sans-serif;
}

.waiting-subtext {
  font-size: 13px;
  color: #9CA3AF;
}

.queued-icon {
  width: 36px;
  height: 36px;
  color: #7C3AED;
  opacity: 0.6;
  animation: queued-pulse 2s ease-in-out infinite;
}

@keyframes queued-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}

/* Archive controls */
.archive-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: #D1FAE5;
  color: #16A34A;
  border: 1px solid #86EFAC;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.archive-btn:hover { background: #DCFCE7; }

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: #00000066;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

/* Archive dialog — standard modal token */
.archive-dialog {
  background: #FFFFFF;
  border-radius: 16px;
  padding: 24px;
  width: 380px;
  box-shadow: 0 8px 32px -4px #00000020;
}

.archive-dialog h3 { margin: 0 0 16px; font-size: 16px; color: #18181B; }
.archive-field { margin-bottom: 12px; }
.archive-field label { display: block; font-size: 13px; color: #6B7280; margin-bottom: 4px; }

.archive-select {
  width: 100%;
  padding: 8px;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  font-size: 14px;
}

.archive-select:focus { outline: none; border-color: #7C3AED; }

.archive-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.archive-actions .btn { padding: 6px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; font-weight: 500; }
.archive-actions .btn-primary { background: #7C3AED; color: #FFFFFF; }
.archive-actions .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.archive-actions .btn-secondary { background: #F0EDE8; color: #374151; border: 1px solid #D1D5DB; }

/* Responsive layout */
@media (max-width: 1024px) {
  .discussion-main {
    flex-direction: column;
  }

  .left-panel,
  .right-panel {
    flex: 1 1 auto !important;
  }

  .panel-divider {
    display: none;
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
    padding: 4px;
  }

  .right-panel {
    max-height: 200px;
  }

  .discussion-footer {
    padding: 8px 12px;
    padding-bottom: calc(8px + env(safe-area-inset-bottom));
  }

  .continue-panel {
    padding: 10px;
    max-height: 50vh;
  }

  .error-card {
    max-width: calc(100vw - 32px);
    margin: 12px;
    padding: 12px 16px;
  }

  .archive-dialog {
    width: calc(100vw - 32px);
    padding: 20px;
  }

  .auto-pause-banner {
    flex-direction: column;
    gap: 8px;
    align-items: flex-start;
    height: auto;
    padding: 8px 12px;
  }
}

/* Model badge */
.model-badge-area {
  position: relative;
  cursor: pointer;
}
.model-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: var(--bg-secondary, #f3f4f6);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary, #6b7280);
  transition: background 0.15s;
  white-space: nowrap;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.model-badge:hover {
  background: var(--bg-tertiary, #e5e7eb);
}
.model-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  background: white;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  min-width: 200px;
  z-index: 200;
  overflow: hidden;
}
.model-dropdown-title {
  padding: 8px 12px 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-weak, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.model-dropdown-item {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-primary, #374151);
  transition: background 0.15s;
}
.model-dropdown-item:hover { background: #f9fafb; }
.model-dropdown-item.active { background: #eff6ff; color: #2563eb; }
.model-dropdown-item:disabled { opacity: 0.5; cursor: not-allowed; }
.model-item-name { font-weight: 500; flex: 1; }
.model-item-model { font-size: 10px; color: var(--text-weak, #9ca3af); max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
