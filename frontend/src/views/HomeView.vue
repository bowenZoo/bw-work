<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick, toRaw } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, Search, X, Paperclip, MessageSquare, FileText, Eye, EyeOff, RotateCcw, LogOut, ChevronDown, User } from 'lucide-vue-next';
import { getDiscussionHistory, getDiscussionStyles } from '@/api/discussion';
import { useLobby } from '@/composables/useLobby';
import { AgentConfigEditor } from '@/components/discussion';
import SidePanel from '@/components/layout/SidePanel.vue';
import LoginModal from '@/components/auth/LoginModal.vue';
import UserManagePanel from '@/components/admin/UserManagePanel.vue';
import ProfilePanel from '@/components/settings/ProfilePanel.vue';
import SystemSettingsPanel from '@/components/settings/SystemSettingsPanel.vue';
import AuditLogPanel from '@/components/settings/AuditLogPanel.vue';
import LetterAvatar from '@/components/common/LetterAvatar.vue';
import { useUserStore } from '@/stores/user';
import type { DiscussionSummary, AgentConfig, DiscussionStyle, DiscussionStyleFull, DiscussionStyleOverrides } from '@/types';

const router = useRouter();
const props = defineProps<{ projectId?: string }>();
const userStore = useUserStore();
const currentProject = ref<any>(null);

// Side panel
const activeSection = ref('my-discussions');
const showLoginModal = ref(false);
const showResumeDialog = ref(false);
const resumeTarget = ref<CardItem | null>(null);
const resumeFollowUp = ref('');
const resumeRounds = ref(10);
const resumeMode = ref<'extend' | 'continue'>('extend');
const showUserMenu = ref(false);


// Lobby state (active discussions via WebSocket)
const {
  activeDiscussions,
  createDiscussion: lobbyCreateDiscussion,
} = useLobby(computed(() => props.projectId));

// Workspace list (history)
const workspaces = ref<DiscussionSummary[]>([]);
const isLoadingList = ref(false);
const hasMore = ref(true);
const page = ref(1);
const listError = ref<string | null>(null);
const PAGE_SIZE = 20;

// Search
const searchQuery = ref('');

// Unified card item
interface CardItem {
  id: string;
  topic: string;
  status: string | null;
  message_count: number;
  doc_count: number;
  rounds: number;
  created_at: string;
  isLive: boolean;
  owner_id?: number | null;
  owner_name?: string | null;
  owner_avatar?: string | null;
}

// Merge active discussions + history into unified list
const allCards = computed<CardItem[]>(() => {
  const activeIds = new Set(activeDiscussions.value.map(d => d.id));
  const cards: CardItem[] = [];

  // Add active discussions first (they have live status)
  // Filter by project if in workspace context
  const activeList = props.projectId
    ? activeDiscussions.value.filter((d: any) => d.project_id === props.projectId)
    : activeDiscussions.value;
  for (const d of activeList) {
    cards.push({
      id: d.id,
      topic: d.topic,
      status: d.status,
      message_count: 0,
      doc_count: 0,
      rounds: d.rounds,
      created_at: d.created_at,
      isLive: true,
      owner_name: (d as any).owner_name || null,
      owner_avatar: (d as any).owner_avatar || null,
    });
  }

  // Add history items that aren't already in active list
  for (const w of workspaces.value) {
    if (!activeIds.has(w.id)) {
      cards.push({
        id: w.id,
        topic: w.topic,
        status: w.status,
        message_count: w.message_count,
        doc_count: w.doc_count,
        rounds: 0,
        created_at: w.created_at,
        isLive: false,
        owner_name: (w as any).owner_name || null,
        owner_avatar: (w as any).owner_avatar || null,
      });
    }
  }

  return cards;
});

// Filter by search
const filteredCards = computed(() => {
  let cards = allCards.value;
  
  // Search filtering
  const q = searchQuery.value.trim().toLowerCase();
  if (q) {
    cards = cards.filter(c => c.topic?.toLowerCase().includes(q));
  }
  return cards;
});

// Date grouping
interface DateGroup {
  label: string;
  items: CardItem[];
}

const groupedCards = computed<DateGroup[]>(() => {
  const items = filteredCards.value;
  if (items.length === 0) return [];

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86400000;
  const weekStart = todayStart - 6 * 86400000;

  const today: CardItem[] = [];
  const yesterday: CardItem[] = [];
  const thisWeek: CardItem[] = [];
  const earlier: CardItem[] = [];

  for (const item of items) {
    const ts = new Date(item.created_at).getTime();
    if (ts >= todayStart) {
      today.push(item);
    } else if (ts >= yesterdayStart) {
      yesterday.push(item);
    } else if (ts >= weekStart) {
      thisWeek.push(item);
    } else {
      earlier.push(item);
    }
  }

  const groups: DateGroup[] = [];
  if (today.length) groups.push({ label: '今天', items: today });
  if (yesterday.length) groups.push({ label: '昨天', items: yesterday });
  if (thisWeek.length) groups.push({ label: '本周', items: thisWeek });
  if (earlier.length) groups.push({ label: '更早', items: earlier });
  return groups;
});

const isEmpty = computed(
  () => !isLoadingList.value && allCards.value.length === 0
);

// New discussion dialog
const showNewDialog = ref(false);
const topicInput = ref('');
const briefingInput = ref('');
const autoPauseInterval = ref(5);
const attachmentFile = ref<File | null>(null);
const attachmentContent = ref('');
const fileInputRef = ref<HTMLInputElement | null>(null);
const isCreating = ref(false);

// Agent config
const selectedAgents = ref<string[]>([]);
const agentConfigs = ref<Record<string, Partial<AgentConfig>>>({});

