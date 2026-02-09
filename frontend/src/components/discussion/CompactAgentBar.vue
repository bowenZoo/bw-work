<script setup lang="ts">
import type { Agent, AgentStatus } from '@/types'
import { getAgentDisplayName, getAgentAvatar } from '@/utils/agents'

const props = defineProps<{
  agents: Agent[]
  statuses: Map<string, AgentStatus>
  currentSpeaker?: string
}>()

const emit = defineEmits<{
  (e: 'selectAgent', agentId: string): void
}>()

function getStatus(agentId: string): AgentStatus {
  return props.statuses.get(agentId) || 'idle'
}

function isSpeaking(agentId: string): boolean {
  return agentId === props.currentSpeaker
}

function getStatusLabel(status: AgentStatus): string {
  switch (status) {
    case 'thinking': return '思考中'
    case 'speaking': return '发言中'
    default: return '空闲'
  }
}
</script>

<template>
  <div class="agent-bar">
    <div
      v-for="agent in agents"
      :key="agent.id"
      class="agent-item"
      :class="{
        'is-speaking': isSpeaking(agent.id),
        'is-thinking': getStatus(agent.id) === 'thinking',
      }"
      @click="emit('selectAgent', agent.id)"
    >
      <div class="agent-avatar">
        <img
          v-if="getAgentAvatar(agent.role)"
          :src="getAgentAvatar(agent.role)"
          :alt="getAgentDisplayName(agent.role)"
          class="avatar-img"
        />
        <span v-else class="avatar-fallback">
          {{ agent.role === 'lead_planner' ? '👑' : '👤' }}
        </span>
        <span
          class="status-dot"
          :class="`dot-${getStatus(agent.id)}`"
        ></span>
      </div>
      <span class="agent-name">{{ getAgentDisplayName(agent.role) }}</span>
      <span class="agent-status-label" :class="`label-${getStatus(agent.id)}`">
        {{ getStatusLabel(getStatus(agent.id)) }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.agent-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  flex-shrink: 0;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  cursor: pointer;
  transition: background 0.2s;
  flex: 1;
  min-width: 0;
}

.agent-item:hover {
  background: var(--bg-tertiary);
}

.agent-item.is-speaking {
  background: rgba(5, 150, 105, 0.08);
}

.agent-item.is-thinking {
  background: rgba(217, 119, 6, 0.06);
}

.agent-avatar {
  position: relative;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: visible;
}

.avatar-img {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  font-size: 14px;
}

.status-dot {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--bg-secondary);
}

.dot-idle {
  background: var(--text-weak);
}

.dot-thinking {
  background: var(--warning-color);
  animation: pulse 1.5s ease-in-out infinite;
}

.dot-speaking {
  background: var(--success-color);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.agent-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-status-label {
  font-size: 11px;
  white-space: nowrap;
  margin-left: auto;
}

.label-idle {
  color: var(--text-weak);
}

.label-thinking {
  color: var(--warning-color);
}

.label-speaking {
  color: var(--success-color);
}
</style>
