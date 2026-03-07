<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useUserStore } from '@/stores/user'

const props = defineProps<{
  discussionId: string
  active: boolean  // 是否在制作人轮次中（isProducerTurn || isWaitingDecision）
}>()

const emit = defineEmits<{
  fill: [text: string]    // 填入输入框
  send: [text: string]    // 直接发送
}>()

const userStore = useUserStore()

// ---- 数据类型 ----
interface QuestionItem {
  from_agent: string
  question: string
  answers: string[]
}

// ---- 状态 ----
const collapsed = ref(false)
const loading = ref(false)
const error = ref('')
const mode = ref<'questions' | 'general'>('general')
// 按问题展示的模式
const questions = ref<QuestionItem[]>([])
const selectedAnswers = ref<Record<number, number>>({})  // qIndex → answerIndex
// 通用建议模式（旧格式降级）
const suggestions = ref<{direction: string; style: string; text: string}[]>([])
const contextSummary = ref('')
const checkpointQuestion = ref('')
const source = ref<'llm' | 'heuristic'>('llm')

// 每次变为 active 时自动拉取建议
watch(() => props.active, (val) => {
  if (val && questions.value.length === 0 && suggestions.value.length === 0) fetchSuggestions()
}, { immediate: true })

async function fetchSuggestions() {
  if (!props.discussionId || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/discussions/${props.discussionId}/producer-assist`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    if (res.ok) {
      const data = await res.json()
      mode.value = data.mode === 'questions' ? 'questions' : 'general'
      contextSummary.value = data.context_summary || ''
      checkpointQuestion.value = data.checkpoint_question || ''
      source.value = data.source === 'heuristic' ? 'heuristic' : 'llm'

      if (mode.value === 'questions' && Array.isArray(data.questions)) {
        questions.value = data.questions
        // 默认每题选第一个选项
        const defaults: Record<number, number> = {}
        data.questions.forEach((_: QuestionItem, i: number) => { defaults[i] = 0 })
        selectedAnswers.value = defaults
        suggestions.value = []
      } else {
        suggestions.value = data.suggestions || []
        questions.value = []
        selectedAnswers.value = {}
      }
    } else {
      error.value = '获取建议失败'
    }
  } catch {
    error.value = '网络错误'
  } finally {
    loading.value = false
  }
}

function refresh() {
  questions.value = []
  suggestions.value = []
  selectedAnswers.value = {}
  fetchSuggestions()
}

// 拼合所有选中答案 → 发送
const composedMessage = computed(() => {
  if (mode.value !== 'questions' || questions.value.length === 0) return ''
  if (questions.value.length === 1) {
    // 单问题：直接返回答案
    const idx = selectedAnswers.value[0] ?? 0
    return questions.value[0].answers[idx] ?? ''
  }
  // 多问题：逐题拼合
  return questions.value.map((q, i) => {
    const idx = selectedAnswers.value[i] ?? 0
    const ans = q.answers[idx] ?? ''
    // 精简问题描述（最多20字）
    const qShort = q.question.length > 20 ? q.question.slice(0, 20) + '…' : q.question
    return `关于「${qShort}」：${ans}`
  }).join('\n\n')
})

function sendComposed() {
  const msg = composedMessage.value.trim()
  if (msg) emit('send', msg)
}

function fillComposed() {
  const msg = composedMessage.value.trim()
  if (msg) emit('fill', msg)
}

// 通用建议模式的操作
function useSuggestion(text: string) {
  emit('fill', text)
}
function sendSuggestion(text: string) {
  emit('send', text)
}

const STYLE_CONFIG: Record<string, { color: string; bg: string; icon: string }> = {
  assertive:    { color: '#dc2626', bg: '#fee2e2', icon: '⚡' },
  collaborative: { color: '#16a34a', bg: '#dcfce7', icon: '◎' },
  exploratory:  { color: '#2563eb', bg: '#dbeafe', icon: '?' },
}
</script>

<template>
  <div v-if="active" class="pa-wrap">
    <!-- 头部 -->
    <div class="pa-header" @click="collapsed = !collapsed">
      <div class="pa-header-left">
        <span class="pa-avatar">🎯</span>
        <span class="pa-title">超级制作人建议</span>
        <span v-if="source === 'heuristic'" class="pa-source-tag">快速模式</span>
        <span v-else class="pa-source-tag pa-source-ai">AI 生成</span>
      </div>
      <div class="pa-header-right">
        <button class="pa-refresh" @click.stop="refresh" :disabled="loading" title="刷新建议">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
        </button>
        <span class="pa-collapse-icon">{{ collapsed ? '▲' : '▼' }}</span>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="!collapsed && loading" class="pa-loading">
      <div class="pa-loading-dots"><span></span><span></span><span></span></div>
      正在生成建议...
    </div>

    <!-- 错误 -->
    <div v-else-if="!collapsed && error" class="pa-error">
      {{ error }}
      <button @click="refresh" class="pa-retry">重试</button>
    </div>

    <!-- === 模式 A：按问题展示 === -->
    <template v-else-if="!collapsed && mode === 'questions' && questions.length">
      <div class="pa-questions">
        <div v-for="(q, qi) in questions" :key="qi" class="pa-question-block">
          <!-- 问题标题 -->
          <div class="pa-q-header">
            <span class="pa-q-agent">{{ q.from_agent }}</span>
            <span class="pa-q-text">{{ q.question }}</span>
          </div>
          <!-- 答案选项 -->
          <div class="pa-answers">
            <button
              v-for="(ans, ai) in q.answers"
              :key="ai"
              class="pa-answer-btn"
              :class="{ 'pa-answer-selected': selectedAnswers[qi] === ai }"
              @click="selectedAnswers[qi] = ai"
            >
              <span class="pa-answer-radio">
                <span v-if="selectedAnswers[qi] === ai" class="pa-radio-dot"></span>
              </span>
              <span class="pa-answer-text">{{ ans }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 底部发送栏 -->
      <div class="pa-send-bar">
        <span class="pa-send-hint">已选 {{ questions.length }} 个问题的回答</span>
        <div class="pa-send-actions">
          <button class="pa-btn pa-btn-fill" @click="fillComposed">填入</button>
          <button class="pa-btn pa-btn-send" @click="sendComposed">发送回答</button>
        </div>
      </div>
    </template>

    <!-- === 模式 B：通用三方向建议（降级） === -->
    <template v-else-if="!collapsed && mode === 'general' && suggestions.length">
      <!-- checkpoint 问题提示 -->
      <div v-if="checkpointQuestion" class="pa-checkpoint-q">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
        待决策：{{ checkpointQuestion }}
      </div>
      <div class="pa-cards">
        <div
          v-for="s in suggestions"
          :key="s.direction"
          class="pa-card"
          :style="{ borderLeftColor: STYLE_CONFIG[s.style]?.color || '#6366f1' }"
        >
          <div class="pa-card-top">
            <span
              class="pa-direction"
              :style="{ background: STYLE_CONFIG[s.style]?.bg, color: STYLE_CONFIG[s.style]?.color }"
            >
              {{ STYLE_CONFIG[s.style]?.icon }} {{ s.direction }}
            </span>
            <div class="pa-card-actions">
              <button class="pa-btn pa-btn-fill" @click="useSuggestion(s.text)" title="填入输入框">填入</button>
              <button class="pa-btn pa-btn-send" @click="sendSuggestion(s.text)" title="直接发送">发送</button>
            </div>
          </div>
          <p class="pa-text">{{ s.text }}</p>
        </div>
      </div>
    </template>

    <!-- 上下文摘要 -->
    <div v-if="!collapsed && contextSummary" class="pa-context">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      {{ contextSummary }}
    </div>
  </div>
</template>

<style scoped>
.pa-wrap {
  border-top: 2px solid #6366f1;
  background: linear-gradient(180deg, #eef2ff 0%, #f9fafb 100%);
  flex-shrink: 0;
}

.pa-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  cursor: pointer;
  user-select: none;
}
.pa-header:hover { background: rgba(99,102,241,0.06); }

.pa-header-left { display: flex; align-items: center; gap: 6px; }
.pa-avatar { font-size: 14px; }
.pa-title { font-size: 12.5px; font-weight: 700; color: #4338ca; }
.pa-source-tag { font-size: 10px; background: #e0e7ff; color: #4f46e5; padding: 1px 6px; border-radius: 999px; }
.pa-source-ai { background: #f0fdf4; color: #16a34a; }

.pa-header-right { display: flex; align-items: center; gap: 8px; }
.pa-refresh {
  display: flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border-radius: 50%;
  background: none; border: 1px solid #c7d2fe;
  color: #6366f1; cursor: pointer; transition: all 0.15s;
}
.pa-refresh:hover:not(:disabled) { background: #e0e7ff; }
.pa-refresh:disabled { opacity: 0.4; cursor: not-allowed; }
.pa-collapse-icon { font-size: 10px; color: #9ca3af; }

/* 加载 */
.pa-loading {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 14px; font-size: 12px; color: #6b7280;
}
.pa-loading-dots { display: flex; gap: 4px; }
.pa-loading-dots span {
  width: 5px; height: 5px; border-radius: 50%; background: #6366f1;
  animation: dot-bounce 1.2s infinite ease-in-out;
}
.pa-loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.pa-loading-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 错误 */
.pa-error {
  padding: 8px 14px; font-size: 12px; color: #dc2626;
  display: flex; align-items: center; gap: 8px;
}
.pa-retry {
  font-size: 11px; color: #6366f1; background: none; border: 1px solid #a5b4fc;
  border-radius: 4px; padding: 1px 8px; cursor: pointer;
}

/* ============ 问题模式 ============ */
.pa-questions {
  display: flex; flex-direction: column; gap: 8px;
  padding: 4px 14px 6px;
  max-height: 320px; overflow-y: auto;
}

.pa-question-block {
  background: white; border-radius: 8px;
  border: 1px solid #e0e7ff; overflow: hidden;
}

.pa-q-header {
  display: flex; align-items: baseline; gap: 6px;
  padding: 7px 10px 5px;
  background: #f5f3ff;
  border-bottom: 1px solid #e0e7ff;
}
.pa-q-agent {
  font-size: 10px; font-weight: 700; color: #7c3aed;
  background: #ede9fe; padding: 1px 6px; border-radius: 999px;
  white-space: nowrap; flex-shrink: 0;
}
.pa-q-text {
  font-size: 12px; color: #374151; line-height: 1.4; font-weight: 500;
}

.pa-answers {
  display: flex; flex-direction: column; gap: 0;
}
.pa-answer-btn {
  display: flex; align-items: flex-start; gap: 8px;
  width: 100%; text-align: left;
  padding: 8px 10px;
  background: white; border: none; border-top: 1px solid #f3f4f6;
  cursor: pointer; transition: background 0.12s;
}
.pa-answer-btn:first-child { border-top: none; }
.pa-answer-btn:hover { background: #f5f3ff; }
.pa-answer-btn.pa-answer-selected { background: #eef2ff; }

.pa-answer-radio {
  flex-shrink: 0; width: 14px; height: 14px; margin-top: 2px;
  border: 1.5px solid #a5b4fc; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  transition: border-color 0.12s;
}
.pa-answer-selected .pa-answer-radio { border-color: #6366f1; }
.pa-radio-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #6366f1;
}
.pa-answer-text {
  font-size: 12.5px; color: #1e293b; line-height: 1.5;
}
.pa-answer-selected .pa-answer-text { color: #3730a3; }

/* 底部发送栏 */
.pa-send-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid #e0e7ff;
  background: #f5f3ff;
}
.pa-send-hint { font-size: 11px; color: #7c3aed; }
.pa-send-actions { display: flex; gap: 6px; }

/* ============ 通用建议模式 ============ */
.pa-checkpoint-q {
  display: flex; align-items: flex-start; gap: 5px;
  margin: 0 14px 6px;
  padding: 6px 10px;
  background: #fef3c7; border: 1px solid #fde68a; border-radius: 6px;
  font-size: 11.5px; color: #92400e; line-height: 1.4;
}

.pa-cards {
  display: flex; flex-direction: column; gap: 6px;
  padding: 4px 14px 8px;
}
.pa-card {
  background: white; border-radius: 8px; padding: 8px 10px;
  border: 1px solid #e5e7eb; border-left-width: 3px;
  transition: box-shadow 0.15s;
}
.pa-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.07); }

.pa-card-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 5px;
}
.pa-direction {
  font-size: 10.5px; font-weight: 700;
  padding: 2px 8px; border-radius: 999px;
}
.pa-card-actions { display: flex; gap: 4px; }

.pa-text {
  font-size: 13px; color: #1e293b; line-height: 1.55;
  margin: 0;
}

/* 共用按钮 */
.pa-btn {
  font-size: 11px; font-weight: 600;
  padding: 2px 10px; border-radius: 5px;
  cursor: pointer; transition: all 0.12s;
}
.pa-btn-fill {
  background: white; color: #6366f1;
  border: 1.5px solid #a5b4fc;
}
.pa-btn-fill:hover { background: #eef2ff; }
.pa-btn-send {
  background: #6366f1; color: white; border: none;
}
.pa-btn-send:hover { background: #4f46e5; }

/* 摘要 */
.pa-context {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 14px 8px;
  font-size: 11px; color: #9ca3af;
}
</style>