// Discussion style
const discussionStyles = ref<DiscussionStyle[]>([]);
const discussionStylesFull = ref<DiscussionStyleFull[]>([]);
const defaultStyleId = ref('socratic');
const selectedStyle = ref('socratic');

// Prompt overrides (right panel)
const customOverrides = ref<DiscussionStyleOverrides | null>(null);
const newFocusArea = ref('');

// Password
const password = ref('');
const usePassword = ref(false);
const showPassword = ref(false);

// Error state
const createError = ref('');

// Load workspace list
async function loadWorkspaces(reset = false) {
  if (isLoadingList.value) return;
  if (!reset && !hasMore.value) return;

  isLoadingList.value = true;
  listError.value = null;

  try {
    if (reset) {
      page.value = 1;
      workspaces.value = [];
    }
    const response = await getDiscussionHistory(page.value, PAGE_SIZE, false, props.projectId);
    workspaces.value = [...workspaces.value, ...response.items];
    hasMore.value = response.hasMore;
    page.value++;
  } catch (e) {
    listError.value = e instanceof Error ? e.message : '加载失败';
  } finally {
    isLoadingList.value = false;
  }
}

// Infinite scroll
function handleScroll(event: Event) {
  const target = event.target as HTMLElement;
  const scrollBottom = target.scrollHeight - target.scrollTop - target.clientHeight;
  if (scrollBottom < 100 && hasMore.value && !isLoadingList.value) {
    loadWorkspaces();
  }
}

// Navigation
function openResumeDialog(card: CardItem) {
  resumeTarget.value = card;
  resumeFollowUp.value = '';
  resumeRounds.value = 10;
  resumeMode.value = 'extend';
  showResumeDialog.value = true;
}

async function doResume() {
  if (!resumeTarget.value) return;
  const id = resumeTarget.value.id;
  
  try {
    if (resumeMode.value === 'extend') {
      // Extend: resume in-place
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      const raw = localStorage.getItem('bw_user_tokens');
      if (raw) {
        const { access_token } = JSON.parse(raw);
        headers['Authorization'] = `Bearer ${access_token}`;
      }
      const res = await fetch(`/api/discussions/${id}/extend`, {
        method: 'POST', headers,
        body: JSON.stringify({
          follow_up: resumeFollowUp.value,
          additional_rounds: resumeRounds.value,
        })
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Extend failed');
      showResumeDialog.value = false;
      router.push({ name: 'discussion-by-id', params: { projectId: props.projectId || 'default', id } });
    } else {
      // Continue: create new discussion from this one
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      const raw = localStorage.getItem('bw_user_tokens');
      if (raw) {
        const { access_token } = JSON.parse(raw);
        headers['Authorization'] = `Bearer ${access_token}`;
      }
      const res = await fetch(`/api/discussions/${id}/continue`, {
        method: 'POST', headers,
        body: JSON.stringify({
          follow_up: resumeFollowUp.value,
          rounds: Math.min(resumeRounds.value, 10),
        })
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Continue failed');
      const data = await res.json();
      showResumeDialog.value = false;
      router.push({ name: 'discussion-by-id', params: { projectId: props.projectId || 'default', id: data.new_discussion_id } });
    }
  } catch (e: any) {
    alert(e.message);
  }
}

function viewCard(card: CardItem) {
  const routeName = props.projectId ? 'discussion-by-id' : 'discussion-legacy';
  const params: any = { id: card.id };
  if (props.projectId) params.projectId = props.projectId;
  router.push({ name: routeName, params });
}

// New discussion
function openNewDialog() {
  showNewDialog.value = true;
  topicInput.value = '';
  briefingInput.value = '';
  autoPauseInterval.value = 5;
  attachmentFile.value = null;
  attachmentContent.value = '';
  selectedAgents.value = [];
  agentConfigs.value = {};
  selectedStyle.value = defaultStyleId.value;
  password.value = '';
usePassword.value = false;
  showPassword.value = false;
  newFocusArea.value = '';
  onStyleSelect(defaultStyleId.value);
}

function closeNewDialog() {
  showNewDialog.value = false;
}

async function createDiscussion() {
  const topic = topicInput.value.trim();
  if (!topic) return;

  isCreating.value = true;
  createError.value = '';
  try {
    const attachment = attachmentContent.value
      ? { filename: attachmentFile.value?.name || 'attachment.md', content: attachmentContent.value }
      : null;

    const cleanConfigs: Record<string, Partial<AgentConfig>> = {};
    for (const [role, config] of Object.entries(agentConfigs.value)) {
      const nonEmpty: Partial<AgentConfig> = {};
      for (const [key, val] of Object.entries(config)) {
        if (val !== undefined && val !== '' && !(Array.isArray(val) && val.length === 0)) {
          (nonEmpty as any)[key] = val;
        }
      }
      if (Object.keys(nonEmpty).length > 0) {
        cleanConfigs[role] = nonEmpty;
      }
    }

    // Merge custom prompt overrides into agent_configs for lead_planner
    const agentConfigsFinal = { ...cleanConfigs };
    if (customOverrides.value) {
      const defaultStyle = discussionStylesFull.value.find(s => s.id === selectedStyle.value);
      const overridesChanged = defaultStyle && JSON.stringify(customOverrides.value) !== JSON.stringify(defaultStyle.overrides);
      if (overridesChanged) {
        agentConfigsFinal['lead_planner'] = {
          ...(agentConfigsFinal['lead_planner'] || {}),
          ...customOverrides.value,
        };
      }
    }

    const response = await lobbyCreateDiscussion(
      topic,
      10,
      attachment,
      autoPauseInterval.value,
      selectedAgents.value.length > 0 ? selectedAgents.value : undefined,
      Object.keys(agentConfigsFinal).length > 0 ? agentConfigsFinal : undefined,
      selectedStyle.value || undefined,
      usePassword.value ? (password.value || undefined) : undefined,
      briefingInput.value.trim() || undefined,
    );

    showNewDialog.value = false;
    router.push({ name: 'discussion-by-id', params: { projectId: props.projectId || 'default', id: response.id } });
  } catch (e) {
    console.error('Failed to create discussion:', e);
    createError.value = '创建讨论失败，请重试';
  } finally {
    isCreating.value = false;
  }
}

function handleNewDialogKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !(event.target as HTMLElement)?.closest('textarea')) {
    event.preventDefault();
    createDiscussion();
  }
  if (event.key === 'Escape') {
    closeNewDialog();
  }
}

// Style selection & prompt overrides
function onStyleSelect(styleId: string) {
  selectedStyle.value = styleId;
  const style = discussionStylesFull.value.find(s => s.id === styleId);
  if (style) {
    customOverrides.value = structuredClone(toRaw(style.overrides));
  }
}

function resetToPreset() {
  const style = discussionStylesFull.value.find(s => s.id === selectedStyle.value);
  if (style) {
    customOverrides.value = structuredClone(toRaw(style.overrides));
  }
}

// Textarea 自适应高度
function autoResize(event: Event) {
  const el = event.target as HTMLTextAreaElement;
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// customOverrides 变化时（如切换风格），重新计算所有 textarea 高度
watch(customOverrides, () => {
  nextTick(() => {
    document.querySelectorAll('.prompt-field-input').forEach(el => {
      const ta = el as HTMLTextAreaElement;
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    });
  });
}, { deep: false });

// 修复：styles 异步加载完成后，确保 customOverrides 被正确设置
watch(discussionStylesFull, (styles) => {
  if (styles.length > 0 && customOverrides.value === null && selectedStyle.value) {
    onStyleSelect(selectedStyle.value);
  }
});

function removeFocusArea(index: number) {
  if (customOverrides.value) {
    customOverrides.value.focus_areas.splice(index, 1);
  }
}

function addFocusArea() {
  const text = newFocusArea.value.trim();
  if (text && customOverrides.value && !customOverrides.value.focus_areas.includes(text)) {
    customOverrides.value.focus_areas.push(text);
    newFocusArea.value = '';
  }
}

function handleFocusAreaKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    event.preventDefault();
    event.stopPropagation();
    addFocusArea();
  }
}

// Attachment
function triggerFileInput() {
  fileInputRef.value?.click();
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) {
    if (!file.name.endsWith('.md')) {
      alert('请上传 .md 格式的文件');
      return;
    }
    attachmentFile.value = file;
    try {
      attachmentContent.value = await file.text();
    } catch {
      alert('读取文件失败');
      removeAttachment();
    }
  }
}

