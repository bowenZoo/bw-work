<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { DesignDocItem, DesignDocContentResponse, DocUpdateEvent, DocPlan } from '@/types'
import { listDesignDocs, getDesignDoc } from '@/api/design-docs'
import { toSanitizedMarkdownHtml } from '@/utils/markdown'

const props = defineProps<{
  discussionId: string
  latestDocUpdate: DocUpdateEvent | null
  docContents?: Map<string, string>
  selectedFilename?: string | null
}>()

const files = ref<DesignDocItem[]>([])
const selectedFile = ref<string | null>(null)
const selectedContent = ref<DesignDocContentResponse | null>(null)
const isLoading = ref(false)
const isLoadingContent = ref(false)
const error = ref<string | null>(null)

const isEmpty = computed(() => !isLoading.value && files.value.length === 0)

function extractTitle(content: string): string {
  const match = content.match(/^#\s+(.+)/m)
  return match ? match[1] : '未命名文档'
}

// If docContents provided via WebSocket, use it
const hasRealtimeDocs = computed(() => props.docContents && props.docContents.size > 0)

// Build file list from docContents when available
watch(() => props.docContents, (newMap) => {
  if (newMap && newMap.size > 0) {
    files.value = Array.from(newMap.entries()).map(([filename, content]) => ({
      filename,
      title: extractTitle(content),
      size: new Blob([content]).size,
      created_at: new Date().toISOString(),
    }))
    // Auto-select first if none selected
    if (!selectedFile.value && files.value.length > 0) {
      selectedFile.value = files.value[0].filename
    }
    // Refresh content for currently selected file
    if (selectedFile.value && newMap.has(selectedFile.value)) {
      const content = newMap.get(selectedFile.value)!
      selectedContent.value = {
        filename: selectedFile.value,
        title: extractTitle(content),
        content,
      }
    }
  }
}, { deep: true })

// Watch selectedFilename prop
watch(() => props.selectedFilename, (filename) => {
  if (filename) selectFile(filename)
})

// Load file list when discussionId changes
watch(
  () => props.discussionId,
  async (newId) => {
    if (newId) {
      await loadFileList()
    } else {
      files.value = []
      selectedFile.value = null
      selectedContent.value = null
    }
  },
  { immediate: true }
)

// Auto-refresh when latestDocUpdate changes
watch(
  () => props.latestDocUpdate,
  async (newVal) => {
    if (newVal && props.discussionId) {
      await loadFileList()
    }
  }
)

async function loadFileList() {
  if (!props.discussionId) return
  isLoading.value = true
  error.value = null
  try {
    const result = await listDesignDocs(props.discussionId)
    files.value = result.files
    // Auto-select first file if none selected
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

  // Prefer real-time content from WebSocket
  if (props.docContents?.has(filename)) {
    const content = props.docContents.get(filename)!
    selectedContent.value = {
      filename,
      title: extractTitle(content),
      content,
    }
    return
  }

  // Fallback to API
  isLoadingContent.value = true
  try {
    selectedContent.value = await getDesignDoc(props.discussionId, filename)
    error.value = null
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载文档内容失败'
    selectedContent.value = null
  } finally {
    isLoadingContent.value = false
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB`
}

function downloadCurrentFile() {
  if (!selectedContent.value) return
  const blob = new Blob([selectedContent.value.content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = selectedContent.value.filename
  a.click()
  URL.revokeObjectURL(url)
}

const renderedContent = computed(() => {
  if (!selectedContent.value?.content) return ''
  return toSanitizedMarkdownHtml(selectedContent.value.content)
})
</script>

<template>
  <div class="inline-docs">
    <!-- Loading state -->
    <div v-if="isLoading" class="loading-state">
      <div class="loading-spinner"></div>
      <span>加载中...</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <span>{{ error }}</span>
      <button class="retry-btn" @click="loadFileList">重试</button>
    </div>

    <!-- Empty state -->
    <div v-else-if="isEmpty" class="empty-state">
      <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
      <span class="empty-text">暂无策划文档</span>
    </div>

    <!-- File list + Preview -->
    <template v-else>
      <!-- File tabs -->
      <div class="file-tabs">
        <button
          v-for="file in files"
          :key="file.filename"
          class="file-tab"
          :class="{ active: selectedFile === file.filename }"
          @click="selectFile(file.filename)"
          :title="file.title"
        >
          <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span class="file-tab-title">{{ file.title }}</span>
          <span class="file-tab-size">{{ formatFileSize(file.size) }}</span>
        </button>
      </div>

      <!-- Content preview -->
      <div class="content-area">
        <div v-if="isLoadingContent" class="loading-state">
          <div class="loading-spinner"></div>
          <span>加载中...</span>
        </div>
        <template v-else-if="selectedContent">
          <div class="content-toolbar">
            <button class="download-btn" @click="downloadCurrentFile" title="下载文档">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <span>下载</span>
            </button>
          </div>
          <div class="markdown-body" v-html="renderedContent"></div>
        </template>
        <div v-else class="empty-state">
          <span class="empty-text">选择文件查看内容</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.inline-docs {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.file-tabs {
  display: flex;
  gap: 2px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
  overflow-x: auto;
}

.file-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}

.file-tab:hover {
  background: var(--bg-tertiary);
}

.file-tab.active {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
  color: var(--primary-color);
}

.file-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.file-tab-title {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-tab-size {
  font-size: 10px;
  opacity: 0.6;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.content-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.download-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.download-btn svg {
  width: 14px;
  height: 14px;
}

.download-btn:hover {
  color: var(--primary-color);
  border-color: var(--primary-color);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  color: var(--text-secondary);
  font-size: 13px;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  color: #fca5a5;
  font-size: 13px;
}

.retry-btn {
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 4px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  cursor: pointer;
}

.retry-btn:hover {
  background: var(--bg-hover);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 100%;
  min-height: 150px;
}

.empty-icon {
  width: 36px;
  height: 36px;
  color: var(--text-secondary);
  opacity: 0.4;
}

.empty-text {
  font-size: 13px;
  color: var(--text-weak);
}

/* Markdown styles */
.markdown-body {
  color: var(--text-primary);
  line-height: 1.8;
  font-size: 14px;
}

.markdown-body :deep(h1) {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.markdown-body :deep(h2) {
  font-size: 15px;
  font-weight: 600;
  margin: 16px 0 8px;
}

.markdown-body :deep(h3) {
  font-size: 14px;
  font-weight: 600;
  margin: 12px 0 6px;
}

.markdown-body :deep(p) {
  margin: 0 0 10px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin: 3px 0;
}

.markdown-body :deep(strong) {
  color: var(--primary-color);
}

.markdown-body :deep(code) {
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 0.9em;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
}

.markdown-body :deep(td),
.markdown-body :deep(th) {
  padding: 6px 10px;
  border: 1px solid var(--border-color);
  font-size: 12px;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--border-color);
  margin: 10px 0;
  padding-left: 12px;
  color: var(--text-secondary);
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 12px 0;
}
</style>
