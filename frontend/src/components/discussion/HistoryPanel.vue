<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { Message } from '@/types'
import { getAgentDisplayName } from '@/utils/agents'

const props = withDefaults(defineProps<{
  messages: Message[]
  filter?: string
}>(), {
  filter: '',
})

const emit = defineEmits<{
  (e: 'filterChange', filter: string): void
  (e: 'messageClick', message: Message): void
}>()

const containerRef = ref<HTMLElement | null>(null)
const isCollapsed = ref(false)

const filterOptions = [
  { key: '', label: '全部' },
  { key: 'lead_planner', label: '主策划' },
  { key: 'system_designer', label: '系统' },
  { key: 'number_designer', label: '数值' },
  { key: 'player_advocate', label: '玩家' },
]

const activeFilter = ref(props.filter)

const filteredMessages = computed(() => {
  if (!activeFilter.value) {
    return props.messages
  }
  return props.messages.filter(msg =>
    msg.agentId === activeFilter.value || msg.agentRole.toLowerCase().includes(activeFilter.value)
  )
})

function handleFilterClick(filterKey: string) {
  activeFilter.value = filterKey
  emit('filterChange', filterKey)
}

function handleMessageClick(message: Message) {
  emit('messageClick', message)
}

function getAgentIcon(agentRole: string): string {
  if (agentRole.includes('主策划') || agentRole === 'lead_planner') {
    return '👑'
  }
  if (agentRole.includes('User') || agentRole === 'user') {
    return '👤'
  }
  return '👤'
}

function truncateContent(content: string, maxLength = 100): string {
  if (content.length <= maxLength) return content
  return content.substring(0, maxLength) + '...'
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

// Auto-scroll to bottom when new messages arrive
watch(() => props.messages.length, async () => {
  await nextTick()
  if (containerRef.value && !isCollapsed.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight
  }
})
</script>

<template>
  <div class="history-panel" :class="{ collapsed: isCollapsed }">
    <!-- Header with filters -->
    <div class="panel-header" @click="toggleCollapse">
      <span class="header-icon">{{ isCollapsed ? '▶' : '▼' }}</span>
      <span class="header-title">历史记录</span>

      <!-- Filter tabs -->
      <div v-if="!isCollapsed" class="filter-tabs" @click.stop>
        <button
          v-for="option in filterOptions"
          :key="option.key"
          class="filter-tab"
          :class="{ active: activeFilter === option.key }"
          @click="handleFilterClick(option.key)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <!-- Messages list -->
    <div
      v-show="!isCollapsed"
      ref="containerRef"
      class="messages-container"
    >
      <div
        v-if="filteredMessages.length === 0"
        class="no-messages"
      >
        暂无消息
      </div>

      <div
        v-for="message in filteredMessages"
        :key="message.id"
        class="message-item"
        @click="handleMessageClick(message)"
      >
        <span class="message-icon">{{ getAgentIcon(message.agentRole) }}</span>
        <span class="message-role">{{ getAgentDisplayName(message.agentId) || message.agentRole }}:</span>
        <span class="message-content">{{ truncateContent(message.content) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary, #1a1a2e);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-color, #2d2d44);
  min-height: 100px;
  max-height: 300px;
}

.history-panel.collapsed {
  max-height: 44px;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--bg-tertiary, #16162a);
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
}

.panel-header:hover {
  background: var(--bg-hover, #1f1f3a);
}

.header-icon {
  font-size: 10px;
  color: var(--text-secondary, #888);
}

.header-title {
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
  font-size: 14px;
}

.filter-tabs {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.filter-tab {
  padding: 4px 8px;
  font-size: 11px;
  color: var(--text-secondary, #888);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-tab:hover {
  background: var(--bg-hover, #1f1f3a);
  color: var(--text-primary, #e0e0e0);
}

.filter-tab.active {
  background: var(--primary-color, #6366f1);
  color: white;
  border-color: var(--primary-color, #6366f1);
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.no-messages {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  color: var(--text-secondary, #888);
  font-size: 13px;
}

.message-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.message-item:hover {
  background: var(--bg-tertiary, #16162a);
}

.message-icon {
  font-size: 12px;
  flex-shrink: 0;
}

.message-role {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-color, #6366f1);
  flex-shrink: 0;
}

.message-content {
  font-size: 12px;
  color: var(--text-secondary, #888);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Scrollbar styling */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track {
  background: var(--bg-tertiary, #16162a);
}

.messages-container::-webkit-scrollbar-thumb {
  background: var(--border-color, #2d2d44);
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary, #888);
}
</style>
