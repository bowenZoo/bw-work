<script setup lang="ts">
import { computed } from 'vue'
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

// Position agents around the table (4 positions)
const agentPositions = computed(() => {
  // Arrange agents in round table positions:
  // Top-left, Top-right, Bottom-left, Bottom-right
  const positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right']
  return props.agents.slice(0, 4).map((agent, index) => ({
    agent,
    position: positions[index] || 'top-left',
    status: props.statuses.get(agent.id) || 'idle',
    isSpeaking: agent.id === props.currentSpeaker,
  }))
})

function getStatusLabel(status: AgentStatus): string {
  switch (status) {
    case 'thinking':
      return '思考中'
    case 'speaking':
      return '发言中'
    default:
      return '空闲'
  }
}

function handleAgentClick(agentId: string) {
  emit('selectAgent', agentId)
}
</script>

<template>
  <div class="round-table">
    <!-- Table center -->
    <div class="table-center">
      <span class="center-icon">💬</span>
    </div>

    <!-- Agent avatars positioned around the table -->
    <div
      v-for="{ agent, position, status, isSpeaking } in agentPositions"
      :key="agent.id"
      class="agent-seat"
      :class="[
        `position-${position}`,
        `status-${status}`,
        { 'is-speaking': isSpeaking },
      ]"
      @click="handleAgentClick(agent.id)"
    >
      <!-- Avatar -->
      <div class="agent-avatar" :class="{ 'avatar-speaking': isSpeaking }">
        <img
          v-if="getAgentAvatar(agent.role)"
          :src="getAgentAvatar(agent.role)"
          :alt="getAgentDisplayName(agent.role)"
          class="avatar-image"
        />
        <span v-else class="avatar-fallback">
          {{ agent.role === 'lead_planner' ? '👑' : '👤' }}
        </span>

        <!-- Status indicator dot -->
        <span class="status-dot" :class="`dot-${status}`"></span>
      </div>

      <!-- Agent name and status -->
      <div class="agent-info">
        <span class="agent-name">{{ getAgentDisplayName(agent.role) }}</span>
        <span class="agent-status" :class="`text-${status}`">
          ({{ getStatusLabel(status) }})
        </span>
      </div>

      <!-- Connection lines to center -->
      <div class="connection-line" :class="`line-${position}`"></div>
    </div>
  </div>
</template>

<style scoped>
.round-table {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  max-width: 300px;
  margin: 0 auto;
}

.table-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 60px;
  height: 60px;
  background: var(--bg-tertiary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--border-color);
  z-index: 2;
}

.center-icon {
  font-size: 24px;
}

.agent-seat {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: transform 0.2s;
}

.agent-seat:hover {
  transform: scale(1.05);
}

/* Position agents around the table */
.position-top-left {
  top: 5%;
  left: 10%;
}

.position-top-right {
  top: 5%;
  right: 10%;
}

.position-bottom-left {
  bottom: 5%;
  left: 10%;
}

.position-bottom-right {
  bottom: 5%;
  right: 10%;
}

.agent-avatar {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--bg-secondary);
  border: 3px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-fallback {
  font-size: 24px;
}

/* Status-based border colors */
.status-idle .agent-avatar {
  border-color: var(--border-color);
}

.status-thinking .agent-avatar {
  border-color: var(--warning-color);
  animation: pulse 1.5s ease-in-out infinite;
}

.status-speaking .agent-avatar,
.is-speaking .agent-avatar {
  border-color: var(--success-color);
  transform: scale(1.1);
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.status-dot {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--bg-secondary);
}

.dot-idle {
  background: var(--text-weak);
}

.dot-thinking {
  background: var(--warning-color);
  animation: blink 1s ease-in-out infinite;
}

.dot-speaking {
  background: var(--success-color);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.agent-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.agent-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.agent-status {
  font-size: 10px;
  white-space: nowrap;
}

.text-idle {
  color: var(--text-weak);
}

.text-thinking {
  color: var(--warning-color);
}

.text-speaking {
  color: var(--success-color);
}

/* Connection lines (decorative) */
.connection-line {
  position: absolute;
  background: var(--border-color);
  z-index: -1;
}

.line-top-left {
  width: 2px;
  height: 50px;
  transform: rotate(45deg);
  bottom: -20px;
  right: -20px;
}

.line-top-right {
  width: 2px;
  height: 50px;
  transform: rotate(-45deg);
  bottom: -20px;
  left: -20px;
}

.line-bottom-left {
  width: 2px;
  height: 50px;
  transform: rotate(-45deg);
  top: -20px;
  right: -20px;
}

.line-bottom-right {
  width: 2px;
  height: 50px;
  transform: rotate(45deg);
  top: -20px;
  left: -20px;
}
</style>
