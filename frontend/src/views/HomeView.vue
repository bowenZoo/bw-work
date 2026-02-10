<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, Search, X, Paperclip, PlayCircle, MessageSquare, FileText, Eye } from 'lucide-vue-next';
import { getDiscussionHistory } from '@/api/discussion';
import { useLobby } from '@/composables/useLobby';
import { AgentConfigEditor } from '@/components/discussion';
import type { DiscussionSummary, AgentConfig } from '@/types';

const router = useRouter();

// Lobby state (active discussions via WebSocket)
const {
  activeDiscussions,
  viewerCount,
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
const filteredWorkspaces = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return workspaces.value;
  return workspaces.value.filter(
    (w) =>
      w.topic?.toLowerCase().includes(q) ||
      w.summary?.toLowerCase().includes(q)
  );
});

// Date grouping
interface DateGroup {
  label: string;
  items: DiscussionSummary[];
}

const groupedWorkspaces = computed<DateGroup[]>(() => {
  const items = filteredWorkspaces.value;
  if (items.length === 0) return [];

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86400000;

  const today: DiscussionSummary[] = [];
  const yesterday: DiscussionSummary[] = [];
  const earlier: DiscussionSummary[] = [];

  for (const item of items) {
    const ts = new Date(item.created_at).getTime();
    if (ts >= todayStart) {
      today.push(item);
    } else if (ts >= yesterdayStart) {
      yesterday.push(item);
    } else {
      earlier.push(item);
    }
  }

  const groups: DateGroup[] = [];
  if (today.length) groups.push({ label: '今天', items: today });
  if (yesterday.length) groups.push({ label: '昨天', items: yesterday });
  if (earlier.length) groups.push({ label: '更早', items: earlier });
  return groups;
});

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

// Has active discussions?
const hasActive = computed(() => activeDiscussions.value.length > 0);

const isEmpty = computed(
  () => !isLoadingList.value && filteredWorkspaces.value.length === 0 && !hasActive.value
);

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
function viewDiscussion(id: string) {
  router.push({ name: 'discussion-by-id', params: { id } });
}

function viewWorkspace(workspace: DiscussionSummary) {
  router.push({ name: 'discussion-by-id', params: { id: workspace.id } });
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
    // Prepare attachment
    const attachment = attachmentContent.value
      ? { filename: attachmentFile.value?.name || 'attachment.md', content: attachmentContent.value }
      : null;

    // Filter out empty config overrides
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

    // Navigate to the new discussion
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

// Format date helper
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
    case 'failed': return '已中断';
    default: return '已完成';
  }
}

