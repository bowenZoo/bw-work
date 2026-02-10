<script setup lang="ts">
import type { HolisticReviewEventData } from '@/types'

defineProps<{
  reviews: HolisticReviewEventData[]
}>()

function conclusionClass(conclusion: string): string {
  switch (conclusion) {
    case 'APPROVED': return 'conclusion-approved'
    case 'NEEDS_REVISION': return 'conclusion-revision'
    case 'NEEDS_NEW_TOPIC': return 'conclusion-new-topic'
    default: return ''
  }
}

function conclusionLabel(conclusion: string): string {
  switch (conclusion) {
    case 'APPROVED': return '通过'
    case 'NEEDS_REVISION': return '需要修订'
    case 'NEEDS_NEW_TOPIC': return '需新议题'
    default: return conclusion
  }
}

function scoreClass(score: string): string {
  switch (score) {
    case 'pass': return 'score-pass'
    case 'warning': return 'score-warning'
    case 'fail': return 'score-fail'
    default: return ''
  }
}

function scoreLabel(score: string): string {
  switch (score) {
    case 'pass': return '通过'
    case 'warning': return '警告'
    case 'fail': return '未通过'
    default: return score
  }
}

function dimensionLabel(name: string): string {
  switch (name) {
    case 'consistency': return '一致性'
    case 'completeness': return '完整性'
    case 'responsiveness': return '回应度'
    case 'quality': return '质量'
    default: return name
  }
}
</script>

<template>
  <div class="review-card" v-for="(review, idx) in reviews" :key="idx">
    <div class="card-header">
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
      <span class="card-title">全局审视 (第 {{ review.review_round }} 轮)</span>
      <span class="conclusion-badge" :class="conclusionClass(review.conclusion)">
        {{ conclusionLabel(review.conclusion) }}
      </span>
    </div>

    <!-- Dimensions -->
    <div v-if="review.review_dimensions.length > 0" class="dimensions">
      <div
        v-for="dim in review.review_dimensions"
        :key="dim.name"
        class="dimension-row"
      >
        <span class="dim-name">{{ dimensionLabel(dim.name) }}</span>
        <span class="dim-score" :class="scoreClass(dim.score)">{{ scoreLabel(dim.score) }}</span>
        <span v-if="dim.notes" class="dim-notes">{{ dim.notes }}</span>
      </div>
    </div>

    <!-- Revisions needed -->
    <div v-if="review.revisions_needed.length > 0" class="revisions-section">
      <span class="section-label">需修订章节:</span>
      <ul class="revisions-list">
        <li v-for="(rev, ri) in review.revisions_needed" :key="ri">
          <span class="rev-id">{{ rev.section_id }}</span>
          <span class="rev-reason">{{ rev.reason }}</span>
        </li>
      </ul>
    </div>

    <!-- New topics -->
    <div v-if="review.new_topics.length > 0" class="topics-section">
      <span class="section-label">新增议题:</span>
      <ul class="topics-list">
        <li v-for="(topic, ti) in review.new_topics" :key="ti">
          <span class="topic-title">{{ topic.title }}</span>
          <span v-if="topic.description" class="topic-desc">— {{ topic.description }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.review-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
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
  color: var(--text-primary);
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  flex: 1;
}

.conclusion-badge {
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.conclusion-approved {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.conclusion-revision {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.conclusion-new-topic {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.dimensions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dimension-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 4px 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
}

.dim-name {
  font-weight: 500;
  color: var(--text-primary);
  min-width: 56px;
}

.dim-score {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.score-pass {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.score-warning {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.score-fail {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.dim-notes {
  color: var(--text-secondary);
  flex: 1;
}

.section-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.revisions-section,
.topics-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.revisions-list,
.topics-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--text-secondary);
}

.revisions-list li,
.topics-list li {
  margin: 2px 0;
}

.rev-id {
  font-weight: 500;
  color: #d97706;
  margin-right: 4px;
}

.rev-reason {
  color: var(--text-secondary);
}

.topic-title {
  font-weight: 500;
  color: #2563eb;
}

.topic-desc {
  color: var(--text-secondary);
}
</style>
