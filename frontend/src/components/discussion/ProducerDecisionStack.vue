<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useUserStore } from '@/stores/user'

const props = defineProps<{
  discussionId: string
  active: boolean
  pendingCheckpoint: { id: string; question: string } | null
  messagesCount?: number
  questionTrigger?: number  // increments when @超级制作人 questions arrive via WebSocket
}>()

const emit = defineEmits<{
  send: [text: string]
  respondCheckpoint: [id: string, text: string]
}>()

const userStore = useUserStore()

interface QuestionItem {
  from_agent: string
  question: string
  answers: string[]
}

// ── State ──
const loading = ref(false)
const error = ref('')
const questions = ref<QuestionItem[]>([])
const currentIndex = ref(0)
const selectedAnswer = ref(0)
const customInput = ref('')
const useCustom = ref(false)
const completed = ref<{ question: string; answer: string }[]>([])
const contextSummary = ref('')
const source = ref<'llm' | 'heuristic'>('llm')
const autoDeciding = ref(false)

const MAX_RETRIES = 3
const RETRY_DELAY_MS = 5000

// Only fetch when explicitly triggered:
// 1. active flag turns true (producer's explicit turn)
watch(() => props.active, (val) => {
  if (val) {
    // Only fetch if questions haven't already been loaded by questionTrigger.
    // Both questionTrigger and active fire when @超级制作人 is detected —
    // questionTrigger fires first (from WS message), active fires a moment
    // later (when discussion state flips to PAUSED). A second resetAndFetch()
    // would pop an already-empty queue and overwrite the correct card.
    if (questions.value.length === 0 && !loading.value) {
      resetAndFetch()
    }
  } else {
    // Waiting period ended — clear stale card
    resetState()
  }
}, { immediate: true })

// 2. @超级制作人 question arrives via WebSocket
watch(() => props.questionTrigger, (val) => {
  if (val !== undefined && val > 0) {
    resetAndFetch()
  }
})

function resetState() {
  questions.value = []
  currentIndex.value = 0
  selectedAnswer.value = 0
  customInput.value = ''
  useCustom.value = false
  completed.value = []
}

async function resetAndFetch() {
  resetState()
  await fetchCards()
}

async function _doFetch(attempt: number, refreshQuestions?: QuestionItem[]): Promise<void> {
  try {
    const body: Record<string, unknown> = {}
    if (refreshQuestions && refreshQuestions.length > 0) {
      body.refresh_questions = refreshQuestions.map(q => ({
        from_agent: q.from_agent,
        question: q.question,
      }))
    }
    const res = await fetch(`/api/discussions/${props.discussionId}/producer-assist`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userStore.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) { error.value = '获取建议失败'; return }
    const data = await res.json()

    if (data.mode === 'questions' && Array.isArray(data.questions) && data.questions.length) {
      // LLM fallback returned empty answers — retry silently
      const hasEmptyAnswers = data.source === 'heuristic' &&
        data.questions.some((q: QuestionItem) => q.answers.length === 0)
      if (hasEmptyAnswers && attempt < MAX_RETRIES) {
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS))
        return _doFetch(attempt + 1, refreshQuestions)
      }
      questions.value = data.questions
      contextSummary.value = data.context_summary || ''
      source.value = data.source === 'heuristic' ? 'heuristic' : 'llm'
    } else if (Array.isArray(data.suggestions) && data.suggestions.length) {
      // General mode — wrap suggestions as a single-question card
      questions.value = [{
        from_agent: '讨论助手',
        question: '你现在想表达什么？',
        answers: data.suggestions.map((s: { text: string }) => s.text),
      }]
      contextSummary.value = data.context_summary || ''
      source.value = 'llm'
    } else if (props.pendingCheckpoint) {
      questions.value = [{
        from_agent: '主策划',
        question: props.pendingCheckpoint.question,
        answers: [],
      }]
    }
  } catch {
    error.value = '网络错误'
  }
}

