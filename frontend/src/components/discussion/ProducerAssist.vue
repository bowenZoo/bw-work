<script setup lang="ts">
import { ref, watch } from 'vue'
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

// ---- 状态 ----
const collapsed = ref(false)
const loading = ref(false)
const error = ref('')
const suggestions = ref<{direction: string; style: string; text: string}[]>([])
const contextSummary = ref('')
const checkpointQuestion = ref('')
const source = ref<'llm' | 'heuristic'>('llm')

// 每次变为 active 时自动拉取建议
watch(() => props.active, (val) => {
  if (val && suggestions.value.length === 0) fetchSuggestions()
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
      suggestions.value = data.suggestions || []
      contextSummary.value = data.context_summary || ''
      checkpointQuestion.value = data.checkpoint_question || ''
      source.value = data.source === 'heuristic' ? 'heuristic' : 'llm'
    } else {
      error.value = '获取建议失败'
    }
  } catch {
    error.value = '网络错误'
  } finally {
    loading.value = false
  }
}

function useSuggestion(text: string) {
  emit('fill', text)
}

function sendSuggestion(text: string) {
  emit('send', text)
}

function refresh() {
  suggestions.value = []
  fetchSuggestions()
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

    <!-- 当前问题提示 -->
    <div v-if="!collapsed && checkpointQuestion" class="pa-question">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
      待决策：{{ checkpointQuestion }}
    </div>

    <!-- 加载中 -->
    <div v-if="!collapsed && loading" class="pa-loading">
      <div class="pa-loading-dots"><span></span><span></span><span></span></div>
      正在生成发言建议...
    </div>

    <!-- 错误 -->
    <div v-else-if="!collapsed && error" class="pa-error">
      {{ error }}
      <button @click="refresh" class="pa-retry">重试</button>
    </div>

    <!-- 建议卡片 -->
    <div v-else-if="!collapsed && suggestions.length" class="pa-cards">
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
            <button class="pa-btn pa-btn-fill" @click="useSuggestion(s.text)" title="填入输入框">
              填入
            </button>
            <button class="pa-btn pa-btn-send" @click="sendSuggestion(s.text)" title="直接发送">
              发送
            </button>
          </div>
        </div>
        <p class="pa-text">{{ s.text }}</p>
      </div>
    </div>

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

.pa-question {
  display: flex; align-items: flex-start; gap: 5px;
  margin: 0 14px 6px;
  padding: 6px 10px;
  background: #fef3c7; border: 1px solid #fde68a; border-radius: 6px;
  font-size: 11.5px; color: #92400e; line-height: 1.4;
}

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

.pa-error {
  padding: 8px 14px; font-size: 12px; color: #dc2626;
  display: flex; align-items: center; gap: 8px;
}
.pa-retry {
  font-size: 11px; color: #6366f1; background: none; border: 1px solid #a5b4fc;
  border-radius: 4px; padding: 1px 8px; cursor: pointer;
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

.pa-text {
  font-size: 13px; color: #1e293b; line-height: 1.55;
  margin: 0;
}

.pa-context {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 14px 8px;
  font-size: 11px; color: #9ca3af;
}
</style>
