<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Message } from '@/types'
import { toSanitizedMarkdownHtml } from '@/utils/markdown'

const props = defineProps<{
  messages: Message[]
}>()

// Extract round summary messages from lead_planner
const summaryMessages = computed(() =>
  props.messages.filter(m =>
    m.agentId === 'lead_planner' && m.content.includes('本轮总结')
  )
)

// Extract final decision document
const decisionMessage = computed(() =>
  [...props.messages].reverse().find(m =>
    m.agentId === 'lead_planner' && m.content.includes('策划决策文档')
  )
)

const isCompleted = computed(() => !!decisionMessage.value)

// Selected round index (null = show latest or decision)
const selectedRound = ref<number | null>(null)

// Auto-select latest when new summaries arrive
watch(
  () => summaryMessages.value.length,
  () => {
    selectedRound.value = null
  }
)

const displayContent = computed(() => {
  // If completed and no specific round selected, show decision document
  if (isCompleted.value && selectedRound.value === null) {
    return decisionMessage.value!.content
  }
  // If a specific round is selected, show that round's summary
  if (selectedRound.value !== null) {
    return summaryMessages.value[selectedRound.value]?.content ?? ''
  }
  // Otherwise show the latest summary
  const latest = summaryMessages.value[summaryMessages.value.length - 1]
  return latest?.content ?? ''
})

const renderedHtml = computed(() => {
  if (!displayContent.value) return ''
  return toSanitizedMarkdownHtml(displayContent.value)
})

const hasContent = computed(() => summaryMessages.value.length > 0 || isCompleted.value)

// Display title
const panelTitle = computed(() => {
  if (isCompleted.value && selectedRound.value === null) {
    return '策划决策文档'
  }
  if (selectedRound.value !== null) {
    return `第 ${selectedRound.value + 1} 轮总结`
  }
  if (summaryMessages.value.length > 0) {
    return `第 ${summaryMessages.value.length} 轮总结`
  }
  return '阶段总结'
})

function selectRound(index: number) {
  selectedRound.value = index
}

function showLatest() {
  selectedRound.value = null
}
</script>

<template>
  <div class="summary-panel">
    <!-- Header -->
    <div class="panel-header">
      <div class="header-left">
        <svg class="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span class="header-title">{{ panelTitle }}</span>
      </div>
      <span v-if="isCompleted" class="completed-badge">已完成</span>
    </div>

    <!-- Content -->
    <div class="panel-content">
      <template v-if="hasContent">
        <div class="markdown-body" v-html="renderedHtml"></div>
      </template>
      <template v-else>
        <div class="empty-state">
          <svg class="w-10 h-10 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span class="empty-text">讨论进行中，等待阶段总结...</span>
        </div>
      </template>
    </div>

    <!-- Round navigation -->
    <div v-if="summaryMessages.length > 0" class="round-nav">
      <button
        v-for="(_, idx) in summaryMessages"
        :key="idx"
        class="round-btn"
        :class="{ active: selectedRound === idx }"
        @click="selectRound(idx)"
      >
        第{{ idx + 1 }}轮
      </button>
      <button
        v-if="isCompleted"
        class="round-btn round-btn-decision"
        :class="{ active: selectedRound === null }"
        @click="showLatest"
      >
        决策文档
      </button>
    </div>
  </div>
</template>

<style scoped>
.summary-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.completed-badge {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(5, 150, 105, 0.1);
  color: var(--success-color);
  border-radius: 10px;
  font-weight: 500;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
}

.markdown-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
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
  color: var(--text-primary);
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

.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--border-color);
  margin: 10px 0;
  padding-left: 12px;
  color: var(--text-secondary);
}

.markdown-body :deep(code) {
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 0.9em;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 12px 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  min-height: 200px;
}

.empty-text {
  font-size: 13px;
  color: var(--text-weak);
}

.round-nav {
  display: flex;
  gap: 4px;
  padding: 8px 14px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.round-btn {
  padding: 3px 10px;
  font-size: 12px;
  border-radius: 12px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.15s;
}

.round-btn:hover {
  background: var(--bg-hover);
}

.round-btn.active {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.round-btn-decision {
  margin-left: auto;
}

.round-btn-decision.active {
  background: var(--success-color);
  border-color: var(--success-color);
}
</style>
