<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { Checkpoint } from '@/types'

const props = defineProps<{
  checkpoint: Checkpoint
  discussionId: string
}>()

const emit = defineEmits<{
  respond: [checkpointId: string, optionId: string | null, freeInput: string]
}>()

const selectedOption = ref<string | null>(null)
const freeInput = ref('')
const isSubmitting = ref(false)

const isResponded = computed(() => props.checkpoint.response !== null || props.checkpoint.responded_at !== null)
const isWaiting = computed(() => !isResponded.value)
const canSubmit = computed(() => !isSubmitting.value && !isResponded.value && (selectedOption.value || freeInput.value.trim()))

function selectOption(optionId: string) {
  if (isResponded.value) return
  selectedOption.value = selectedOption.value === optionId ? null : optionId
}

function submitDecision() {
  if (!canSubmit.value) return
  isSubmitting.value = true
  emit('respond', props.checkpoint.id, selectedOption.value, freeInput.value.trim())
}

watch(isResponded, (val) => {
  if (val) isSubmitting.value = false
})

const formattedTime = computed(() => {
  const date = new Date(props.checkpoint.created_at)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})

const respondedTime = computed(() => {
  if (!props.checkpoint.responded_at) return ''
  const date = new Date(props.checkpoint.responded_at)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})

const selectedLabel = computed(() => {
  if (!props.checkpoint.response) return ''
  const opt = props.checkpoint.options.find(o => o.id === props.checkpoint.response)
  return opt ? `${opt.id}. ${opt.label}` : props.checkpoint.response
})
</script>

