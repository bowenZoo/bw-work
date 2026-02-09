<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, Search, X, Paperclip, PlayCircle, Eye, ArrowRight, MessageSquare } from 'lucide-vue-next';
import api from '@/api';
import { getDiscussionHistory } from '@/api/discussion';
import type { DiscussionStatus, DiscussionSummary } from '@/types';

interface CurrentDiscussion {
  id: string;
  topic: string;
  status: DiscussionStatus;
  rounds: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

const router = useRouter();

// Current (active) discussion
const currentDiscussion = ref<CurrentDiscussion | null>(null);
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null);

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

// New discussion dialog
const showNewDialog = ref(false);
const topicInput = ref('');
const autoPauseInterval = ref(5);
const attachmentFile = ref<File | null>(null);
const attachmentContent = ref('');
const fileInputRef = ref<HTMLInputElement | null>(null);
const isCreating = ref(false);

// Continue discussion
const showContinueModal = ref(false);
const selectedWorkspace = ref<DiscussionSummary | null>(null);
const continueFollowUp = ref('');
const isContinuing = ref(false);
const continueError = ref<string | null>(null);

// Computed
const isDiscussionRunning = computed(() => currentDiscussion.value?.status === 'running');
const isEmpty = computed(
  () => !isLoadingList.value && filteredWorkspaces.value.length === 0 && !currentDiscussion.value
);

// Fetch current discussion
async function fetchCurrentDiscussion() {
  try {
    const response = await api.get<CurrentDiscussion | null>('/api/discussions/current');
    currentDiscussion.value = response.data;
  } catch {
    currentDiscussion.value = null;
  }
}

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

// Polling
function startPolling() {
  stopPolling();
  pollTimer.value = setInterval(fetchCurrentDiscussion, 5000);
}
function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
}

// Navigation
function joinDiscussion() {
  router.push({ name: 'discussion' });
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
}

function closeNewDialog() {
  showNewDialog.value = false;
}

function createDiscussion() {
  const topic = topicInput.value.trim();
  if (!topic) return;

  isCreating.value = true;
  try {
    if (attachmentContent.value) {
      sessionStorage.setItem(
        'discussion_attachment',
        JSON.stringify({
          filename: attachmentFile.value?.name || 'attachment.md',
          content: attachmentContent.value,
        })
      );
    } else {
      sessionStorage.removeItem('discussion_attachment');
    }

    // Store auto-pause config for DiscussionView to pick up
    sessionStorage.setItem('discussion_auto_pause_interval', String(autoPauseInterval.value));

    showNewDialog.value = false;
    router.push({ name: 'discussion', query: { topic } });
  } finally {
    isCreating.value = false;
  }
}

function handleNewDialogKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
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

// Continue discussion
function handleContinueClick(workspace: DiscussionSummary) {
  selectedWorkspace.value = workspace;
  continueFollowUp.value = '';
  continueError.value = null;
  showContinueModal.value = true;
}

async function submitContinue() {
  if (!selectedWorkspace.value) return;

  isContinuing.value = true;
  try {
    const response = await api.post(
      `/api/discussions/${selectedWorkspace.value.id}/continue`,
      { follow_up: continueFollowUp.value.trim() || '', rounds: 2 }
    );
    if (response.data.new_discussion_id) {
      showContinueModal.value = false;
      router.push({ name: 'discussion' });
    }
  } catch (error: any) {
    continueError.value = error.response?.data?.detail || '继续讨论失败';
  } finally {
    isContinuing.value = false;
  }
}

