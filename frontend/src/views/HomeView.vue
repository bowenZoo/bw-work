<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick, toRaw } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, Search, X, Paperclip, MessageSquare, FileText, Eye, EyeOff, RotateCcw } from 'lucide-vue-next';
import { getDiscussionHistory, getDiscussionStyles } from '@/api/discussion';
import { useLobby } from '@/composables/useLobby';
import { AgentConfigEditor } from '@/components/discussion';
import type { DiscussionSummary, AgentConfig, DiscussionStyle, DiscussionStyleFull, DiscussionStyleOverrides } from '@/types';

const router = useRouter();

// Lobby state (active discussions via WebSocket)
const {
  activeDiscussions,
  createDiscussion: lobbyCreateDiscussion,
} = useLobby();

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
}

// Merge active discussions + history into unified list
const allCards = computed<CardItem[]>(() => {
  const activeIds = new Set(activeDiscussions.value.map(d => d.id));
  const cards: CardItem[] = [];

  // Add active discussions first (they have live status)
  for (const d of activeDiscussions.value) {
    cards.push({
      id: d.id,
      topic: d.topic,
      status: d.status,
      message_count: 0,
      doc_count: 0,
      rounds: d.rounds,
      created_at: d.created_at,
      isLive: true,
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
      });
    }
  }

  return cards;
});

// Filter by search
const filteredCards = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return allCards.value;
  return allCards.value.filter(c => c.topic?.toLowerCase().includes(q));
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
const password = ref('123456');
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
    const response = await getDiscussionHistory(page.value, PAGE_SIZE);
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
function viewCard(card: CardItem) {
  router.push({ name: 'discussion-by-id', params: { id: card.id } });
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
  password.value = '123456';
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
      password.value || undefined,
      briefingInput.value.trim() || undefined,
    );

    showNewDialog.value = false;
    router.push({ name: 'discussion-by-id', params: { id: response.id } });
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
onMounted(() => {
  loadWorkspaces(true);
  loadStyles();
});
</script>

<template>
  <div class="home-page" @scroll="handleScroll">
    <!-- Header -->
    <header class="home-header">
      <div class="header-left">
        <div class="logo">
          <span class="logo-text">BW</span>
        </div>
        <div>
          <h1 class="app-title">Game Design</h1>
          <p class="app-subtitle">AI 策划工作空间</p>
        </div>
      </div>
      <button class="new-btn" @click="openNewDialog">
        <Plus class="icon-sm" />
        <span>新建讨论</span>
      </button>
    </header>

    <!-- Content -->
    <main class="home-content">

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
              <!-- Status badge -->
              <div class="card-status">
                <span v-if="isActiveStatus(card.status)" class="pulse-dot" :class="{ 'queued-dot': card.status === 'queued' }" />
                <span class="card-badge" :class="getStatusClass(card.status)">
                  {{ getStatusLabel(card.status) }}
                </span>
                <span class="card-time">{{ formatDate(card.created_at) }}</span>
              </div>

              <!-- Topic -->
              <h3 class="card-topic">{{ card.topic }}</h3>

              <!-- Metrics -->
              <div class="card-metrics">
                <span v-if="card.isLive && card.rounds > 0" class="metric">
                  第 {{ card.rounds }} 轮
                </span>
                <span v-if="card.message_count > 0" class="metric">
                  <MessageSquare class="icon-xs" />
                  {{ card.message_count }}
                </span>
                <span v-if="card.doc_count > 0" class="metric">
                  <FileText class="icon-xs" />
                  {{ card.doc_count }}
                </span>
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
                    <label class="input-label">密码设置</label>
                    <div class="password-field">
                      <input
                        v-model="password"
                        :type="showPassword ? 'text' : 'password'"
                        class="password-input"
                        placeholder="设置讨论密码"
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
  </div>
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
.home-page {
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
</style>