async function fetchCards(refreshQuestions?: QuestionItem[]) {
  if (!props.discussionId || loading.value) return
  loading.value = true
  error.value = ''
  try {
    await _doFetch(0, refreshQuestions)
  } finally {
    loading.value = false
  }
}

const currentCard = computed(() => questions.value[currentIndex.value] ?? null)
const totalCards = computed(() => questions.value.length)
const isLastCard = computed(() => currentIndex.value >= totalCards.value - 1)

// 无预设选项时（开放式问题）自动展开自定义输入
watch(currentCard, (card) => {
  if (card && card.answers.length === 0) useCustom.value = true
}, { immediate: true })

function getCurrentAnswer(): string {
  if (useCustom.value) return customInput.value.trim()
  return currentCard.value?.answers[selectedAnswer.value] ?? ''
}

const canSubmit = computed(() => {
  if (useCustom.value) return customInput.value.trim().length > 0
  return (currentCard.value?.answers.length ?? 0) > 0
})

function submitCurrent() {
  const answer = getCurrentAnswer()
  if (!answer) return
  completed.value.push({ question: currentCard.value!.question, answer })

  if (isLastCard.value) {
    sendAll()
  } else {
    currentIndex.value++
    selectedAnswer.value = 0
    customInput.value = ''
    useCustom.value = false
  }
}

function buildMessage(answers: { question: string; answer: string }[]): string {
  if (answers.length === 1) return answers[0].answer
  return answers.map(a => {
    const q = a.question.length > 28 ? a.question.slice(0, 28) + '…' : a.question
    return `关于「${q}」：${a.answer}`
  }).join('\n\n')
}

function sendAll() {
  const msg = buildMessage(completed.value)
  if (props.pendingCheckpoint) {
    emit('respondCheckpoint', props.pendingCheckpoint.id, msg)
  } else {
    emit('send', msg)
  }
  resetState()
}

async function autoDecide() {
  autoDeciding.value = true
  // Pick first option for each remaining card
  const remaining = questions.value.slice(currentIndex.value)
  for (const q of remaining) {
    completed.value.push({
      question: q.question,
      answer: q.answers[0] ?? '同意，按最优方案推进',
    })
  }
  sendAll()
  autoDeciding.value = false
}

function refresh() {
  if (questions.value.length > 0) {
    // 保留当前问题，仅重新生成答案选项
    const currentQuestions = [...questions.value]
    selectedAnswer.value = 0
    customInput.value = ''
    useCustom.value = false
    fetchCards(currentQuestions)
  } else {
    resetAndFetch()
  }
}

// Stack visual: how many shadow cards to show (max 2)
const shadowCount = computed(() => Math.min(totalCards.value - currentIndex.value - 1, 2))
</script>