function removeAttachment() {
  attachmentFile.value = null;
  attachmentContent.value = '';
  if (fileInputRef.value) fileInputRef.value.value = '';
}

// Helpers
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffHours < 24) return `${diffHours} 小时前`;
  if (diffDays === 1) return '昨天';
  if (diffDays < 7) return `${diffDays} 天前`;
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

function getStatusLabel(status: string | null): string {
  switch (status) {
    case 'queued': return '排队中';
    case 'running': return '进行中';
    case 'waiting_decision': return '等待决策';
    case 'paused': return '已暂停';
    case 'stopped': return '已停止';
    case 'failed': return '已中断';
    default: return '已完成';
  }
}

function getStatusClass(status: string | null): string {
  switch (status) {
    case 'queued': return 'badge-queued';
    case 'running': return 'badge-running';
    case 'waiting_decision': return 'badge-paused';
    case 'paused': return 'badge-paused';
    case 'stopped': return 'badge-stopped';
    case 'failed': return 'badge-failed';
    default: return 'badge-completed';
  }
}

function isActiveStatus(status: string | null): boolean {
  return status === 'running' || status === 'queued' || status === 'paused' || status === 'waiting_decision';
}

// Load discussion styles
async function loadStyles() {
  try {
    const data = await getDiscussionStyles();
    discussionStylesFull.value = data.styles;
    discussionStyles.value = data.styles; // 保持兼容
    defaultStyleId.value = data.default;
    selectedStyle.value = data.default;
    onStyleSelect(data.default);
  } catch {
    // Fallback defaults (no overrides available) — use independent arrays to avoid shared references
    discussionStylesFull.value = [
      { id: 'socratic', name: '苏格拉底式', description: '不断追问「为什么」，逼迫每个决策回到第一性原理', overrides: { goal: '', backstory: '', communication_style: '', focus_areas: [] } },
      { id: 'directive', name: '主策划主导制', description: '主策划提出框架，团队挑战补充，主策划有否决权', overrides: { goal: '', backstory: '', communication_style: '', focus_areas: [] } },
      { id: 'debate', name: '辩论制', description: '各策划独立提案，互相质疑辩论，主策划裁决', overrides: { goal: '', backstory: '', communication_style: '', focus_areas: [] } },
    ];
    discussionStyles.value = [
      { id: 'socratic', name: '苏格拉底式', description: '不断追问「为什么」，逼迫每个决策回到第一性原理' },
      { id: 'directive', name: '主策划主导制', description: '主策划提出框架，团队挑战补充，主策划有否决权' },
      { id: 'debate', name: '辩论制', description: '各策划独立提案，互相质疑辩论，主策划裁决' },
    ];
  }
}

