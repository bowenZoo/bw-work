<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import type { Agent, AgentStatus } from '@/types'
import { getAgentDisplayName, getAgentAvatar } from '@/utils/agents'
import { useAgentsStore } from '@/stores'

const agentsStore = useAgentsStore()

const props = defineProps<{
  agents: Agent[]
  statuses: Map<string, AgentStatus>
  currentSpeaker?: string
  moderatorRole?: string
  showSuperProducer?: boolean
  superProducerStatus?: 'idle' | 'thinking'
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

function getStatusLabel(agentId: string, status: AgentStatus): string {
  const content = agentsStore.getStatusContent(agentId)
  if (status === 'thinking' && content) {
    return content
  }
  switch (status) {
    case 'thinking': return '思考中'
    case 'speaking': return '发言中'
    case 'writing': return '更新文档中'
    default: return '空闲'
  }
}

// --- Timer logic (uses backend-provided started_at timestamps) ---
const timers = ref<Record<string, number>>({})       // agentId -> elapsed seconds
let intervalId: ReturnType<typeof setInterval> | null = null

function startTick() {
  if (intervalId) return
  intervalId = setInterval(() => {
    const now = Date.now()
    const updated: Record<string, number> = {}
    for (const [id, isoStr] of Object.entries(agentsStore.statusStartedAt)) {
      const startMs = new Date(isoStr).getTime()
      if (startMs > 0) {
        updated[id] = Math.floor((now - startMs) / 1000)
      }
    }
    timers.value = updated
  }, 1000)
}

function stopTick() {
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

// Watch statusStartedAt from store to start/stop ticker
watch(
  () => Object.keys(agentsStore.statusStartedAt).length,
  (count) => {
    if (count > 0) {
      // Immediate calc before next tick
      const now = Date.now()
      const updated: Record<string, number> = {}
      for (const [id, isoStr] of Object.entries(agentsStore.statusStartedAt)) {
        const startMs = new Date(isoStr).getTime()
        if (startMs > 0) {
          updated[id] = Math.floor((now - startMs) / 1000)
        }
      }
      timers.value = updated
      startTick()
    } else {
      timers.value = {}
      stopTick()
    }
  },
  { immediate: true },
)

onUnmounted(() => stopTick())
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
        'is-writing': getStatus(agent.id) === 'writing',
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
          <svg v-if="agent.role === 'lead_planner'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        </span>
        <span
          class="status-dot"
          :class="`dot-${getStatus(agent.id)}`"
        ></span>
      </div>
      <div class="agent-info">
        <div class="agent-name-row">
          <span class="agent-name">{{ getAgentDisplayName(agent.role) }}</span>
          <span v-if="moderatorRole && agent.role === moderatorRole" class="moderator-badge">主持</span>
          <span
            v-if="timers[agent.id] !== undefined"
            class="agent-timer"
            :class="`label-${getStatus(agent.id)}`"
          >{{ formatTime(timers[agent.id]) }}</span>
        </div>
        <span class="agent-status-label" :class="`label-${getStatus(agent.id)}`">
          {{ getStatusLabel(agent.id, getStatus(agent.id)) }}
        </span>
      </div>
    </div>

    <!-- Virtual: super producer (always last) -->
    <div
      v-if="showSuperProducer"
      class="agent-item super-producer-item"
      :class="{ 'is-thinking': superProducerStatus === 'thinking' }"
    >
      <div class="agent-avatar sp-avatar">
        <span class="sp-icon">🤖</span>
        <span class="status-dot" :class="superProducerStatus === 'thinking' ? 'dot-thinking' : 'dot-idle'" />
      </div>
      <div class="agent-info">
        <div class="agent-name-row">
          <span class="agent-name">超级制作人</span>
          <span class="sp-badge">AI</span>
        </div>
        <span class="agent-status-label" :class="superProducerStatus === 'thinking' ? 'label-thinking' : 'label-idle'">
          {{ superProducerStatus === 'thinking' ? '分析中' : '监控中' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-bar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  flex-shrink: 0;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 16px;
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

.agent-item.is-writing {
  background: rgba(99, 102, 241, 0.08);
}

.agent-avatar {
  position: relative;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: visible;
}

.avatar-img {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  font-size: 12px;
}

.status-dot {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1.5px solid var(--bg-secondary);
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

.dot-writing {
  background: #6366f1;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.agent-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.2;
}

.agent-name-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  min-width: 0;
}

.agent-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-timer {
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  flex-shrink: 0;
}

.moderator-badge {
  font-size: 9px;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 3px;
  background: #ede9fe;
  color: #6d28d9;
  white-space: nowrap;
  flex-shrink: 0;
  line-height: 1.4;
}

.sp-avatar {
  background: linear-gradient(135deg, #e0e7ff 0%, #f0fdf4 100%);
}
.sp-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  font-size: 14px;
  line-height: 1;
}
.sp-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
  background: #f0fdf4;
  color: #16a34a;
  white-space: nowrap;
  flex-shrink: 0;
  line-height: 1.4;
}
.super-producer-item {
  border-left: 1px solid #e0e7ff;
  margin-left: 2px;
  padding-left: 10px;
}

.agent-status-label {
  font-size: 10px;
  white-space: nowrap;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
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

.label-writing {
  color: #6366f1;
}
</style>
