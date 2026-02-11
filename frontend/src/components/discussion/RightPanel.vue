<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { RoundSummary, DocUpdateEvent, DocPlan } from '@/types'
import StageSummaryPanel from './StageSummaryPanel.vue'
import InlineDesignDocs from './InlineDesignDocs.vue'
import DocOutline from './DocOutline.vue'

const props = defineProps<{
  roundSummaries: RoundSummary[]
  discussionId: string
  latestDocUpdate: DocUpdateEvent | null
  docPlan: DocPlan | null
  docContents: Map<string, string>
  currentSectionId: string | null
}>()

const emit = defineEmits<{
  (e: 'focus-section', sectionId: string): void
}>()

type TabKey = 'outline' | 'summaries'
const activeTab = ref<TabKey>('outline')

// Doc preview modal state
const showDocPreview = ref(false)
const previewFilename = ref<string | null>(null)

// New content indicators
const hasNewSummary = ref(false)
const hasNewOutline = ref(false)

watch(() => props.roundSummaries.length, (newLen, oldLen) => {
  if (oldLen !== undefined && newLen > oldLen && activeTab.value !== 'summaries') {
    hasNewSummary.value = true
  }
})

watch(() => props.docPlan, (newVal) => {
  if (newVal && activeTab.value !== 'outline') {
    hasNewOutline.value = true
  }
}, { deep: true })

// Auto-switch to outline when docPlan first arrives
watch(() => props.docPlan, (newVal, oldVal) => {
  if (newVal && !oldVal) {
    activeTab.value = 'outline'
  }
})

function switchTab(tab: TabKey) {
  activeTab.value = tab
  if (tab === 'summaries') hasNewSummary.value = false
  if (tab === 'outline') hasNewOutline.value = false
}

function handleSelectSection(_sectionId: string, filename: string) {
  previewFilename.value = filename
  showDocPreview.value = true
}

function handleFocusSection(sectionId: string) {
  emit('focus-section', sectionId)
}

function closeDocPreview() {
  showDocPreview.value = false
}

function downloadPreviewFile() {
  if (!previewFilename.value) return
  // Try to get content from docContents (WebSocket real-time data)
  const content = props.docContents?.get(previewFilename.value)
  if (content) {
    triggerDownload(previewFilename.value, content)
  }
}

function triggerDownload(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="right-panel-container">
    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'outline' }" @click="switchTab('outline')">
        <span>文档大纲</span>
        <span v-if="hasNewOutline" class="new-dot"></span>
      </button>
      <button class="tab-btn" :class="{ active: activeTab === 'summaries' }" @click="switchTab('summaries')">
        <span>轮次总结</span>
        <span v-if="hasNewSummary" class="new-dot"></span>
      </button>
    </div>

    <div class="tab-content">
      <DocOutline
        v-show="activeTab === 'outline'"
        :doc-plan="props.docPlan"
        :current-section-id="props.currentSectionId"
        @select-section="handleSelectSection"
        @focus-section="handleFocusSection"
      />
      <StageSummaryPanel
        v-show="activeTab === 'summaries'"
        :round-summaries="props.roundSummaries"
      />
    </div>

    <!-- Doc Preview Modal (overlay) -->
    <Teleport to="body">
      <div v-if="showDocPreview" class="doc-preview-overlay" @click.self="closeDocPreview">
        <div class="doc-preview-modal">
          <div class="doc-preview-header">
            <span class="doc-preview-title">{{ previewFilename }}</span>
            <div class="doc-preview-actions">
              <button class="doc-preview-download" @click="downloadPreviewFile" title="下载文档">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                <span>下载</span>
              </button>
              <button class="doc-preview-close" @click="closeDocPreview">&times;</button>
            </div>
          </div>
          <div class="doc-preview-body">
            <InlineDesignDocs
              :discussion-id="props.discussionId"
              :latest-doc-update="props.latestDocUpdate"
              :doc-contents="props.docContents"
              :selected-filename="previewFilename"
            />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.right-panel-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  overflow: hidden;
}

.tab-bar {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover, rgba(0, 0, 0, 0.03));
}

.tab-btn.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
}

.new-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ef4444;
  flex-shrink: 0;
}

.tab-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.tab-content > :deep(*) {
  flex: 1;
  min-height: 0;
}

/* Doc Preview Modal */
.doc-preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.doc-preview-modal {
  width: 92vw;
  max-width: 1400px;
  height: 90vh;
  background: var(--bg-primary, #fff);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.doc-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.doc-preview-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.doc-preview-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.doc-preview-download {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.doc-preview-download svg {
  width: 15px;
  height: 15px;
}

.doc-preview-download:hover {
  color: var(--primary-color);
  border-color: var(--primary-color);
  background: rgba(99, 102, 241, 0.08);
}

.doc-preview-close {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.doc-preview-close:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.doc-preview-body {
  flex: 1;
  overflow: hidden;
}
</style>