<template>
  <div :class="['decision-card', { 'decision-card--waiting': isWaiting, 'decision-card--responded': isResponded }]">
    <!-- Header -->
    <div class="decision-card__header">
      <span class="decision-card__badge" :class="isWaiting ? 'badge--waiting' : 'badge--done'">
        {{ isWaiting ? '需要你的决策' : '已回答' }}
      </span>
      <span class="decision-card__time">{{ formattedTime }}</span>
    </div>

    <!-- Question -->
    <h4 class="decision-card__question">{{ checkpoint.question }}</h4>

    <!-- Context -->
    <p v-if="checkpoint.context" class="decision-card__context">{{ checkpoint.context }}</p>

    <!-- Options -->
    <div class="decision-card__options">
      <button
        v-for="option in checkpoint.options"
        :key="option.id"
        :class="[
          'decision-option',
          {
            'decision-option--selected': selectedOption === option.id || (isResponded && checkpoint.response === option.id),
            'decision-option--disabled': isResponded,
          },
        ]"
        :disabled="isResponded"
        @click="selectOption(option.id)"
      >
        <span class="decision-option__id">{{ option.id }}</span>
        <div class="decision-option__content">
          <span class="decision-option__label">{{ option.label }}</span>
          <span v-if="option.description" class="decision-option__desc">{{ option.description }}</span>
        </div>
      </button>
    </div>

    <!-- Free input (when allowed) -->
    <div v-if="checkpoint.allow_free_input && !isResponded" class="decision-card__free-input">
      <textarea
        v-model="freeInput"
        class="decision-card__textarea"
        placeholder="或者输入你的想法..."
        rows="2"
      />
    </div>

    <!-- Responded: show response text -->
    <div v-if="isResponded && checkpoint.response_text" class="decision-card__response-text">
      <span class="decision-card__response-label">补充说明:</span>
      {{ checkpoint.response_text }}
    </div>

    <!-- Submit button -->
    <div v-if="!isResponded" class="decision-card__footer">
      <button
        class="decision-card__submit"
        :disabled="!canSubmit"
        @click="submitDecision"
      >
        {{ isSubmitting ? '提交中...' : '提交决策' }}
      </button>
    </div>

    <!-- Responded footer -->
    <div v-if="isResponded" class="decision-card__responded-footer">
      <span class="decision-card__responded-choice">
        选择: {{ selectedLabel }}
      </span>
      <span v-if="respondedTime" class="decision-card__responded-time">
        {{ respondedTime }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.decision-card {
  border: 1.5px solid var(--chat-border, #e5e7eb);
  border-radius: var(--chat-radius-lg, 12px);
  padding: 16px 20px;
  background: var(--chat-card, #ffffff);
  max-width: min(560px, 100%);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.decision-card--waiting {
  border-color: #f59e0b;
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.1), 0 2px 8px rgba(245, 158, 11, 0.08);
  animation: decision-pulse 3s ease-in-out infinite;
}

.decision-card--responded {
  border-color: var(--chat-border, #e5e7eb);
  opacity: 0.85;
}

@keyframes decision-pulse {
  0%, 100% { box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.1), 0 2px 8px rgba(245, 158, 11, 0.08); }
  50% { box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2), 0 4px 12px rgba(245, 158, 11, 0.12); }
}

/* Header */
.decision-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.decision-card__badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.badge--waiting {
  background: #fef3c7;
  color: #b45309;
}

.badge--done {
  background: #d1fae5;
  color: #065f46;
}

.decision-card__time {
  font-size: 12px;
  color: var(--chat-muted, #6b7280);
}

/* Question */
.decision-card__question {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #111827);
  line-height: 1.4;
  margin: 0 0 6px 0;
}

/* Context */
.decision-card__context {
  font-size: 13px;
  color: var(--chat-muted-strong, #4b5563);
  line-height: 1.5;
  margin: 0 0 14px 0;
}

/* Options */
.decision-card__options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.decision-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border: 1.5px solid var(--chat-border, #e5e7eb);
  border-radius: var(--chat-radius-md, 8px);
  background: var(--chat-card, #ffffff);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
  width: 100%;
}

.decision-option:hover:not(:disabled) {
  border-color: var(--chat-border-hover, #9ca3af);
  background: var(--chat-bg-hover, #f3f4f6);
}

.decision-option--selected {
  border-color: var(--primary-color, #3b82f6);
  background: #eff6ff;
}

.decision-option--selected:hover:not(:disabled) {
  border-color: var(--primary-color, #3b82f6);
  background: #dbeafe;
}

.decision-option--disabled {
  cursor: default;
  opacity: 0.6;
}

.decision-option--disabled.decision-option--selected {
  opacity: 1;
  border-color: #10b981;
  background: #ecfdf5;
}

.decision-option__id {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--chat-secondary, #f3f4f6);
  font-size: 12px;
  font-weight: 600;
  color: var(--chat-muted-strong, #4b5563);
}

.decision-option--selected .decision-option__id {
  background: var(--primary-color, #3b82f6);
  color: white;
}

.decision-option--disabled.decision-option--selected .decision-option__id {
  background: #10b981;
}

.decision-option__content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.decision-option__label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #111827);
}

.decision-option__desc {
  font-size: 12px;
  color: var(--chat-muted, #6b7280);
  line-height: 1.4;
}

/* Free input */
.decision-card__free-input {
  margin-bottom: 12px;
}

.decision-card__textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--chat-border, #e5e7eb);
  border-radius: var(--chat-radius-md, 8px);
  font-size: 13px;
  font-family: inherit;
  line-height: 1.5;
  resize: vertical;
  min-height: 40px;
  transition: border-color 0.2s, box-shadow 0.2s;
  background: var(--chat-card, #ffffff);
  color: var(--text-primary, #111827);
}

.decision-card__textarea:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.decision-card__textarea::placeholder {
  color: var(--chat-muted, #6b7280);
}

/* Response text (after responded) */
.decision-card__response-text {
  font-size: 13px;
  color: var(--chat-muted-strong, #4b5563);
  padding: 8px 12px;
  background: var(--chat-bg, #f9fafb);
  border-radius: var(--chat-radius-md, 8px);
  margin-top: 8px;
  line-height: 1.5;
}

.decision-card__response-label {
  font-weight: 500;
  color: var(--chat-muted, #6b7280);
}

/* Footer */
.decision-card__footer {
  display: flex;
  justify-content: flex-end;
}

.decision-card__submit {
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 500;
  color: white;
  background: var(--primary-color, #3b82f6);
  border-radius: var(--chat-radius-md, 8px);
  transition: background 0.2s, opacity 0.2s;
}

.decision-card__submit:hover:not(:disabled) {
  background: #2563eb;
}

.decision-card__submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Responded footer */
.decision-card__responded-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--chat-border, #e5e7eb);
}

.decision-card__responded-choice {
  font-size: 12px;
  font-weight: 500;
  color: #10b981;
}

.decision-card__responded-time {
  font-size: 12px;
  color: var(--chat-muted, #6b7280);
}
</style>
