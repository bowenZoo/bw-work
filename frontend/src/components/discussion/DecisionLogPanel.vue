<script setup lang="ts">
import { computed } from 'vue'
import type { Checkpoint, DecisionLogEntry, DecisionLogEntryType } from '@/types'

const props = defineProps<{
  checkpoints: Checkpoint[]
  discussionId: string
}>()

const emit = defineEmits<{
  'scroll-to-checkpoint': [checkpointId: string]
}>()

// Pending decisions: type=decision, not yet responded
const pendingDecisions = computed(() =>
  props.checkpoints.filter(cp => cp.type === 'decision' && cp.response === null && cp.responded_at === null)
)

// Timeline entries: all non-silent checkpoints, most recent first
const timelineEntries = computed<DecisionLogEntry[]>(() => {
  return props.checkpoints
    .filter(cp => cp.type !== 'silent')
    .map(cp => {
      let entryType: DecisionLogEntryType
      if (cp.type === 'decision') {
        entryType = 'decision'
      } else {
        // PROGRESS: determine if it's consensus or milestone based on title/summary heuristic
        // Default to 'milestone' for progress checkpoints
        entryType = 'milestone'
      }

      return {
        id: cp.id,
        type: entryType,
        checkpoint_id: cp.id,
        round_num: cp.round_num,
        title: cp.type === 'decision' ? cp.question : cp.title,
        summary: cp.summary,
        question: cp.question || undefined,
        options: cp.options.length > 0 ? cp.options : undefined,
        response: cp.response || undefined,
        response_text: cp.response_text || undefined,
        announced: cp.announced || undefined,
        created_at: cp.created_at,
        responded_at: cp.responded_at || undefined,
      }
    })
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
})

// Timeline entries excluding pending decisions (to avoid duplication)
const resolvedTimeline = computed(() =>
  timelineEntries.value.filter(entry => {
    if (entry.type === 'decision') {
      return entry.response !== undefined
    }
    return true
  })
)

function getSelectedLabel(entry: DecisionLogEntry): string {
  if (!entry.response || !entry.options) return entry.response || ''
  const opt = entry.options.find(o => o.id === entry.response)
  return opt ? `${opt.id}. ${opt.label}` : entry.response
}

function scrollTo(checkpointId: string) {
  emit('scroll-to-checkpoint', checkpointId)
}
</script>

<template>
  <div class="decision-log">
    <!-- Empty state -->
    <div v-if="checkpoints.length === 0 || timelineEntries.length === 0" class="decision-log__empty">
      <p class="decision-log__empty-title">暂无决策记录</p>
      <p class="decision-log__empty-desc">讨论进行中会在此显示关键决策和进展</p>
    </div>

    <template v-else>
      <!-- Pending decisions (pinned top) -->
      <div v-if="pendingDecisions.length > 0" class="decision-log__pending">
        <h5 class="decision-log__section-title decision-log__section-title--warning">
          待决策 ({{ pendingDecisions.length }})
        </h5>
        <div
          v-for="cp in pendingDecisions"
          :key="cp.id"
          class="decision-log__pending-card"
          @click="scrollTo(cp.id)"
        >
          <div class="pending-card__title">{{ cp.question }}</div>
          <div class="pending-card__meta">
            {{ cp.options.length }} 个选项 · 等待回答
          </div>
          <button class="pending-card__action" @click.stop="scrollTo(cp.id)">
            去回答
          </button>
        </div>
      </div>

      <!-- Timeline divider -->
      <div v-if="resolvedTimeline.length > 0" class="decision-log__divider">
        <span class="decision-log__divider-text">决策时间线</span>
      </div>

      <!-- Timeline -->
      <div class="decision-log__timeline">
        <div
          v-for="entry in resolvedTimeline"
          :key="entry.id"
          class="timeline-item"
          @click="scrollTo(entry.checkpoint_id)"
        >
          <!-- Icon -->
          <div
            class="timeline-item__icon"
            :class="{
              'timeline-item__icon--decision': entry.type === 'decision',
              'timeline-item__icon--milestone': entry.type === 'milestone',
              'timeline-item__icon--consensus': entry.type === 'consensus',
            }"
          >
            <!-- Decision: checkmark -->
            <svg v-if="entry.type === 'decision'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <!-- Milestone: flag -->
            <svg v-else-if="entry.type === 'milestone'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
              <line x1="4" y1="22" x2="4" y2="15" />
            </svg>
            <!-- Consensus: handshake circle -->
            <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="8 12 11 15 16 9" />
            </svg>
          </div>

          <!-- Content -->
          <div class="timeline-item__content">
            <div class="timeline-item__header">
              <span class="timeline-item__title">{{ entry.title }}</span>
              <span class="timeline-item__round">轮次 {{ entry.round_num }}</span>
            </div>

            <!-- Decision result -->
            <div v-if="entry.type === 'decision' && entry.response" class="timeline-item__result">
              选择: {{ getSelectedLabel(entry) }}
            </div>

            <!-- Summary for progress -->
            <div v-if="entry.type !== 'decision' && entry.summary" class="timeline-item__summary">
              {{ entry.summary }}
            </div>

            <!-- Response text -->
            <div v-if="entry.response_text" class="timeline-item__response-text">
              "{{ entry.response_text }}"
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.decision-log {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 0;
  height: 100%;
  overflow-y: auto;
}

