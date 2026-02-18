<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import type { RoundSummary } from '@/types'
import { toSanitizedMarkdownHtml } from '@/utils/markdown'

const props = defineProps<{
  roundSummaries: RoundSummary[]
}>()

// Selected round index (null = show latest)
const selectedRound = ref<number | null>(null)
const showDropdown = ref(false)
const selectorRef = ref<HTMLElement | null>(null)

// Current effective index
const currentIndex = computed(() =>
  selectedRound.value ?? props.roundSummaries.length - 1
)

// Auto-select latest when new summaries arrive
watch(
  () => props.roundSummaries.length,
  () => {
    selectedRound.value = null
  }
)

const currentSummary = computed<RoundSummary | null>(() => {
  if (props.roundSummaries.length === 0) return null
  if (selectedRound.value !== null) {
    return props.roundSummaries[selectedRound.value] ?? null
  }
  return props.roundSummaries[props.roundSummaries.length - 1]
})

const renderedHtml = computed(() => {
  if (!currentSummary.value) return ''
  return toSanitizedMarkdownHtml(currentSummary.value.content)
})

const hasContent = computed(() => props.roundSummaries.length > 0)

// Display title
const panelTitle = computed(() => {
  if (currentSummary.value) {
    return `第 ${currentSummary.value.round} 轮总结`
  }
  return '阶段总结'
})

function goPrev() {
  if (currentIndex.value > 0) selectedRound.value = currentIndex.value - 1
}

function goNext() {
  if (currentIndex.value < props.roundSummaries.length - 1) {
    selectedRound.value = currentIndex.value + 1
    // If reached the last one, set to null (= latest)
    if (selectedRound.value === props.roundSummaries.length - 1) {
      selectedRound.value = null
    }
  }
}

function jumpTo(idx: number) {
  selectedRound.value = idx === props.roundSummaries.length - 1 ? null : idx
  showDropdown.value = false
}

function showLatest() {
  selectedRound.value = null
}

function closeDropdown() {
  showDropdown.value = false
}

function onClickOutside(e: MouseEvent) {
  if (selectorRef.value && !selectorRef.value.contains(e.target as Node)) {
    showDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside, true)
})
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
    </div>

    <!-- Content -->
    <div class="panel-content">
      <template v-if="hasContent">
        <!-- Key points -->
        <div v-if="currentSummary?.key_points?.length" class="section">
          <h4 class="section-title">要点</h4>
          <ul class="point-list">
            <li v-for="(point, idx) in currentSummary.key_points" :key="idx" v-html="toSanitizedMarkdownHtml(point)"></li>
          </ul>
        </div>

        <!-- Markdown content -->
        <div class="markdown-body" v-html="renderedHtml"></div>

        <!-- Open questions -->
        <div v-if="currentSummary?.open_questions?.length" class="section open-questions">
          <h4 class="section-title">待讨论问题</h4>
          <ul class="point-list">
            <li v-for="(q, idx) in currentSummary.open_questions" :key="idx" v-html="toSanitizedMarkdownHtml(q)"></li>
          </ul>
        </div>
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
    <div v-if="roundSummaries.length > 1" class="round-nav">
      <!-- Prev -->
      <button class="nav-arrow" :disabled="currentIndex <= 0" @click="goPrev">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </button>

      <!-- Round selector -->
      <div ref="selectorRef" class="round-selector">
        <button class="round-current" @click="showDropdown = !showDropdown">
          第 {{ currentSummary?.round ?? currentIndex + 1 }} 轮
          <span class="round-total">/ 共 {{ roundSummaries.length }} 轮</span>
          <svg class="dropdown-caret" :class="{ open: showDropdown }" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        <!-- Dropdown (opens upward) -->
        <div v-if="showDropdown" class="round-dropdown">
          <button
            v-for="(s, idx) in [...roundSummaries].reverse()"
            :key="roundSummaries.length - idx"
            class="dropdown-item"
            :class="{ active: currentIndex === roundSummaries.length - 1 - idx }"
            @click="jumpTo(roundSummaries.length - 1 - idx)"
          >
            <span class="dropdown-seq">{{ roundSummaries.length - idx }}</span>
            <span class="dropdown-round">第{{ s.round }}轮</span>
          </button>
        </div>
      </div>

      <!-- Next -->
      <button class="nav-arrow" :disabled="selectedRound === null" @click="goNext">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>

      <!-- Latest shortcut -->
      <button v-if="selectedRound !== null" class="nav-latest" @click="showLatest">
        最新
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

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
}

.section {
  margin-bottom: 12px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-color);
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.point-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}

.point-list li {
  margin: 3px 0;
}

.open-questions {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.open-questions .section-title {
  color: var(--warning-color, #d97706);
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
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-top: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
}

.nav-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}

.nav-arrow:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-arrow:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.round-selector {
  position: relative;
}

.round-current {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  background: none;
  border: none;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s;
  white-space: nowrap;
}

.round-current:hover {
  background: var(--bg-hover);
}

.round-total {
  color: var(--text-weak);
  font-weight: 400;
}

.dropdown-caret {
  transition: transform 0.15s;
  color: var(--text-weak);
}

.dropdown-caret.open {
  transform: rotate(180deg);
}

.round-dropdown {
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  min-width: 120px;
  max-height: 240px;
  overflow-y: auto;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  z-index: 10;
  padding: 4px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: none;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
  transition: all 0.1s;
  white-space: nowrap;
}

.dropdown-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.dropdown-item.active {
  background: var(--primary-color);
  color: white;
}

.dropdown-item.active .dropdown-round {
  color: rgba(255, 255, 255, 0.7);
}

.dropdown-seq {
  min-width: 20px;
  text-align: right;
}

.dropdown-round {
  color: var(--text-weak);
  font-size: 11px;
}

.nav-latest {
  padding: 3px 10px;
  font-size: 12px;
  border-radius: 12px;
  background: var(--primary-color);
  color: white;
  border: 1px solid var(--primary-color);
  cursor: pointer;
  transition: all 0.15s;
  margin-left: 4px;
  flex-shrink: 0;
}

.nav-latest:hover {
  opacity: 0.85;
}
</style>
