<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, Search, X, Paperclip, MessageSquare, FileText } from 'lucide-vue-next';
import { getDiscussionHistory } from '@/api/discussion';
import { useLobby } from '@/composables/useLobby';
import { AgentConfigEditor } from '@/components/discussion';
import type { DiscussionSummary, AgentConfig } from '@/types';

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
const autoPauseInterval = ref(5);
const attachmentFile = ref<File | null>(null);
const attachmentContent = ref('');
const fileInputRef = ref<HTMLInputElement | null>(null);
const isCreating = ref(false);

// Agent config
const selectedAgents = ref<string[]>([]);
const agentConfigs = ref<Record<string, Partial<AgentConfig>>>({});

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
  autoPauseInterval.value = 5;
  attachmentFile.value = null;
  attachmentContent.value = '';
  selectedAgents.value = [];
  agentConfigs.value = {};
}

function closeNewDialog() {
  showNewDialog.value = false;
}

async function createDiscussion() {
  const topic = topicInput.value.trim();
  if (!topic) return;

  isCreating.value = true;
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

    const response = await lobbyCreateDiscussion(
      topic,
      10,
      attachment,
      autoPauseInterval.value,
      selectedAgents.value.length > 0 ? selectedAgents.value : undefined,
      Object.keys(cleanConfigs).length > 0 ? cleanConfigs : undefined,
    );

    showNewDialog.value = false;
    router.push({ name: 'discussion-by-id', params: { id: response.id } });
  } catch (e) {
    console.error('Failed to create discussion:', e);
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
    case 'paused': return '已暂停';
    case 'failed': return '已中断';
    default: return '已完成';
  }
}

function getStatusClass(status: string | null): string {
  switch (status) {
    case 'queued': return 'badge-queued';
    case 'running': return 'badge-running';
    case 'paused': return 'badge-paused';
    case 'failed': return 'badge-failed';
    default: return 'badge-completed';
  }
}

function isActiveStatus(status: string | null): boolean {
  return status === 'running' || status === 'queued' || status === 'paused';
}

// Lifecycle
onMounted(() => {
  loadWorkspaces(true);
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

    <!-- New Discussion Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showNewDialog" class="modal-backdrop" @click.self="closeNewDialog">
          <div class="modal-container" @keydown="handleNewDialogKeydown">
            <div class="modal-header">
              <h3 class="modal-title">新建讨论</h3>
              <button class="modal-close" @click="closeNewDialog">
                <X class="icon-md" />
              </button>
            </div>
            <div class="modal-body">
              <label class="input-label">讨论主题</label>
              <input
                v-model="topicInput"
                type="text"
                placeholder="例如：为 RPG 游戏设计抽卡系统"
                class="topic-input"
                autofocus
              />

              <div class="auto-pause-section">
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

              <div class="attachment-section">
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

              <!-- Agent Configuration -->
              <div class="agent-config-section">
                <AgentConfigEditor
                  v-model:agents="selectedAgents"
                  v-model:configs="agentConfigs"
                />
              </div>
            </div>
            <div class="modal-footer">
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

/* ===== Modal styles ===== */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal-container {
  background: white;
  border-radius: 14px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
  margin: 16px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f3f4f6;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.modal-close {
  padding: 4px;
  color: var(--text-secondary, #9ca3af);
  border-radius: 6px;
  transition: all 0.2s;
}

.modal-close:hover {
  background: #f3f4f6;
  color: var(--text-primary, #374151);
}

.modal-body {
  padding: 20px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f3f4f6;
  background: var(--bg-secondary, #fafafa);
  border-radius: 0 0 14px 14px;
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

.auto-pause-section {
  margin-top: 14px;
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

.attachment-section {
  margin-top: 14px;
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

.hidden {
  display: none;
}

/* ===== Modal transition ===== */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
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
