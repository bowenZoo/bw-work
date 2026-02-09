<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { DesignDocItem, DesignDocContentResponse } from '@/types'
import { listDesignDocs, getDesignDoc, organizeDiscussion } from '@/api/design-docs'
import { toSanitizedMarkdownHtml } from '@/utils/markdown'

const props = defineProps<{
  visible: boolean
  discussionId: string
  discussionTopic?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const files = ref<DesignDocItem[]>([])
const selectedFile = ref<string | null>(null)
const selectedContent = ref<DesignDocContentResponse | null>(null)
const isLoading = ref(false)
const isLoadingContent = ref(false)
const isOrganizing = ref(false)
const error = ref<string | null>(null)
const createdAt = ref<string | null>(null)

// Load file list when panel opens
watch(
  () => props.visible,
  async (visible) => {
    if (visible && props.discussionId) {
      await loadFileList()
    } else {
      // Reset state when closed
      selectedFile.value = null
      selectedContent.value = null
      error.value = null
    }
  }
)

async function loadFileList() {
  isLoading.value = true
  error.value = null
  try {
    const result = await listDesignDocs(props.discussionId)
    files.value = result.files
    createdAt.value = result.created_at
    // Auto-select first file if available
    if (result.files.length > 0 && !selectedFile.value) {
      await selectFile(result.files[0].filename)
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载文档列表失败'
    files.value = []
  } finally {
    isLoading.value = false
  }
}

async function selectFile(filename: string) {
  selectedFile.value = filename
  isLoadingContent.value = true
  try {
    selectedContent.value = await getDesignDoc(props.discussionId, filename)
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载文档内容失败'
    selectedContent.value = null
  } finally {
    isLoadingContent.value = false
  }
}

async function handleOrganize() {
  isOrganizing.value = true
  error.value = null
  try {
    await organizeDiscussion(props.discussionId)
    // Reload file list
    selectedFile.value = null
    selectedContent.value = null
    await loadFileList()
  } catch (e: any) {
    error.value = e.response?.data?.detail || '整理文档失败'
  } finally {
    isOrganizing.value = false
  }
}

function handleClose() {
  emit('close')
}

function handleOverlayClick(event: MouseEvent) {
  if ((event.target as HTMLElement).classList.contains('panel-overlay')) {
    handleClose()
  }
}

const renderedContent = computed(() => {
  if (!selectedContent.value?.content) return ''
  return toSanitizedMarkdownHtml(selectedContent.value.content)
})

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB`
}

function formatDate(isoStr: string): string {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const isEmpty = computed(() => !isLoading.value && files.value.length === 0)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="panel-overlay"
      @click="handleOverlayClick"
    >
      <div class="panel-container">
        <!-- Header -->
        <div class="panel-header">
          <div class="header-left">
            <svg class="header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
            <div>
              <h3 class="panel-title">策划文档</h3>
              <p v-if="discussionTopic" class="panel-subtitle">{{ discussionTopic }}</p>
            </div>
          </div>
          <div class="header-actions">
            <button
              class="btn btn-organize"
              :disabled="isOrganizing"
              @click="handleOrganize"
              :title="files.length ? '重新整理' : '开始整理'"
            >
              <svg v-if="isOrganizing" class="spin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12a9 9 0 11-6.219-8.56" />
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-4 h-4">
                <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <span>{{ isOrganizing ? '整理中...' : (files.length ? '重新整理' : '开始整理') }}</span>
            </button>
            <button class="btn-close" @click="handleClose" title="关闭">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Error banner -->
        <div v-if="error" class="error-banner">
          <span>{{ error }}</span>
          <button @click="error = null" class="error-dismiss">x</button>
        </div>

        <!-- Main content -->
        <div class="panel-body">
          <!-- Loading state -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>加载中...</span>
          </div>

          <!-- Empty state -->
          <div v-else-if="isEmpty" class="empty-state">
            <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <p class="empty-title">暂无策划文档</p>
            <p class="empty-desc">点击"开始整理"按钮，AI 将自动分析讨论内容并生成策划文档</p>
          </div>

          <!-- File list + Preview -->
          <template v-else>
            <!-- File sidebar -->
            <div class="file-sidebar">
              <div class="file-list-header">
                <span class="file-count">{{ files.length }} 个文档</span>
                <span v-if="createdAt" class="file-date">{{ formatDate(createdAt) }}</span>
              </div>
              <div class="file-list">
                <button
                  v-for="file in files"
                  :key="file.filename"
                  class="file-item"
                  :class="{ active: selectedFile === file.filename }"
                  @click="selectFile(file.filename)"
                >
                  <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  <div class="file-info">
                    <span class="file-title">{{ file.title }}</span>
                    <span class="file-meta">{{ formatFileSize(file.size) }}</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Content preview -->
            <div class="content-preview">
              <div v-if="isLoadingContent" class="loading-state">
                <div class="loading-spinner"></div>
                <span>加载中...</span>
              </div>
              <div v-else-if="selectedContent" class="markdown-body" v-html="renderedContent"></div>
              <div v-else class="preview-placeholder">
                <p>选择左侧文件查看内容</p>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>


<style scoped>
.panel-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.panel-container {
  background: var(--bg-secondary, #1a1a2e);
  border-radius: 12px;
  width: 92%;
  max-width: 1100px;
  height: 85vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color, #2d2d44);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

/* Header */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color, #2d2d44);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  width: 24px;
  height: 24px;
  color: var(--primary-color, #6366f1);
}

.panel-title {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary, #e0e0e0);
}

.panel-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--text-secondary, #888);
  max-width: 400px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-organize {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--primary-color, #6366f1);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-organize:hover:not(:disabled) {
  background: var(--primary-hover, #4f46e5);
}

.btn-organize:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-organize svg {
  width: 16px;
  height: 16px;
}

.btn-close {
  background: transparent;
  border: none;
  color: var(--text-secondary, #888);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
}

.btn-close svg {
  width: 20px;
  height: 20px;
}

.btn-close:hover {
  background: var(--bg-tertiary, #16162a);
  color: var(--text-primary, #e0e0e0);
}

/* Error banner */
.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: rgba(239, 68, 68, 0.15);
  border-bottom: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  font-size: 13px;
}

.error-dismiss {
  background: none;
  border: none;
  color: #fca5a5;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
}

/* Body */
.panel-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Loading state */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
  padding: 40px;
  color: var(--text-secondary, #888);
  font-size: 14px;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-color, #2d2d44);
  border-top-color: var(--primary-color, #6366f1);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
  padding: 60px 40px;
  text-align: center;
}

.empty-icon {
  width: 48px;
  height: 48px;
  color: var(--text-secondary, #888);
  opacity: 0.5;
}

.empty-title {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary, #e0e0e0);
}

.empty-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary, #888);
  max-width: 300px;
}

/* File sidebar */
.file-sidebar {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color, #2d2d44);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.file-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color, #2d2d44);
}

.file-count {
  font-size: 12px;
  color: var(--text-secondary, #888);
}

.file-date {
  font-size: 11px;
  color: var(--text-secondary, #888);
  opacity: 0.7;
}

.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.file-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
  color: var(--text-primary, #e0e0e0);
}

.file-item:hover {
  background: var(--bg-tertiary, #16162a);
}

.file-item.active {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.3);
}

.file-icon {
  width: 18px;
  height: 18px;
  color: var(--primary-color, #6366f1);
  flex-shrink: 0;
  margin-top: 2px;
}

.file-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.file-title {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
  word-break: break-all;
}

.file-meta {
  font-size: 11px;
  color: var(--text-secondary, #888);
}

/* Content preview */
.content-preview {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.preview-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary, #888);
  font-size: 14px;
}

/* Markdown styles */
.markdown-body {
  color: var(--text-primary, #e0e0e0);
  line-height: 1.7;
  font-size: 14px;
}

.markdown-body :deep(.md-h2) {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
  margin: 24px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color, #2d2d44);
}

.markdown-body :deep(.md-h3) {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
  margin: 20px 0 10px;
}

.markdown-body :deep(.md-h4) {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary, #aaa);
  margin: 16px 0 8px;
}

.markdown-body :deep(.md-h5) {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary, #888);
  margin: 12px 0 6px;
}

.markdown-body :deep(strong) {
  color: var(--primary-color, #6366f1);
}

.markdown-body :deep(code) {
  background: var(--bg-tertiary, #16162a);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: #f0abfc;
}

.markdown-body :deep(ul) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.markdown-body :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--border-color, #2d2d44);
  font-size: 13px;
}

.markdown-body :deep(tr:nth-child(odd)) {
  background: var(--bg-tertiary, #16162a);
}

.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Responsive */
@media (max-width: 768px) {
  .panel-container {
    width: 100%;
    height: 100vh;
    border-radius: 0;
  }

  .panel-body {
    flex-direction: column;
  }

  .file-sidebar {
    width: 100%;
    max-height: 200px;
    border-right: none;
    border-bottom: 1px solid var(--border-color, #2d2d44);
  }
}
</style>