/* Empty state */
.decision-log__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  flex: 1;
}

.decision-log__empty-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #374151);
  margin: 0 0 4px 0;
}

.decision-log__empty-desc {
  font-size: 13px;
  color: var(--chat-muted, #6b7280);
  margin: 0;
}

/* Section title */
.decision-log__section-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 8px 0;
  color: var(--chat-muted, #6b7280);
}

.decision-log__section-title--warning {
  color: #b45309;
}

/* Pending decisions */
.decision-log__pending {
  margin-bottom: 16px;
}

.decision-log__pending-card {
  padding: 10px 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.decision-log__pending-card:hover {
  border-color: #f59e0b;
  box-shadow: 0 1px 4px rgba(245, 158, 11, 0.1);
}

.pending-card__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  margin-bottom: 4px;
}

.pending-card__meta {
  font-size: 12px;
  color: var(--chat-muted, #6b7280);
  margin-bottom: 6px;
}

.pending-card__action {
  font-size: 12px;
  font-weight: 500;
  color: #b45309;
  padding: 0;
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.15s;
}

.pending-card__action:hover {
  color: #92400e;
  text-decoration: underline;
}

/* Divider */
.decision-log__divider {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 12px 0;
}

.decision-log__divider::before,
.decision-log__divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-color, #e5e7eb);
}

.decision-log__divider-text {
  font-size: 11px;
  font-weight: 500;
  color: var(--chat-muted, #9ca3af);
  white-space: nowrap;
}

/* Timeline */
.decision-log__timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-item {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s;
  position: relative;
}

.timeline-item:hover {
  background: var(--chat-bg-hover, #f3f4f6);
}

/* Timeline connector line */
.timeline-item:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 13px;
  top: 30px;
  bottom: -8px;
  width: 1px;
  background: var(--border-color, #e5e7eb);
}

/* Icon */
.timeline-item__icon {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  z-index: 1;
}

.timeline-item__icon--decision {
  background: #d1fae5;
  color: #065f46;
}

.timeline-item__icon--milestone {
  background: #dbeafe;
  color: #1e40af;
}

.timeline-item__icon--consensus {
  background: #ede9fe;
  color: #5b21b6;
}

/* Content */
.timeline-item__content {
  flex: 1;
  min-width: 0;
}

.timeline-item__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.timeline-item__title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #111827);
  line-height: 1.3;
}

.timeline-item__round {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--chat-muted, #9ca3af);
}

.timeline-item__result {
  font-size: 12px;
  color: #059669;
  margin-top: 2px;
}

.timeline-item__summary {
  font-size: 12px;
  color: var(--chat-muted-strong, #4b5563);
  margin-top: 2px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.timeline-item__response-text {
  font-size: 12px;
  color: var(--chat-muted, #6b7280);
  margin-top: 2px;
  font-style: italic;
}
</style>