function closeContinueModal() {
  if (isContinuing.value) return;
  showContinueModal.value = false;
  selectedWorkspace.value = null;
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

// Lifecycle
onMounted(() => {
  fetchCurrentDiscussion();
  loadWorkspaces(true);
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="workspace-page" @scroll="handleScroll">
    <!-- Header -->
    <header class="workspace-header">
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
        <Plus class="w-4 h-4" />
        <span>新建讨论</span>
      </button>
    </header>

    <!-- Content -->
    <main class="workspace-content">
      <!-- Active Workspace -->
      <section v-if="currentDiscussion && isDiscussionRunning" class="active-workspace">
        <div class="active-card" @click="joinDiscussion">
          <div class="active-indicator">
            <span class="pulse-dot" />
            <span class="active-label">进行中</span>
          </div>
          <h3 class="active-topic">{{ currentDiscussion.topic }}</h3>
          <div class="active-meta">
            <span>{{ currentDiscussion.rounds }} 轮讨论</span>
            <span v-if="currentDiscussion.started_at">
              · 开始于 {{ formatDate(currentDiscussion.started_at) }}
            </span>
          </div>
          <button class="join-btn" @click.stop="joinDiscussion">
            <PlayCircle class="w-4 h-4" />
            <span>加入讨论</span>
          </button>
        </div>
      </section>

      <!-- Completed current discussion hint -->
      <section
        v-else-if="currentDiscussion && currentDiscussion.status === 'completed'"
        class="completed-hint"
      >
        <div class="completed-hint-card">
          <MessageSquare class="w-5 h-5 text-gray-400" />
          <div class="completed-hint-text">
            <span class="completed-hint-topic">{{ currentDiscussion.topic }}</span>
            <span class="completed-hint-status">已完成</span>
          </div>
          <button
            class="view-btn-sm"
            @click="router.push({ name: 'discussion-by-id', params: { id: currentDiscussion.id } })"
          >
            查看
          </button>
        </div>
      </section>

      <!-- Search bar -->
      <div v-if="workspaces.length > 0 || searchQuery" class="search-bar">
        <Search class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索工作空间..."
          class="search-input"
        />
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Workspace list -->
      <section v-if="filteredWorkspaces.length > 0" class="workspace-list">
        <div
          v-for="workspace in filteredWorkspaces"
          :key="workspace.id"
          class="workspace-card"
          @click="viewWorkspace(workspace)"
        >
          <div class="workspace-card-main">
            <h3 class="workspace-topic">{{ workspace.topic }}</h3>
            <p v-if="workspace.summary" class="workspace-summary">
              {{ workspace.summary.length > 120 ? workspace.summary.slice(0, 120) + '...' : workspace.summary }}
            </p>
            <div class="workspace-meta">
              <span
                class="meta-badge"
                :class="{
                  'completed-badge': !workspace.status || workspace.status === 'completed',
                  'running-badge': workspace.status === 'running',
                  'failed-badge': workspace.status === 'failed',
                }"
              >{{ workspace.status === 'running' ? '进行中' : workspace.status === 'failed' ? '已中断' : '已完成' }}</span>
              <span class="meta-item">
                <MessageSquare class="w-3.5 h-3.5" />
                {{ workspace.message_count }} 条消息
              </span>
              <span class="meta-item">{{ formatDate(workspace.created_at) }}</span>
            </div>
          </div>
          <div class="workspace-card-actions">
            <button
              class="action-btn-icon"
              title="查看回放"
              @click.stop="viewWorkspace(workspace)"
            >
              <Eye class="w-4 h-4" />
            </button>
            <button
              class="action-btn-continue"
              title="继续讨论"
              @click.stop="handleContinueClick(workspace)"
            >
              <ArrowRight class="w-4 h-4" />
              <span>继续</span>
            </button>
          </div>
        </div>
      </section>

      <!-- Empty state -->
      <section v-if="isEmpty && !searchQuery" class="empty-state">
        <div class="empty-icon">
          <MessageSquare class="w-12 h-12 text-gray-300" />
        </div>
        <h3 class="empty-title">还没有工作空间</h3>
        <p class="empty-desc">创建你的第一个讨论，AI 策划团队将协作帮你设计游戏功能</p>
        <button class="new-btn" @click="openNewDialog">
          <Plus class="w-4 h-4" />
          <span>新建讨论</span>
        </button>
      </section>

      <!-- Empty search result -->
      <section v-if="filteredWorkspaces.length === 0 && searchQuery && !isLoadingList" class="empty-state">
        <p class="empty-title">没有匹配的工作空间</p>
        <p class="empty-desc">试试其他关键词</p>
      </section>

      <!-- Loading -->
      <div v-if="isLoadingList" class="loading-indicator">
        <svg class="animate-spin h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24">
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
                <X class="w-5 h-5" />
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
                  <Paperclip class="w-4 h-4 text-blue-500" />
                  <span class="attachment-name">{{ attachmentFile.name }}</span>
                  <span class="attachment-size">{{ (attachmentFile.size / 1024).toFixed(1) }} KB</span>
                  <button class="attachment-remove" @click="removeAttachment">
                    <X class="w-3.5 h-3.5" />
                  </button>
                </div>
                <button v-else class="attachment-add" @click="triggerFileInput">
                  <Paperclip class="w-4 h-4" />
                  <span>添加参考文档（.md）</span>
                </button>
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

    <!-- Continue Discussion Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showContinueModal" class="modal-backdrop" @click.self="closeContinueModal">
          <div class="modal-container">
            <div class="modal-header">
              <h3 class="modal-title">继续讨论</h3>
              <button class="modal-close" :disabled="isContinuing" @click="closeContinueModal">
                <X class="w-5 h-5" />
              </button>
            </div>
            <div class="modal-body">
              <div class="continue-info">
                <span class="continue-label">原议题</span>
                <p class="continue-topic">{{ selectedWorkspace?.topic }}</p>
              </div>
              <div v-if="selectedWorkspace?.summary" class="continue-info">
                <span class="continue-label">摘要</span>
                <p class="continue-summary">
                  {{ selectedWorkspace.summary.length > 200 ? selectedWorkspace.summary.slice(0, 200) + '...' : selectedWorkspace.summary }}
                </p>
              </div>
              <div class="continue-divider" />
              <label class="input-label">追加问题/方向</label>
              <textarea
                v-model="continueFollowUp"
                class="continue-input"
                placeholder="例如：想深入讨论装备强化的数值平衡..."
                rows="4"
                :disabled="isContinuing"
              />
              <p v-if="continueError" class="continue-error">{{ continueError }}</p>
            </div>
            <div class="modal-footer">
              <button class="btn-cancel" :disabled="isContinuing" @click="closeContinueModal">
                取消
              </button>
              <button
                class="btn-continue"
                :disabled="isContinuing"
                @click="submitContinue"
              >
                <svg v-if="isContinuing" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                {{ isContinuing ? '创建中...' : '继续讨论' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
/* Page layout */
.workspace-page {
  min-height: 100vh;
  background: #f8f9fb;
  overflow-y: auto;
}

/* Header */
.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
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
  color: #111827;
  line-height: 1.2;
}

.app-subtitle {
  font-size: 12px;
  color: #9ca3af;
}

.new-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #3b82f6;
  color: white;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.new-btn:hover {
  background: #2563eb;
}

/* Content */
.workspace-content {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px 16px;
}

/* Active workspace */
.active-workspace {
  margin-bottom: 24px;
}

.active-card {
  background: white;
  border: 1px solid #d1fae5;
  border-left: 4px solid #10b981;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.active-card:hover {
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.12);
}

.active-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background: #10b981;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.active-label {
  font-size: 12px;
  font-weight: 600;
  color: #059669;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.active-topic {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 6px;
}

.active-meta {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 16px;
}

.join-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  background: #10b981;
  color: white;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.join-btn:hover {
  background: #059669;
}

/* Completed hint */
.completed-hint {
  margin-bottom: 20px;
}

.completed-hint-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
}

