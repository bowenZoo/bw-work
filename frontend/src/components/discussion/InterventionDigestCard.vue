<script setup lang="ts">
import type { LeadPlannerDigestEventData, InterventionAssessmentEventData } from '@/types'

defineProps<{
  digests: LeadPlannerDigestEventData[]
  assessments: InterventionAssessmentEventData[]
}>()

function impactColor(level: string): string {
  switch (level) {
    case 'ABSORB': return 'impact-absorb'
    case 'ADJUST': return 'impact-adjust'
    case 'REOPEN': return 'impact-reopen'
    default: return ''
  }
}

function impactLabel(level: string): string {
  switch (level) {
    case 'ABSORB': return '吸收'
    case 'ADJUST': return '调整'
    case 'REOPEN': return '回溯'
    default: return level
  }
}
</script>

<template>
  <div class="digest-card">
    <div class="card-header">
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
      <span class="card-title">主策划消化</span>
    </div>

    <!-- Digests -->
    <div v-for="(digest, idx) in digests" :key="'d-' + idx" class="digest-item">
      <p class="digest-summary">{{ digest.digest_summary }}</p>
      <div v-if="digest.key_points.length > 0" class="key-points">
        <span class="points-label">关键诉求:</span>
        <ul>
          <li v-for="(point, pi) in digest.key_points" :key="pi">{{ point }}</li>
        </ul>
      </div>
      <div v-if="digest.guidance" class="guidance">
        <span class="guidance-label">引导方向:</span>
        <span>{{ digest.guidance }}</span>
      </div>
    </div>

    <!-- Assessments -->
    <div v-for="(assess, idx) in assessments" :key="'a-' + idx" class="assessment-item">
      <div class="assessment-header">
        <span class="impact-badge" :class="impactColor(assess.impact_level)">
          {{ impactLabel(assess.impact_level) }}
        </span>
        <span class="assessment-reason">{{ assess.reason }}</span>
      </div>
      <div v-if="assess.affected_sections.length > 0" class="affected-sections">
        <span class="sections-label">受影响章节:</span>
        <span
          v-for="sid in assess.affected_sections"
          :key="sid"
          class="section-tag"
          :class="{ 'tag-reopen': assess.impact_level === 'REOPEN' }"
        >
          {{ sid }}
        </span>
      </div>
      <p v-if="assess.action_plan" class="action-plan">{{ assess.action_plan }}</p>
    </div>

    <div v-if="digests.length === 0 && assessments.length === 0" class="empty-hint">
      暂无消化记录
    </div>
  </div>
</template>

<style scoped>
.digest-card {
  background: var(--bg-secondary);
  border: 1px solid #93c5fd;
  border-left: 3px solid #3b82f6;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #2563eb;
}

.card-title {
  font-size: 13px;
  font-weight: 600;
}

.digest-item {
  padding: 8px;
  background: rgba(59, 130, 246, 0.04);
  border-radius: 4px;
}

.digest-summary {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0 0 6px;
  line-height: 1.5;
}

.key-points {
  font-size: 12px;
  color: var(--text-secondary);
}

.points-label {
  font-weight: 500;
  color: var(--text-primary);
}

.key-points ul {
  margin: 4px 0 0;
  padding-left: 18px;
}

.key-points li {
  margin: 2px 0;
}

.guidance {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.guidance-label {
  font-weight: 500;
  color: #2563eb;
}

.assessment-item {
  padding: 8px;
  background: rgba(59, 130, 246, 0.04);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.assessment-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.impact-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.impact-absorb {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.impact-adjust {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.impact-reopen {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.assessment-reason {
  font-size: 13px;
  color: var(--text-primary);
}

.affected-sections {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  font-size: 12px;
}

.sections-label {
  color: var(--text-secondary);
  font-weight: 500;
}

.section-tag {
  padding: 1px 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  font-size: 11px;
  color: var(--text-secondary);
}

.tag-reopen {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  font-weight: 500;
}

.action-plan {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.empty-hint {
  font-size: 12px;
  color: var(--text-weak);
  text-align: center;
  padding: 8px;
}
</style>