<template>
  <div class="pds-wrap">

    <!-- Loading -->
    <div v-if="loading" class="pds-loading">
      <div class="pds-dots"><span/><span/><span/></div>
      <span>超级制作人正在分析问题...</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="pds-error">
      {{ error }}
      <button class="pds-retry" @click="refresh">重试</button>
    </div>

    <!-- Empty: compact idle state -->
    <div v-else-if="!loading && questions.length === 0" class="pds-idle">
      <div class="pds-idle-inner">
        <span class="pds-idle-icon">🤖</span>
        <span class="pds-idle-label">超级制作人监控中</span>
        <button class="pds-idle-refresh" @click="refresh" title="立即检查是否有需要决策的问题">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Card Stack -->
    <div v-else class="pds-stack-area">
      <!-- Header: counter + agent + refresh -->
      <div class="pds-stack-header">
        <div class="pds-counter">
          <span class="pds-counter-cur">{{ currentIndex + 1 }}</span>
          <span class="pds-counter-sep">/</span>
          <span class="pds-counter-tot">{{ totalCards }}</span>
          <span class="pds-counter-label">张决策卡</span>
        </div>
        <div class="pds-header-right">
          <span v-if="source === 'heuristic'" class="pds-mode-tag">快速模式</span>
          <span v-else class="pds-mode-tag pds-mode-ai">AI 生成</span>
          <button class="pds-icon-btn" @click="refresh" :disabled="loading" title="重新生成">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Card with stack shadow -->
      <div class="pds-card-container">
        <!-- Shadow cards (visual depth) -->
        <div v-if="shadowCount >= 2" class="pds-shadow pds-shadow-3" />
        <div v-if="shadowCount >= 1" class="pds-shadow pds-shadow-2" />

        <!-- Main card -->
        <div class="pds-card">
          <!-- Agent label -->
          <div class="pds-agent-row">
            <span class="pds-agent-tag">{{ currentCard?.from_agent }}</span>
            <span class="pds-agent-label">向你提问</span>
          </div>

          <!-- Question -->
          <div class="pds-question">{{ currentCard?.question }}</div>

          <!-- Heuristic fallback notice -->
          <div v-if="source === 'heuristic'" class="pds-heuristic-notice">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            AI 未能生成具体选项，以下为通用答案
            <button class="pds-heuristic-retry" @click.stop="refresh" :disabled="loading">重新生成</button>
          </div>

          <!-- Answer options -->
          <div v-if="currentCard?.answers.length" class="pds-options">
            <button
              v-for="(ans, ai) in currentCard.answers"
              :key="ai"
              class="pds-option"
              :class="{ 'pds-option-selected': !useCustom && selectedAnswer === ai }"
              @click="() => { useCustom = false; selectedAnswer = ai }"
            >
              <span class="pds-radio">
                <span v-if="!useCustom && selectedAnswer === ai" class="pds-radio-dot" />
              </span>
              <span class="pds-option-text">{{ ans }}</span>
            </button>
          </div>

          <!-- Custom input toggle + input -->
          <div class="pds-custom-section">
            <button
              class="pds-custom-toggle"
              :class="{ 'pds-custom-active': useCustom }"
              @click="useCustom = !useCustom"
            >
              <span class="pds-radio">
                <span v-if="useCustom" class="pds-radio-dot" />
              </span>
              <span>自定义回答</span>
            </button>
            <textarea
              v-if="useCustom"
              v-model="customInput"
              class="pds-textarea"
              placeholder="输入你的想法..."
              rows="3"
              @focus="useCustom = true"
            />
          </div>

          <!-- Actions -->
          <div class="pds-actions">
            <button
              class="pds-btn-auto"
              @click="autoDecide"
              :disabled="autoDeciding"
              title="让超级制作人自动完成所有决策"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
              </svg>
              超级制作人自主决策
            </button>
            <button
              class="pds-btn-submit"
              @click="submitCurrent"
              :disabled="!canSubmit"
            >
              {{ isLastCard ? '完成并发送' : '提交，下一张 →' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Progress dots -->
      <div class="pds-progress-dots" v-if="totalCards > 1">
        <span
          v-for="i in totalCards"
          :key="i"
          class="pds-dot"
          :class="{
            'pds-dot-done': i - 1 < currentIndex,
            'pds-dot-current': i - 1 === currentIndex,
          }"
        />
      </div>

      <!-- Context summary -->
      <div v-if="contextSummary" class="pds-context">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        {{ contextSummary }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.pds-wrap {
  display: flex;
  flex-direction: column;
  padding: 10px 14px 8px;
  overflow-y: auto;
}

/* Compact idle state */
.pds-idle {
  padding: 0;
}
.pds-idle-inner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px;
  background: #f8f7ff;
  border: 1px solid #e0e7ff;
  border-radius: 7px;
}
.pds-idle-icon { font-size: 13px; line-height: 1; }
.pds-idle-label {
  flex: 1;
  font-size: 11.5px;
  color: #6b7280;
}
.pds-idle-refresh {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%;
  background: none; border: 1px solid #c7d2fe; color: #6366f1;
  cursor: pointer; transition: background 0.12s; flex-shrink: 0;
}
.pds-idle-refresh:hover { background: #e0e7ff; }

/* Loading */
.pds-loading {
  display: flex; align-items: center; gap: 10px;
  padding: 24px 0; font-size: 13px; color: #6b7280;
}
.pds-dots { display: flex; gap: 4px; }
.pds-dots span {
  width: 6px; height: 6px; border-radius: 50%; background: #6366f1;
  animation: dot-pop 1.2s infinite ease-in-out;
}
.pds-dots span:nth-child(2) { animation-delay: 0.2s; }
.pds-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-pop {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* Error */
.pds-error {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 0; font-size: 13px; color: #dc2626;
}
.pds-retry {
  font-size: 11px; padding: 2px 10px; border-radius: 5px;
  border: 1px solid #fca5a5; background: white; color: #dc2626; cursor: pointer;
}

/* Stack area */
.pds-stack-area {
  display: flex; flex-direction: column; gap: 12px;
}

/* Header */
.pds-stack-header {
  display: flex; align-items: center; justify-content: space-between;
}
.pds-counter {
  display: flex; align-items: baseline; gap: 2px;
}
.pds-counter-cur { font-size: 20px; font-weight: 800; color: #4f46e5; line-height: 1; }
.pds-counter-sep { font-size: 13px; color: #9ca3af; margin: 0 1px; }
.pds-counter-tot { font-size: 13px; color: #9ca3af; }
.pds-counter-label { font-size: 11px; color: #9ca3af; margin-left: 4px; }
.pds-header-right { display: flex; align-items: center; gap: 6px; }
.pds-mode-tag {
  font-size: 10px; padding: 1px 6px; border-radius: 999px;
  background: #e0e7ff; color: #4f46e5;
}
.pds-mode-ai { background: #f0fdf4; color: #16a34a; }
.pds-icon-btn {
  display: flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border-radius: 50%;
  background: none; border: 1px solid #c7d2fe; color: #6366f1;
  cursor: pointer; transition: background 0.12s;
}
.pds-icon-btn:hover:not(:disabled) { background: #e0e7ff; }
.pds-icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Card container with stack effect */
.pds-card-container {
  position: relative;
  margin-bottom: 12px;
}
.pds-shadow {
  position: absolute;
  border-radius: 12px;
  border: 1px solid #c7d2fe;
}
.pds-shadow-2 {
  top: 8px; left: 6px; right: -6px; bottom: -8px;
  background: #eef2ff; z-index: 0;
}
.pds-shadow-3 {
  top: 16px; left: 12px; right: -12px; bottom: -16px;
  background: #e0e7ff; z-index: -1;
}

/* Main card */
.pds-card {
  position: relative; z-index: 1;
  background: white;
  border-radius: 12px;
  border: 1.5px solid #a5b4fc;
  box-shadow: 0 2px 12px rgba(99,102,241,0.1);
  padding: 14px 14px 12px;
  display: flex; flex-direction: column; gap: 10px;
}

.pds-agent-row {
  display: flex; align-items: center; gap: 6px;
}
.pds-agent-tag {
  font-size: 11px; font-weight: 700; color: #4f46e5;
  background: #ede9fe; padding: 2px 8px; border-radius: 999px;
}
.pds-agent-label { font-size: 11px; color: #9ca3af; }

.pds-question {
  font-size: 14px; font-weight: 600; color: #111827; line-height: 1.5;
}

.pds-options {
  display: flex; flex-direction: column; gap: 0;
  border-radius: 8px; border: 1px solid #e5e7eb; overflow: hidden;
}
.pds-option {
  display: flex; align-items: flex-start; gap: 8px;
  width: 100%; text-align: left; padding: 9px 10px;
  background: white; border: none; border-top: 1px solid #f3f4f6;
  cursor: pointer; transition: background 0.1s;
}
.pds-option:first-child { border-top: none; }
.pds-option:hover { background: #f5f3ff; }
.pds-option-selected { background: #eef2ff !important; }

.pds-radio {
  flex-shrink: 0; width: 15px; height: 15px; margin-top: 2px;
  border-radius: 50%; border: 1.5px solid #a5b4fc;
  display: flex; align-items: center; justify-content: center;
  transition: border-color 0.1s;
}
.pds-option-selected .pds-radio, .pds-custom-active .pds-radio { border-color: #6366f1; }
.pds-radio-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #6366f1;
}
.pds-option-text {
  font-size: 12.5px; color: #1e293b; line-height: 1.5;
}
.pds-option-selected .pds-option-text { color: #3730a3; }

.pds-custom-section {
  display: flex; flex-direction: column; gap: 6px;
}
.pds-custom-toggle {
  display: flex; align-items: center; gap: 8px;
  width: 100%; text-align: left; padding: 6px 4px;
  background: none; border: none; cursor: pointer;
  font-size: 12px; color: #6b7280; transition: color 0.1s;
}
.pds-custom-toggle:hover { color: #4f46e5; }
.pds-custom-active { color: #4f46e5 !important; }
.pds-textarea {
  width: 100%; padding: 8px 10px; border-radius: 7px;
  border: 1.5px solid #a5b4fc; background: #f5f3ff;
  font-size: 13px; color: #1e293b; resize: vertical;
  outline: none; transition: border-color 0.1s;
  font-family: inherit; line-height: 1.5;
}
.pds-textarea:focus { border-color: #6366f1; }

/* Actions */
.pds-actions {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding-top: 4px;
}
.pds-btn-auto {
  display: flex; align-items: center; gap: 5px;
  font-size: 11.5px; font-weight: 500; color: #6b7280;
  background: none; border: 1px solid #e5e7eb; border-radius: 6px;
  padding: 4px 10px; cursor: pointer; transition: all 0.12s;
}
.pds-btn-auto:hover:not(:disabled) { border-color: #a5b4fc; color: #4f46e5; background: #eef2ff; }
.pds-btn-auto:disabled { opacity: 0.4; cursor: not-allowed; }
.pds-btn-submit {
  font-size: 12.5px; font-weight: 700;
  padding: 6px 16px; border-radius: 7px;
  background: #6366f1; color: white; border: none;
  cursor: pointer; transition: background 0.12s;
}
.pds-btn-submit:hover:not(:disabled) { background: #4f46e5; }
.pds-btn-submit:disabled { opacity: 0.4; cursor: not-allowed; }

/* Progress dots */
.pds-progress-dots {
  display: flex; justify-content: center; gap: 6px;
}
.pds-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #e0e7ff; transition: all 0.2s;
}
.pds-dot-done { background: #a5b4fc; }
.pds-dot-current { background: #6366f1; transform: scale(1.3); }

/* Heuristic fallback notice */
.pds-heuristic-notice {
  display: flex; align-items: center; gap: 5px;
  padding: 5px 8px;
  background: #fef9c3; border: 1px solid #fde047; border-radius: 6px;
  font-size: 11.5px; color: #854d0e; line-height: 1.4;
}
.pds-heuristic-retry {
  margin-left: auto; flex-shrink: 0;
  font-size: 11px; font-weight: 600; color: #92400e;
  background: white; border: 1px solid #fbbf24; border-radius: 4px;
  padding: 1px 8px; cursor: pointer; transition: background 0.12s;
}
.pds-heuristic-retry:hover:not(:disabled) { background: #fef3c7; }
.pds-heuristic-retry:disabled { opacity: 0.5; cursor: not-allowed; }

/* Context */
.pds-context {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; color: #9ca3af;
}
</style>