.completed-hint-text {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.completed-hint-topic {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}

.completed-hint-status {
  font-size: 12px;
  color: #9ca3af;
  padding: 2px 8px;
  background: #f3f4f6;
  border-radius: 4px;
}

.view-btn-sm {
  font-size: 13px;
  color: #3b82f6;
  padding: 4px 12px;
  border-radius: 6px;
  transition: background 0.2s;
}

.view-btn-sm:hover {
  background: #eff6ff;
}

/* Search */
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
  color: #9ca3af;
}

.search-input {
  width: 100%;
  padding: 10px 36px 10px 36px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  font-size: 14px;
  color: #111827;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.search-input::placeholder {
  color: #9ca3af;
}

.search-clear {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #9ca3af;
  padding: 2px;
  border-radius: 4px;
  transition: color 0.2s;
}

.search-clear:hover {
  color: #6b7280;
}

/* Workspace list */
.workspace-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.workspace-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.workspace-card:hover {
  border-color: #d1d5db;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.workspace-card-main {
  flex: 1;
  min-width: 0;
}

.workspace-topic {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-summary {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.workspace-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #9ca3af;
}

.meta-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.completed-badge {
  background: #f0fdf4;
  color: #16a34a;
}

.running-badge {
  background: #fefce8;
  color: #ca8a04;
}

.failed-badge {
  background: #fef2f2;
  color: #dc2626;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.workspace-card-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.action-btn-icon {
  padding: 6px;
  color: #9ca3af;
  border-radius: 6px;
  transition: all 0.2s;
}

.action-btn-icon:hover {
  color: #3b82f6;
  background: #eff6ff;
}

.action-btn-continue {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: #10b981;
  background: #ecfdf5;
  border: 1px solid #d1fae5;
  border-radius: 6px;
  transition: all 0.2s;
}

.action-btn-continue:hover {
  background: #d1fae5;
  color: #059669;
}

/* Empty state */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  margin-bottom: 16px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 14px;
  color: #9ca3af;
  margin-bottom: 24px;
}

