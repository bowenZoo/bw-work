<script setup lang="ts">
import { computed } from 'vue'
import type { Checkpoint } from '@/types'

const props = defineProps<{
  checkpoint: Checkpoint
}>()

const formattedTime = computed(() => {
  const date = new Date(props.checkpoint.created_at)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})
</script>

<template>
  <div class="progress-notice">
    <div class="progress-notice__accent" />
    <div class="progress-notice__body">
      <!-- Header -->
      <div class="progress-notice__header">
        <span class="progress-notice__badge">进展通报</span>
        <span class="progress-notice__round">第 {{ checkpoint.round_num }} 轮</span>
        <span class="progress-notice__time">{{ formattedTime }}</span>
      </div>

      <!-- Title -->
      <h4 class="progress-notice__title">{{ checkpoint.title }}</h4>

      <!-- Summary -->
      <p v-if="checkpoint.summary" class="progress-notice__summary">
        {{ checkpoint.summary }}
      </p>

      <!-- Key points -->
      <ul v-if="checkpoint.key_points.length > 0" class="progress-notice__points">
        <li
          v-for="(point, idx) in checkpoint.key_points"
          :key="idx"
          class="progress-notice__point"
        >
          {{ point }}
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.progress-notice {
  display: flex;
  max-width: min(560px, 100%);
  border-radius: var(--chat-radius-lg, 12px);
  overflow: hidden;
  background: var(--chat-card, #ffffff);
  border: 1px solid var(--chat-border, #e5e7eb);
}

.progress-notice__accent {
  width: 4px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #3b82f6, #8b5cf6);
}

.progress-notice__body {
  flex: 1;
  padding: 12px 16px;
  min-width: 0;
}

/* Header */
.progress-notice__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.progress-notice__badge {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: #ede9fe;
  color: #6d28d9;
}

.progress-notice__round {
  font-size: 11px;
  color: var(--chat-muted, #6b7280);
}

.progress-notice__time {
  font-size: 11px;
  color: var(--chat-muted, #6b7280);
  margin-left: auto;
}

/* Title */
.progress-notice__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  margin: 0 0 4px 0;
  line-height: 1.4;
}

/* Summary */
.progress-notice__summary {
  font-size: 13px;
  color: var(--chat-muted-strong, #4b5563);
  line-height: 1.5;
  margin: 0 0 8px 0;
}

/* Key points */
.progress-notice__points {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-notice__point {
  font-size: 12px;
  color: var(--chat-muted-strong, #4b5563);
  line-height: 1.4;
  padding-left: 14px;
  position: relative;
}

.progress-notice__point::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #8b5cf6;
}
</style>
