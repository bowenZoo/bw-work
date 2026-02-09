<script setup lang="ts">
import { computed } from 'vue'
import type { DocPlan, FilePlan, SectionPlan } from '@/types'

const props = defineProps<{
  docPlan: DocPlan | null
  currentSectionId: string | null
}>()

const emit = defineEmits<{
  (e: 'select-section', sectionId: string, filename: string): void
  (e: 'focus-section', sectionId: string): void
}>()

function handleSectionClick(section: SectionPlan, filename: string) {
  emit('select-section', section.id, filename)
}

function handleFocusSection(section: SectionPlan) {
  emit('focus-section', section.id)
}

function statusIcon(status: string) {
  if (status === 'completed') return '\u2713'
  if (status === 'in_progress') return '\u25CF'
  return '\u25CB'
}

function statusClass(status: string, sectionId: string) {
  const isCurrent = sectionId === props.currentSectionId
  return {
    'status-pending': status === 'pending' && !isCurrent,
    'status-in-progress': status === 'in_progress' || isCurrent,
    'status-completed': status === 'completed',
  }
}
</script>

<template>
  <div class="doc-outline">
    <div v-if="!docPlan" class="empty-state">
      <span class="empty-text">等待文档规划生成...</span>
    </div>
    <div v-else class="outline-tree">
      <div v-for="file in docPlan.files" :key="file.filename" class="file-group">
        <div class="file-header">
          <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span class="file-title">{{ file.title }}</span>
        </div>
        <div class="sections-list">
          <button
            v-for="section in file.sections"
            :key="section.id"
            class="section-item"
            :class="statusClass(section.status, section.id)"
            @click="handleSectionClick(section, file.filename)"
            @contextmenu.prevent="handleFocusSection(section)"
          >
            <span class="section-status">{{ statusIcon(section.status) }}</span>
            <span class="section-title">{{ section.title }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.doc-outline {
  padding: 10px;
  overflow-y: auto;
  height: 100%;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 100px;
}

.empty-text {
  font-size: 13px;
  color: var(--text-weak);
}

.outline-tree {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.file-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.file-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.sections-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-left: 22px;
}

.section-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: all 0.15s;
  font-size: 12px;
  color: var(--text-secondary);
}

.section-item:hover {
  background: var(--bg-tertiary);
}

.section-status {
  flex-shrink: 0;
  width: 14px;
  text-align: center;
  font-size: 10px;
}

.section-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Status styles */
.status-pending .section-status {
  color: var(--text-weak);
}

.status-in-progress {
  background: rgba(59, 130, 246, 0.08);
}

.status-in-progress .section-status {
  color: #3b82f6;
  animation: pulse-blue 2s ease-in-out infinite;
}

.status-in-progress .section-title {
  color: #3b82f6;
  font-weight: 500;
}

.status-completed .section-status {
  color: #10b981;
  font-weight: bold;
}

.status-completed .section-title {
  color: var(--text-primary);
}

@keyframes pulse-blue {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