/* Loading */
.loading-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: #9ca3af;
  font-size: 14px;
}

/* Error */
.list-error {
  text-align: center;
  padding: 20px;
  color: #ef4444;
  font-size: 14px;
}

.list-error button {
  margin-top: 8px;
  padding: 6px 16px;
  background: #3b82f6;
  color: white;
  border-radius: 6px;
  font-size: 13px;
}

/* Load more hint */
.load-more-hint {
  text-align: center;
  padding: 16px;
  font-size: 13px;
  color: #d1d5db;
}

/* Modal styles */
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
  max-width: 480px;
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
  color: #111827;
}

.modal-close {
  padding: 4px;
  color: #9ca3af;
  border-radius: 6px;
  transition: all 0.2s;
}

.modal-close:hover:not(:disabled) {
  background: #f3f4f6;
  color: #374151;
}

.modal-close:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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
  background: #fafafa;
  border-radius: 0 0 14px 14px;
}

.input-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 6px;
}

.topic-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.topic-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.topic-input::placeholder {
  color: #9ca3af;
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
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 14px;
  text-align: center;
}

.auto-pause-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.auto-pause-hint {
  font-size: 12px;
  color: #9ca3af;
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
  color: #374151;
}

.attachment-size {
  font-size: 12px;
  color: #9ca3af;
}

.attachment-remove {
  padding: 2px;
  color: #9ca3af;
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
  color: #9ca3af;
  transition: color 0.2s;
}

.attachment-add:hover {
  color: #3b82f6;
}

.btn-cancel {
  padding: 8px 16px;
  font-size: 14px;
  color: #6b7280;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  transition: background 0.2s;
}

.btn-cancel:hover:not(:disabled) {
  background: #f9fafb;
}

.btn-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-create {
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 500;
  color: white;
  background: #3b82f6;
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

.btn-continue {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 500;
  color: white;
  background: #10b981;
  border-radius: 8px;
  transition: background 0.2s;
}

.btn-continue:hover:not(:disabled) {
  background: #059669;
}

.btn-continue:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Continue modal extras */
.continue-info {
  margin-bottom: 14px;
}

.continue-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #9ca3af;
  margin-bottom: 4px;
}

.continue-topic {
  font-size: 15px;
  font-weight: 500;
  color: #111827;
}

.continue-summary {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
}

.continue-divider {
  height: 1px;
  background: #f3f4f6;
  margin: 16px 0;
}

.continue-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 14px;
  resize: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.continue-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.continue-input:disabled {
  background: #f9fafb;
}

.continue-input::placeholder {
  color: #9ca3af;
}

.continue-error {
  margin-top: 8px;
  font-size: 13px;
  color: #ef4444;
}

/* Modal transition */
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

/* Responsive */
@media (max-width: 640px) {
  .workspace-header {
    padding: 12px 16px;
  }

  .workspace-content {
    padding: 16px 12px;
  }

  .workspace-card {
    flex-direction: column;
    gap: 12px;
  }

  .workspace-card-actions {
    flex-direction: row;
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