// Lifecycle
async function loadProject() {
  if (!props.projectId) return;
  try {
    const raw = localStorage.getItem('bw_user_tokens');
    const headers: Record<string, string> = {};
    if (raw) { try { headers['Authorization'] = `Bearer ${JSON.parse(raw).access_token}`; } catch {} }
    const res = await fetch(`/api/projects/${props.projectId}`, { headers });
    if (res.ok) currentProject.value = await res.json();
  } catch {}
}

onMounted(() => {
  loadProject();
  loadWorkspaces(true);
  loadStyles();
});
</script>

<template>
  <div class="home-layout">
    <SidePanel :active-section="activeSection" @select="activeSection = $event" />
    <div class="home-page" @scroll="handleScroll">
    <!-- Header -->
    <header class="home-header">
      <div class="header-left">
        <div class="logo">
          <span class="logo-text">BW</span>
        </div>
        <div>
          <div class="title-row" :class="{clickable: !!projectId}" @click="projectId && $router.push('/')">
            <span v-if="projectId" class="back-arrow">←</span>
            <h1 class="app-title" :title="projectId ? '返回项目列表' : ''">{{ currentProject?.name || "BW-Work" }}</h1>
          </div>
          <p class="app-subtitle">AI 策划工作空间</p>
        </div>
      </div>
      <!-- User area -->
      <div class="header-actions">
        <template v-if="userStore.isAuthenticated">
          <div class="user-area" @click.stop="showUserMenu = !showUserMenu">
            <LetterAvatar :name="userStore.user?.display_name || userStore.user?.username || '?'" :size="24" />
            <span class="user-name">{{ userStore.user?.display_name || userStore.user?.username }}</span>
            <span v-if="userStore.isAdmin" class="role-tag">管理员</span>
            <ChevronDown :size="14" />
            <div v-if="showUserMenu" class="user-dropdown">
              <button class="dropdown-item" @click="userStore.logout(); showUserMenu = false">
                <LogOut :size="14" />
                <span>退出登录</span>
              </button>
            </div>
          </div>
        </template>
        <template v-else>
          <button class="login-btn" @click="showLoginModal = true">登录</button>
        </template>
        <button class="new-btn" @click="openNewDialog">
          <Plus class="icon-sm" />
          <span>新建讨论</span>
        </button>
      </div>
    </header>

    <!-- Content -->
    <main class="home-content">
      <!-- Section: User Management (admin only) -->
      <template v-if="activeSection === 'user-manage' && userStore.isAdmin">
        <UserManagePanel />
      </template>

      <!-- Section: Discussions (default) -->
      <template v-else-if="activeSection === 'my-discussions' || activeSection === 'all-discussions'">


      <!-- Search bar -->
      <div v-if="allCards.length > 0 || searchQuery" class="search-bar">
        <Search class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索讨论..."
          class="search-input"
        />
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">
          <X class="icon-sm" />
        </button>
      </div>

      <!-- Card grid with date groups -->
      <section v-if="groupedCards.length > 0" class="cards-section">
        <div v-for="group in groupedCards" :key="group.label" class="date-group">
          <h4 class="date-label">{{ group.label }}</h4>
          <div class="card-grid">
            <div
              v-for="card in group.items"
              :key="card.id"
              class="card"
              :class="{ 'card-active': isActiveStatus(card.status) }"
              @click="viewCard(card)"
            >
              <!-- Row 1: status + topic + time -->
              <div class="card-row1">
                <span v-if="isActiveStatus(card.status)" class="pulse-dot" :class="{ 'queued-dot': card.status === 'queued' }" />
                <span class="card-badge" :class="getStatusClass(card.status)">{{ getStatusLabel(card.status) }}</span>
                <h3 class="card-topic">{{ card.topic }}</h3>
                <span class="card-time">{{ formatDate(card.created_at) }}</span>
              </div>
              <!-- Row 2: avatar + name + metrics + action -->
              <div class="card-row2">
                <LetterAvatar v-if="card.owner_name" :name="card.owner_name" :size="18" />
                <span v-if="card.owner_name" class="card-owner-text">{{ card.owner_name }}</span>
                <span v-if="card.isLive && card.rounds > 0" class="metric">第{{ card.rounds }}轮</span>
                <span v-if="card.message_count > 0" class="metric"><MessageSquare :size="12" /> {{ card.message_count }}</span>
                <span v-if="card.doc_count > 0" class="metric"><FileText :size="12" /> {{ card.doc_count }}</span>
                <button v-if="card.status === 'completed' || card.status === 'error' || card.status === 'failed' || card.status === 'stopped'" class="resume-btn" @click.stop="openResumeDialog(card)"><RotateCcw :size="12" /> 继续</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Empty state -->
      <section v-if="isEmpty" class="empty-state">
        <MessageSquare class="icon-xl text-weak" />
        <p class="empty-title">还没有讨论</p>
        <p class="empty-desc">发起一个新的策划讨论开始吧</p>
        <button class="btn-primary" @click="openNewDialog">
          <Plus class="icon-sm" />
          发起讨论
        </button>
      </section>

      <!-- Empty search result -->
      <section v-if="filteredCards.length === 0 && searchQuery && !isLoadingList" class="empty-state">
        <p class="empty-title">没有匹配的讨论</p>
        <p class="empty-desc">试试其他关键词</p>
      </section>

      <!-- Loading -->
      <div v-if="isLoadingList" class="loading-indicator">
        <svg class="spin-icon" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <span>加载中...</span>
      </div>

      <!-- Error -->
      <div v-if="listError" class="list-error">
        <p>{{ listError }}</p>
        <button @click="loadWorkspaces(true)">重试</button>
      </div>

      <!-- Load more hint -->
      <div v-if="hasMore && !isLoadingList && filteredCards.length > 0" class="load-more-hint">
        向下滚动加载更多
      </div>
      </template>

      <!-- Section: Other placeholders -->
      <template v-else-if="activeSection === 'system-settings'">
        <div class="section-placeholder">
          <p>系统设置功能开发中...</p>
        </div>
      </template>
      <template v-else-if="activeSection === 'audit-logs'">
        <div class="section-placeholder">
          <p>审计日志功能开发中...</p>
        </div>
      </template>
      <template v-else-if="activeSection === 'profile'">
        <div class="section-placeholder">
          <p>个人中心功能开发中...</p>
        </div>
      </template>
    </main>

    <!-- New Discussion Panel (large, two-column) -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showNewDialog" class="create-panel-overlay" @click.self="closeNewDialog">
          <div class="create-panel" tabindex="-1" @keydown="handleNewDialogKeydown">
            <!-- Panel Header -->
            <div class="panel-header">
              <h3 class="panel-title">新建讨论</h3>
              <button class="panel-close" @click="closeNewDialog">
                <X class="icon-md" />
              </button>
            </div>

            <!-- Panel Body: two columns -->
            <div class="panel-body">
              <!-- Left Column: Basic Settings (40%) -->
              <div class="panel-left">
                <div class="left-scroll">
                  <!-- Topic -->
                  <div class="form-section">
                    <label class="input-label">讨论主题</label>
                    <input
                      v-model="topicInput"
                      type="text"
                      placeholder="例如：为 RPG 游戏设计抽卡系统"
                      class="topic-input"
                      autofocus
                    />
                  </div>

                  <!-- Briefing -->
                  <div class="form-section">
                    <label class="input-label">讨论简报</label>
                    <textarea
                      v-model="briefingInput"
                      class="briefing-input"
                      placeholder="请提供讨论的背景信息，例如：&#10;- 讨论背景和上下文&#10;- 已知的约束条件&#10;- 期望的讨论产出"
                      rows="4"
                    />
                    <span class="briefing-hint">帮助策划团队更好地理解你的需求（可选）</span>
                  </div>

                  <!-- Attachment -->
                  <div class="form-section">
                    <input
                      ref="fileInputRef"
                      type="file"
                      accept=".md"
                      class="hidden"
                      @change="handleFileSelect"
                    />
                    <div v-if="attachmentFile" class="attachment-info">
                      <Paperclip class="icon-sm text-blue" />
                      <span class="attachment-name">{{ attachmentFile.name }}</span>
                      <span class="attachment-size">{{ (attachmentFile.size / 1024).toFixed(1) }} KB</span>
                      <button class="attachment-remove" @click="removeAttachment">
                        <X class="icon-xs" />
                      </button>
                    </div>
                    <button v-else class="attachment-add" @click="triggerFileInput">
                      <Paperclip class="icon-sm" />
                      <span>添加参考文档（.md）</span>
                    </button>
                  </div>

                  <!-- Password -->
                  <div class="form-section">
                    <label class="checkbox-label">
                      <input type="checkbox" v-model="usePassword" />
                      <span>设置讨论密码</span>
                    </label>
                    <div v-if="usePassword" class="password-field">
                      <input
                        v-model="password"
                        :type="showPassword ? 'text' : 'password'"
                        class="password-input"
                        placeholder="输入密码"
                      />
                      <button class="password-toggle" @click="showPassword = !showPassword" type="button">
                        <Eye v-if="!showPassword" class="icon-sm" />
                        <EyeOff v-else class="icon-sm" />
                      </button>
                    </div>
                  </div>

                  <!-- Auto-pause interval -->
                  <div class="form-section">
                    <label class="input-label">自动暂停间隔</label>
                    <div class="auto-pause-control">
                      <input
                        v-model.number="autoPauseInterval"
                        type="number"
                        min="0"
                        max="50"
                        class="auto-pause-input"
                      />
                      <span class="auto-pause-hint">
                        {{ autoPauseInterval > 0 ? `每 ${autoPauseInterval} 轮自动暂停` : '不自动暂停' }}
                      </span>
                    </div>
                  </div>

                  <!-- Agent Selection -->
                  <div class="form-section">
                    <AgentConfigEditor
                      v-model:agents="selectedAgents"
                      v-model:configs="agentConfigs"
                    />
                  </div>

                  <!-- Discussion Style -->
                  <div v-if="discussionStylesFull.length > 0" class="form-section">
                    <label class="input-label">讨论风格</label>
                    <div class="style-pills">
                      <button
                        v-for="style in discussionStylesFull"
                        :key="style.id"
                        class="style-pill"
                        :class="{ 'style-pill-active': selectedStyle === style.id }"
                        @click="onStyleSelect(style.id)"
                        :title="style.description"
                      >
                        {{ style.name }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Right Column: Prompt Preview & Edit (60%) -->
              <div class="panel-right">
                <!-- Prompt content area (scrollable) -->
                <div class="prompt-scroll">
                  <template v-if="customOverrides">
                    <!-- Goal -->
                    <div class="prompt-field">
                      <label class="prompt-field-label">目标</label>
                      <textarea
                        v-model="customOverrides.goal"
                        class="prompt-field-input"
                        placeholder="主策划的目标..."
                        @input="autoResize"
                      />
                    </div>

                    <!-- Backstory -->
                    <div class="prompt-field">
                      <label class="prompt-field-label">背景设定</label>
                      <textarea
                        v-model="customOverrides.backstory"
                        class="prompt-field-input"
                        placeholder="主策划的背景设定..."
                        @input="autoResize"
                      />
                    </div>

                    <!-- Communication style -->
                    <div class="prompt-field">
                      <label class="prompt-field-label">沟通风格</label>
                      <textarea
                        v-model="customOverrides.communication_style"
                        class="prompt-field-input"
                        placeholder="沟通风格描述..."
                        @input="autoResize"
                      />
                    </div>

                    <!-- Focus areas -->
                    <div class="prompt-field">
                      <label class="prompt-field-label">关注领域</label>
                      <div class="focus-areas-chips">
                        <span
                          v-for="(area, idx) in customOverrides.focus_areas"
                          :key="idx"
                          class="focus-chip"
                        >
                          <span class="focus-chip-text">{{ area }}</span>
                          <button class="focus-chip-remove" @click="removeFocusArea(idx)">
                            <X class="icon-xs" />
                          </button>
                        </span>
                        <div class="focus-add-wrapper">
                          <input
                            v-model="newFocusArea"
                            class="focus-add-input"
                            placeholder="添加领域..."
                            @keydown="handleFocusAreaKeydown"
                          />
                          <button
                            v-if="newFocusArea.trim()"
                            class="focus-add-btn"
                            @click="addFocusArea"
                          >
                            <Plus class="icon-xs" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </template>

                  <div v-else class="prompt-empty">
                    <p>选择讨论风格后可预览和编辑 Prompt</p>
                  </div>
                </div>

              </div>
            </div>

            <!-- Panel Footer -->
            <div class="panel-footer">
              <button class="reset-preset-btn" @click="resetToPreset">
                <RotateCcw class="icon-sm" />
                <span>恢复预设</span>
              </button>
              <p v-if="createError" class="create-error">{{ createError }}</p>
              <button class="btn-cancel" @click="closeNewDialog">取消</button>
              <button
                class="btn-create"
                :disabled="!topicInput.trim() || isCreating"
                @click="createDiscussion"
              >
                {{ isCreating ? '创建中...' : '开始讨论' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div><!-- home-page -->
  </div><!-- home-layout -->
    <!-- Resume Dialog -->
    <div v-if="showResumeDialog && resumeTarget" class="modal-mask" @click.self="showResumeDialog = false">
      <div class="modal-content resume-modal">
        <h2>继续讨论</h2>
        <p class="resume-topic">{{ resumeTarget.topic }}</p>
        
        <div class="form-group">
          <label>模式</label>
          <div class="mode-toggle">
            <button :class="{ active: resumeMode === 'extend' }" @click="resumeMode = 'extend'">
              原地继续
            </button>
            <button :class="{ active: resumeMode === 'continue' }" @click="resumeMode = 'continue'">
              新建分支
            </button>
          </div>
          <p class="mode-hint" v-if="resumeMode === 'extend'">在原讨论基础上追加轮次</p>
          <p class="mode-hint" v-else>创建新讨论，继承上次的上下文</p>
        </div>

        <div class="form-group">
          <label>追加说明（可选）</label>
          <textarea v-model="resumeFollowUp" placeholder="想继续聊什么？或者有新的方向？" rows="3" />
        </div>

        <div class="form-group">
          <label>额外轮次</label>
          <input type="number" v-model.number="resumeRounds" min="1" :max="resumeMode === 'extend' ? 100 : 10" />
        </div>

        <div class="modal-actions">
          <button class="btn-cancel" @click="showResumeDialog = false">取消</button>
          <button class="btn-primary" @click="doResume">开始</button>
        </div>
      </div>
    </div>

    <!-- Login Modal -->
    <LoginModal v-if="showLoginModal" @close="showLoginModal = false" />
</template>

<style scoped>
/* ===== Icon sizing utilities ===== */
.icon-xs { width: 14px; height: 14px; }
.icon-sm { width: 16px; height: 16px; }
.icon-md { width: 20px; height: 20px; }
.icon-lg { width: 32px; height: 32px; }
.icon-xl { width: 48px; height: 48px; }
.text-weak { color: var(--text-weak, #d1d5db); }
.text-blue { color: #3b82f6; }

/* ===== Page layout ===== */
.home-layout {
  display: flex;
  min-height: 100vh;
}
.section-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  color: var(--text-secondary, #9ca3af);
  font-size: 15px;
}
.home-page {
  flex: 1;
  min-width: 0;
  min-height: 100vh;
  background: var(--bg-primary, #f8f9fb);
  overflow-y: auto;
}

/* ===== Header ===== */
.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 32px;
  height: 32px;
  background: #111827;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-text {
  color: white;
  font-weight: 700;
  font-size: 13px;
}

.title-row { display: flex; align-items: center; gap: 4px; }
.title-row.clickable { cursor: pointer; color: #3b82f6; }
.title-row.clickable:hover { opacity: 0.8; }

.back-arrow { margin-right: 6px; font-size: 16px; }
.app-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  line-height: 1.2;
}

.app-subtitle {
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
}

.new-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--primary-color, #3b82f6);
  color: white;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.new-btn:hover {
  background: #2563eb;
}

/* ===== Content ===== */
.home-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 20px;
}

/* ===== Search ===== */
.search-bar {
  position: relative;
  margin-bottom: 20px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--text-secondary, #9ca3af);
}

.search-input {
  width: 100%;
  padding: 10px 36px 10px 36px;
  background: white;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 10px;
  font-size: 14px;
  color: var(--text-primary, #111827);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.search-input::placeholder {
  color: var(--text-secondary, #9ca3af);
}

.search-clear {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-secondary, #9ca3af);
  padding: 2px;
  border-radius: 4px;
  transition: color 0.2s;
}

.search-clear:hover {
  color: var(--text-primary, #6b7280);
}

/* ===== Card Grid Section ===== */
.cards-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.date-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.date-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding-left: 2px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

/* ===== Card ===== */
.card {
  background: white;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
  display: flex;
  flex-direction: column;
  min-height: 120px;
}

.card:hover {
  border-color: #d1d5db;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.card-active {
  border-color: var(--success-color, #10b981);
  border-width: 1.5px;
}

.card-active:hover {
  border-color: #059669;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.12);
}

/* Card status row */
.card-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.pulse-dot {
  width: 7px;
  height: 7px;
  background: var(--success-color, #10b981);
  border-radius: 50%;
  animation: pulse 2s infinite;
  flex-shrink: 0;
}

.queued-dot {
  background: #0284c7;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.card-badge {
  padding: 1px 7px;
  border-radius: 4px;
  font-weight: 500;
  font-size: 11px;
}

.badge-completed {
  background: #f0fdf4;
  color: #16a34a;
}

.badge-queued {
  background: #f0f9ff;
  color: #0284c7;
}

.badge-running {
  background: #ecfdf5;
  color: #059669;
}

.badge-paused {
  background: #fefce8;
  color: #ca8a04;
}

.badge-stopped {
  background: #fffbeb;
  color: #d97706;
}

.badge-failed {
  background: #fef2f2;
  color: #dc2626;
}

.card-time {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-secondary, #b0b7c3);
}

/* Card topic */

.card-owner-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  object-fit: cover;
  vertical-align: middle;
}
.card-owner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}
.card-topic {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  line-height: 1.4;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Card metrics */
.card-metrics {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
}

.metric {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

/* ===== Empty state ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 60px 20px;
  gap: 8px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #374151);
}

.empty-desc {
  font-size: 14px;
  color: var(--text-secondary, #9ca3af);
  margin-bottom: 16px;
}

/* ===== Buttons ===== */
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  background: var(--primary-color, #3b82f6);
  color: white;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #2563eb;
}

/* ===== Loading ===== */
.loading-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: var(--text-secondary, #9ca3af);
  font-size: 14px;
}

.spin-icon {
  width: 20px;
  height: 20px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ===== Error ===== */
.list-error {
  text-align: center;
  padding: 20px;
  color: #ef4444;
  font-size: 14px;
}

.list-error button {
  margin-top: 8px;
  padding: 6px 16px;
  background: var(--primary-color, #3b82f6);
  color: white;
  border-radius: 6px;
  font-size: 13px;
}

/* ===== Load more ===== */
.load-more-hint {
  text-align: center;
  padding: 16px;
  font-size: 13px;
  color: var(--text-weak, #d1d5db);
}

/* ===== Create Panel (large, two-column) ===== */
.create-panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.create-panel {
  width: 90vw;
  max-width: 1200px;
  height: 85vh;
  background: var(--bg-primary, white);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.18);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  flex-shrink: 0;
}

.panel-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.panel-close {
  padding: 4px;
  color: var(--text-secondary, #9ca3af);
  border-radius: 6px;
  transition: all 0.2s;
}

.panel-close:hover {
  background: #f3f4f6;
  color: var(--text-primary, #374151);
}

.panel-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* Left column (40%) */
.panel-left {
  width: 40%;
  border-right: 1px solid var(--border-color, #e5e7eb);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.left-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* Right column (60%) */
.panel-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.panel-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-secondary, #fafafa);
  flex-shrink: 0;
}

/* ===== Password Field ===== */
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
}
.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}
.password-field {
  position: relative;
  display: flex;
  align-items: center;
}

.password-input {
  width: 100%;
  padding: 10px 40px 10px 14px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.password-input:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.password-toggle {
  position: absolute;
  right: 10px;
  padding: 4px;
  color: var(--text-secondary, #9ca3af);
  border-radius: 4px;
  transition: color 0.2s;
  background: none;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.password-toggle:hover {
  color: var(--text-primary, #374151);
}

/* ===== Style Pills ===== */
.style-pills {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.style-pill {
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  border: 1.5px solid var(--border-color, #e5e7eb);
  background: white;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.style-pill:hover {
  border-color: #d1d5db;
  background: #fafbfc;
}

.style-pill-active {
  border-color: var(--primary-color, #3b82f6);
  background: #eff6ff;
  color: var(--primary-color, #3b82f6);
}

.style-pill-active:hover {
  border-color: var(--primary-color, #3b82f6);
  background: #eff6ff;
}

/* ===== Prompt Scroll Area ===== */
.prompt-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.prompt-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary, #9ca3af);
  font-size: 14px;
}

/* ===== Prompt Fields (flat layout) ===== */
.prompt-field {
  margin-bottom: 20px;
}

.prompt-field-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #6b7280);
  margin-bottom: 6px;
  letter-spacing: 0.3px;
}

.prompt-field-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid transparent;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.8;
  color: var(--text-primary, #111827);
  background: #f8f9fb;
  resize: none;
  overflow: hidden;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
}

.prompt-field-input:hover {
  border-color: var(--border-color, #e5e7eb);
}

.prompt-field-input:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  background: white;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.prompt-field-input::placeholder {
  color: var(--text-weak, #d1d5db);
}

/* ===== Focus Areas Chips ===== */
.focus-areas-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.focus-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 16px;
  font-size: 12px;
  color: var(--primary-color, #3b82f6);
}

.focus-chip-text {
  word-break: break-word;
}

.focus-chip-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1px;
  color: #93c5fd;
  border-radius: 50%;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
  background: none;
  border: none;
}

.focus-chip-remove:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.focus-add-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: 1px dashed var(--border-color, #d1d5db);
  border-radius: 16px;
  padding: 2px 8px;
  transition: border-color 0.15s;
}

.focus-add-wrapper:focus-within {
  border-color: var(--primary-color, #3b82f6);
}

.focus-add-input {
  border: none;
  outline: none;
  font-size: 12px;
  width: 100px;
  padding: 3px 0;
  background: transparent;
  color: var(--text-primary, #111827);
}

.focus-add-input::placeholder {
  color: var(--text-weak, #d1d5db);
}

.focus-add-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  color: var(--primary-color, #3b82f6);
  background: none;
  border: none;
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.15s;
}

.focus-add-btn:hover {
  background: rgba(59, 130, 246, 0.1);
}

.reset-preset-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
  background: white;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  margin-right: auto;
}

.reset-preset-btn:hover {
  color: var(--primary-color, #3b82f6);
  border-color: var(--primary-color, #3b82f6);
}

.input-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #374151);
  margin-bottom: 6px;
}

.topic-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.topic-input:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.topic-input::placeholder {
  color: var(--text-secondary, #9ca3af);
}

/* ===== Briefing ===== */
.briefing-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.6;
  resize: vertical;
  min-height: 80px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.briefing-input:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.briefing-input::placeholder {
  color: var(--text-secondary, #9ca3af);
}

.briefing-hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
}

.auto-pause-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.auto-pause-input {
  width: 72px;
  padding: 6px 10px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  font-size: 14px;
  text-align: center;
}

.auto-pause-input:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.auto-pause-hint {
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
}

.attachment-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #eff6ff;
  border-radius: 8px;
}

.attachment-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #374151);
}

.attachment-size {
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
}

.attachment-remove {
  padding: 2px;
  color: var(--text-secondary, #9ca3af);
  border-radius: 4px;
  transition: color 0.2s;
}

.attachment-remove:hover {
  color: #ef4444;
}

.attachment-add {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary, #9ca3af);
  transition: color 0.2s;
}

.attachment-add:hover {
  color: var(--primary-color, #3b82f6);
}

.agent-config-section {
  margin-top: 14px;
}

.btn-cancel {
  padding: 8px 16px;
  font-size: 14px;
  color: var(--text-secondary, #6b7280);
  background: white;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  transition: background 0.2s;
}

.btn-cancel:hover {
  background: #f9fafb;
}

.btn-create {
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 500;
  color: white;
  background: var(--primary-color, #3b82f6);
  border-radius: 8px;
  transition: background 0.2s;
}

.btn-create:hover:not(:disabled) {
  background: #2563eb;
}

.btn-create:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.create-error {
  color: var(--error-color, #dc2626);
  font-size: 12px;
  margin: 0;
  margin-right: auto;
  align-self: center;
}

.hidden {
  display: none;
}

/* ===== Modal transition ===== */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .create-panel,
.modal-leave-active .create-panel {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .create-panel,
.modal-leave-to .create-panel {
  transform: scale(0.95) translateY(10px);
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .card-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .home-content {
    padding: 16px 12px;
  }

  .create-panel {
    width: 98vw;
    height: 95vh;
  }

  .panel-body {
    flex-direction: column;
  }

  .panel-left {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border-color, #e5e7eb);
    max-height: 45%;
  }

  .panel-right {
    flex: 1;
  }
}

@media (max-width: 480px) {
  .card-grid {
    grid-template-columns: 1fr;
  }

  .home-header {
    padding: 12px 16px;
  }
}

/* ===== User Area ===== */
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.login-btn {
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #3b82f6;
  border: 1px solid #3b82f6;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s;
}
.login-btn:hover {
  background: #3b82f6;
  color: white;
}
.user-area {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  font-size: 13px;
  color: #374151;
}
.user-area:hover { background: #f3f4f6; }
.role-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #dbeafe;
  color: #1d4ed8;
}
.user-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  min-width: 140px;
  z-index: 100;
  padding: 4px;
}
.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
  border-radius: 4px;
}
.dropdown-item:hover { background: #f3f4f6; }


/* Modal overlay */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  width: 90%;
}
.modal-content h2 {
  margin: 0 0 4px;
  font-size: 18px;
}


/* Resume Dialog */
.resume-modal {
  max-width: 480px;
}
.resume-topic {
  font-size: 14px;
  color: #6b7280;
  margin: 4px 0 16px;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 6px;
}
.mode-toggle {
  display: flex;
  gap: 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.mode-toggle button {
  flex: 1;
  padding: 8px;
  border: none;
  background: white;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.mode-toggle button.active {
  background: #3b82f6;
  color: white;
}
.mode-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}
.card-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
}
.resume-btn:hover {
  border-color: #3b82f6;
  color: #3b82f6;
  background: #eff6ff;
}
.form-group {
  margin-bottom: 16px;
}
.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
  color: #374151;
}
.form-group textarea, .form-group input[type="number"] {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 13px;
  resize: vertical;
}
.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 20px;
}
.btn-cancel {
  padding: 8px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 13px;
}
.btn-primary {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  background: #3b82f6;
  color: white;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}
.btn-primary:hover { background: #2563eb; }

/* Card compact 2-row layout */
.card-row1 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.card-row1 .card-topic {
  flex: 1;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-row1 .card-time {
  flex-shrink: 0;
  font-size: 12px;
  color: #9ca3af;
}
.card-row1 .card-badge {
  flex-shrink: 0;
}
.card-row2 {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
}
.card-owner-text {
  margin-right: 4px;
}
.card-row2 .metric {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: #9ca3af;
}
.card-row2 .resume-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
  padding: 2px 8px;
  font-size: 12px;
  color: #6b7280;
  background: #f3f4f6;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.card-row2 .resume-btn:hover {
  background: #e5e7eb;
  color: #374151;
}
</style>
