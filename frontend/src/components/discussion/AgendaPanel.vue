<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Agenda, AgendaItem } from '@/types'

const props = withDefaults(defineProps<{
  agenda: Agenda | null
  collapsed?: boolean
}>(), {
  collapsed: false,
})

const emit = defineEmits<{
  (e: 'viewSummary', item: AgendaItem): void
  (e: 'skipItem', itemId: string): void
  (e: 'addItem'): void
}>()

const isCollapsed = ref(props.collapsed)

const currentItem = computed(() => {
  if (!props.agenda || props.agenda.items.length === 0) return null
  const idx = props.agenda.current_index
  if (idx >= 0 && idx < props.agenda.items.length) {
    return props.agenda.items[idx]
  }
  return null
})

const progress = computed(() => {
  if (!props.agenda) return { completed: 0, total: 0 }
  const completed = props.agenda.items.filter(
    item => item.status === 'completed' || item.status === 'skipped'
  ).length
  return { completed, total: props.agenda.items.length }
})

function getStatusIcon(status: string): string {
  switch (status) {
    case 'completed':
      return '✅'
    case 'in_progress':
      return '🔵'
    case 'skipped':
      return '⏭️'
    default:
      return '⬜'
  }
}

function getStatusClass(status: string): string {
  switch (status) {
    case 'completed':
      return 'status-completed'
    case 'in_progress':
      return 'status-in-progress'
    case 'skipped':
      return 'status-skipped'
    default:
      return 'status-pending'
  }
}

function handleViewSummary(item: AgendaItem) {
  if (item.status === 'completed') {
    emit('viewSummary', item)
  }
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}
</script>

<template>
  <div class="agenda-panel">
    <!-- Header -->
    <div class="agenda-header" @click="toggleCollapse">
      <span class="agenda-icon">📝</span>
      <span class="agenda-title">议程</span>
      <template v-if="currentItem">
        <span class="agenda-current-indicator">-</span>
        <span class="agenda-current">
          <span class="current-icon">🔵</span>
          {{ progress.completed + 1 }}. {{ currentItem.title }}
          <span class="current-marker">← 当前</span>
        </span>
      </template>
      <span class="agenda-toggle">{{ isCollapsed ? '展开▼' : '收起▲' }}</span>
    </div>

    <!-- Content (expandable) -->
    <div v-show="!isCollapsed" class="agenda-content">
      <div v-if="!agenda || agenda.items.length === 0" class="agenda-empty">
        暂无议程
      </div>

      <div v-else class="agenda-list">
        <div
          v-for="(item, index) in agenda.items"
          :key="item.id"
          class="agenda-item"
          :class="[getStatusClass(item.status), { 'is-current': index === agenda.current_index }]"
        >
          <span class="item-status">{{ getStatusIcon(item.status) }}</span>
          <span class="item-index">{{ index + 1 }}.</span>
          <span class="item-title">{{ item.title }}</span>

          <!-- Priority indicator -->
          <span v-if="item.priority === 1" class="priority-badge priority-high" title="高优先级">高</span>
          <span v-if="item.priority === -1" class="priority-badge priority-low" title="低优先级">低</span>

          <!-- Source tag -->
          <span
            v-if="item.source && item.source !== 'initial'"
            class="source-tag"
            :class="'source-' + item.source"
          >
            {{ item.source === 'discovered' ? '发现' : item.source === 'intervention' ? '干预' : item.source }}
          </span>

          <!-- Related sections -->
          <div v-if="item.related_sections && item.related_sections.length > 0" class="related-sections">
            <span
              v-for="sid in item.related_sections"
              :key="sid"
              class="section-chip"
              :class="'chip-' + (item.source || 'initial')"
            >
              {{ sid }}
            </span>
          </div>

          <template v-if="item.status === 'completed'">
            <button
              class="btn-view-summary"
              @click.stop="handleViewSummary(item)"
              title="查看小结"
            >
              查看小结
            </button>
          </template>

          <template v-if="index === agenda.current_index">
            <span class="current-badge">当前</span>
          </template>
        </div>

        <!-- Add item button -->
        <div class="agenda-add" @click="emit('addItem')">
          <span class="add-icon">➕</span>
          <span class="add-text">添加新议题</span>
        </div>
      </div>

      <!-- Progress bar -->
      <div v-if="agenda && agenda.items.length > 0" class="agenda-progress">
        <div class="progress-bar">
          <div
            class="progress-fill"
            :style="{ width: `${(progress.completed / progress.total) * 100}%` }"
          ></div>
        </div>
        <span class="progress-text">{{ progress.completed }}/{{ progress.total }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agenda-panel {
  background: var(--bg-secondary);
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.agenda-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-primary);
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.agenda-header:hover {
  background: var(--bg-hover);
}

.agenda-icon {
  font-size: 16px;
}

.agenda-title {
  font-weight: 600;
  color: var(--text-primary);
}

.agenda-current-indicator {
  color: var(--text-secondary);
}

.agenda-current {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-primary);
  font-size: 14px;
}

.current-icon {
  font-size: 12px;
}

.current-marker {
  color: var(--text-secondary);
  font-size: 12px;
  margin-left: 4px;
}

.agenda-toggle {
  color: var(--text-secondary);
  font-size: 12px;
}

.agenda-content {
  padding: 12px 16px;
}

.agenda-empty {
  color: var(--text-weak);
  text-align: center;
  padding: 20px;
}

.agenda-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agenda-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: var(--bg-tertiary);
  transition: all 0.2s;
}

.agenda-item:hover {
  background: var(--bg-hover);
}

.agenda-item.is-current {
  border-left: 3px solid var(--primary-color);
  background: var(--bg-active);
}

.item-status {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.item-index {
  color: var(--text-secondary);
  font-size: 14px;
  min-width: 24px;
}

.item-title {
  flex: 1;
  color: var(--text-primary);
  font-size: 14px;
}

.status-completed .item-title {
  color: var(--success-color);
}

.status-in-progress .item-title {
  color: var(--primary-color);
  font-weight: 500;
}

.status-skipped .item-title {
  color: var(--text-secondary);
  text-decoration: line-through;
}

.btn-view-summary {
  padding: 4px 8px;
  font-size: 12px;
  color: var(--primary-color);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-view-summary:hover {
  background: var(--primary-color);
  color: white;
}

.current-badge {
  padding: 2px 6px;
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  border-radius: 4px;
}

.agenda-add {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px dashed var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.agenda-add:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
  background: rgba(10, 10, 10, 0.03);
}

.add-icon {
  font-size: 14px;
}

.add-text {
  font-size: 13px;
}

.agenda-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary-color);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 40px;
  text-align: right;
}

/* Priority badges */
.priority-badge {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.priority-high {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.priority-low {
  background: rgba(156, 163, 175, 0.1);
  color: #9ca3af;
}

/* Source tags */
.source-tag {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 500;
  flex-shrink: 0;
}

.source-discovered {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.source-intervention {
  background: rgba(168, 85, 247, 0.1);
  color: #7c3aed;
}

/* Related section chips */
.related-sections {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
}

.section-chip {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 10px;
  white-space: nowrap;
}

.chip-initial {
  background: rgba(107, 114, 128, 0.1);
  color: #6b7280;
}

.chip-discovered {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.chip-intervention {
  background: rgba(168, 85, 247, 0.1);
  color: #7c3aed;
}
</style>