function getStatusClass(status: string | null): string {
  switch (status) {
    case 'queued': return 'badge-queued';
    case 'running': return 'badge-running';
    case 'failed': return 'badge-failed';
    default: return 'badge-completed';
  }
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

      <!-- Active Discussions Section -->
      <section v-if="hasActive" class="active-section">
        <h4 class="section-label">
          <span class="pulse-dot" />
          进行中的讨论
        </h4>
        <div class="active-cards">
          <div
            v-for="disc in activeDiscussions"
            :key="disc.id"
            class="meeting-card meeting-running"
            @click="viewDiscussion(disc.id)"
          >
            <div class="meeting-indicator">
              <span :class="disc.status === 'queued' ? 'queued-dot' : 'pulse-dot'" />
              <span class="meeting-label">{{ disc.status === 'queued' ? '排队中' : disc.status === 'paused' ? '已暂停' : '进行中' }}</span>
            </div>
            <h3 class="meeting-topic">"{{ disc.topic }}"</h3>
            <div class="meeting-meta">
              <span>第 {{ disc.rounds }} 轮</span>
              <span v-if="disc.agents.length > 0" class="meta-sep">·</span>
              <span v-if="disc.agents.length > 0">{{ disc.agents.length }} 位参与者</span>
            </div>
            <button class="join-btn" @click.stop="viewDiscussion(disc.id)">
              <PlayCircle class="icon-sm" />
              加入会议
            </button>
          </div>
        </div>
      </section>

      <!-- Idle state (no active discussions) -->
      <section v-else class="meeting-card-wrapper">
        <div class="meeting-card meeting-idle">
          <div class="meeting-idle-text">
            <MessageSquare class="icon-lg text-weak" />
            <p class="idle-hint">随时可以发起新的策划讨论</p>
          </div>
          <button class="btn-primary" @click="openNewDialog">
            <Plus class="icon-sm" />
            发起讨论
          </button>
        </div>
      </section>

      <!-- Search bar -->
      <div v-if="workspaces.length > 0 || searchQuery" class="search-bar">
        <Search class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索讨论记录..."
          class="search-input"
        />
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">
          <X class="icon-sm" />
        </button>
      </div>

      <!-- History list with date groups -->
      <section v-if="groupedWorkspaces.length > 0" class="history-section">
        <div v-for="group in groupedWorkspaces" :key="group.label" class="date-group">
          <h4 class="date-label">{{ group.label }}</h4>
          <div class="history-list">
            <div
              v-for="ws in group.items"
              :key="ws.id"
              class="history-card"
              @click="viewWorkspace(ws)"
            >
              <h3 class="history-topic">{{ ws.topic }}</h3>
              <div class="history-meta">
                <span class="history-badge" :class="getStatusClass(ws.status)">
                  {{ getStatusLabel(ws.status) }}
                </span>
                <span class="meta-item">
                  <MessageSquare class="icon-xs" />
                  {{ ws.message_count }} 条消息
                </span>
                <span v-if="ws.doc_count > 0" class="meta-item">
                  <FileText class="icon-xs" />
                  {{ ws.doc_count }} 份文档
                </span>
                <span class="meta-item meta-time">{{ formatDate(ws.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Empty search result -->
      <section v-if="filteredWorkspaces.length === 0 && searchQuery && !isLoadingList" class="empty-state">
        <p class="empty-title">没有匹配的讨论记录</p>
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
      <div v-if="hasMore && !isLoadingList && filteredWorkspaces.length > 0" class="load-more-hint">
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

              <!-- Agent Configuration (collapsible) -->
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
.text-muted { color: var(--text-secondary, #9ca3af); }
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
  max-width: 720px;
  margin: 0 auto;
  padding: 24px 16px;
}

/* ===== Active Discussions Section ===== */
.active-section {
  margin-bottom: 24px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #059669;
  letter-spacing: 0.3px;
  margin-bottom: 10px;
}

.active-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ===== Meeting Room Card ===== */
.meeting-card-wrapper {
  margin-bottom: 24px;
}

.meeting-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  transition: box-shadow 0.2s;
}

/* Running state */
.meeting-running {
  border: 2px solid var(--success-color, #10b981);
  cursor: pointer;
}

.meeting-running:hover {
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.15);
}

.meeting-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background: var(--success-color, #10b981);
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.queued-dot {
  width: 8px;
  height: 8px;
  background: #0284c7;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

.meeting-label {
  font-size: 13px;
  font-weight: 600;
  color: #059669;
  letter-spacing: 0.3px;
}

.meeting-topic {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  margin-bottom: 8px;
}

.meeting-meta {
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}

.meta-sep {
  margin: 0 6px;
  color: var(--text-weak, #d1d5db);
}

.join-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 28px;
  background: var(--success-color, #10b981);
  color: white;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  transition: background 0.2s;
}

.join-btn:hover {
  background: #059669;
}

/* Idle state */
.meeting-idle {
  border: 2px dashed var(--border-color, #d1d5db);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 32px 24px;
}

.meeting-idle-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.idle-hint {
  font-size: 14px;
  color: var(--text-secondary, #9ca3af);
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

/* ===== Search ===== */
.search-bar {
  position: relative;
  margin-bottom: 16px;
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

/* ===== History Section ===== */
.history-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.date-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.date-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding-left: 2px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-card {
  padding: 14px 18px;
  background: white;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.history-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.history-topic {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
}

.history-badge {
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
  background: #fefce8;
  color: #ca8a04;
}

.badge-failed {
  background: #fef2f2;
  color: #dc2626;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.meta-time {
  margin-left: auto;
}

/* ===== Empty state ===== */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #374151);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: var(--text-secondary, #9ca3af);
  margin-bottom: 24px;
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
@media (max-width: 640px) {
  .home-header {
    padding: 12px 16px;
  }

  .home-content {
    padding: 16px 12px;
  }

  .meeting-card {
    padding: 18px;
  }
}
</style>
