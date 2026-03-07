<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Send } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  discussionId: string
  disabled?: boolean
  isWaitingDecision?: boolean
}>(), {
  disabled: false,
  isWaitingDecision: false,
})

const emit = defineEmits<{
  send: [content: string]
}>()

const MAX_LENGTH = 500
const MAX_MESSAGES_PER_MINUTE = 3

const inputContent = ref('')
const lastSentTimes = ref<number[]>([])
const throttleMessage = ref<string | null>(null)

const charCount = computed(() => inputContent.value.length)
const isOverLimit = computed(() => charCount.value > MAX_LENGTH)

const isInputDisabled = computed(() => props.disabled || props.isWaitingDecision)

const placeholder = computed(() => {
  if (props.isWaitingDecision) return '等待决策中...'
  if (props.disabled) return '讨论未开始或已结束'
  return '制作人发言...'
})

const canSend = computed(() => {
  if (isInputDisabled.value) return false
  if (inputContent.value.trim().length === 0) return false
  if (isOverLimit.value) return false
  return checkThrottle()
})

function checkThrottle(): boolean {
  const now = Date.now()
  const validTimes = lastSentTimes.value.filter(t => now - t <= 60000)
  lastSentTimes.value = validTimes
  return validTimes.length < MAX_MESSAGES_PER_MINUTE
}

function getThrottleRemainingTime(): number {
  if (lastSentTimes.value.length < MAX_MESSAGES_PER_MINUTE) return 0
  const oldestTime = lastSentTimes.value[0]
  if (oldestTime === undefined) return 0
  const now = Date.now()
  const remaining = 60000 - (now - oldestTime)
  return Math.max(0, Math.ceil(remaining / 1000))
}

function handleSend() {
  if (!canSend.value) {
    const remaining = getThrottleRemainingTime()
    if (remaining > 0) {
      throttleMessage.value = `发言过于频繁，请等待 ${remaining} 秒`
      setTimeout(() => { throttleMessage.value = null }, 3000)
    }
    return
  }

  const content = inputContent.value.trim()
  if (!content) return

  lastSentTimes.value.push(Date.now())
  emit('send', content)
  inputContent.value = ''
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

watch(inputContent, () => { throttleMessage.value = null })

// 供外部填充文本（ProducerAssist 使用）
function fillText(text: string) {
  inputContent.value = text
}

// 供外部直接发送（ProducerAssist 点"发送"按钮）
function sendText(text: string) {
  inputContent.value = text
  handleSend()
}

defineExpose({ fillText, sendText })
</script>

<template>
  <div class="producer-input">
    <!-- Throttle warning -->
    <div v-if="throttleMessage" class="producer-input__throttle">
      {{ throttleMessage }}
    </div>

    <!-- Input area -->
    <div class="producer-input__row">
      <div class="producer-input__field">
        <textarea
          v-model="inputContent"
          :placeholder="placeholder"
          :disabled="isInputDisabled"
          class="producer-input__textarea"
          rows="2"
          @keydown="handleKeydown"
        />
        <span
          class="producer-input__count"
          :class="{ 'producer-input__count--over': isOverLimit }"
        >
          {{ charCount }}/{{ MAX_LENGTH }}
        </span>
      </div>

      <button
        class="producer-input__send"
        :disabled="!canSend"
        @click="handleSend"
      >
        <Send class="producer-input__send-icon" />
      </button>
    </div>

    <!-- Help text -->
    <div class="producer-input__hint">
      <template v-if="isInputDisabled && isWaitingDecision">
        请先回答待决策问题
      </template>
      <template v-else-if="isInputDisabled">
        讨论未开始或已结束，无法发送消息
      </template>
      <template v-else>
        按 Enter 发送，消息将由主策划消化处理
      </template>
    </div>
  </div>
</template>

<style scoped>
.producer-input {
  border-top: 1px solid var(--border-color, #e5e7eb);
  background: var(--chat-card, #ffffff);
  padding: 10px 16px;
}

/* Throttle warning */
.producer-input__throttle {
  margin-bottom: 8px;
  padding: 6px 10px;
  background: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 6px;
  color: #b45309;
  font-size: 12px;
}

/* Input row */
.producer-input__row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.producer-input__field {
  flex: 1;
  position: relative;
}

.producer-input__textarea {
  width: 100%;
  padding: 8px 50px 8px 12px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  color: var(--text-primary, #111827);
  background: var(--chat-card, #ffffff);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.producer-input__textarea:focus {
  outline: none;
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.producer-input__textarea:disabled {
  background: var(--chat-bg, #f9fafb);
  cursor: not-allowed;
  opacity: 0.6;
}

.producer-input__textarea::placeholder {
  color: var(--chat-muted, #6b7280);
}

/* Character count */
.producer-input__count {
  position: absolute;
  bottom: 6px;
  right: 10px;
  font-size: 11px;
  color: var(--chat-muted, #6b7280);
}

.producer-input__count--over {
  color: #ef4444;
}

/* Send button */
.producer-input__send {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--primary-color, #3b82f6);
  color: white;
  transition: background 0.2s, opacity 0.2s;
}

.producer-input__send:hover:not(:disabled) {
  background: #2563eb;
}

.producer-input__send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.producer-input__send-icon {
  width: 16px;
  height: 16px;
}

/* Hint */
.producer-input__hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--chat-muted, #6b7280);
}
</style>
