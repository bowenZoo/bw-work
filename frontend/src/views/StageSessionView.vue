<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const projectId = route.params.projectId as string
const sessionId = route.params.sessionId as string
const base = import.meta.env.VITE_API_BASE || ''

// State
const session = ref<any>(null)
const messages = ref<any[]>([])
const loading = ref(true)
const sending = ref(false)
const aiTyping = ref(false)
const generatingDoc = ref(false)
const inputText = ref('')
const generatedDoc = ref<any>(null)
const messagesEl = ref<HTMLElement | null>(null)

// WebSocket
let ws: WebSocket | null = null
let wsPingInterval: ReturnType<typeof setInterval> | null = null

const authHeader = computed(() => ({ Authorization: `Bearer ${userStore.accessToken}` }))

async function loadSession() {
  const res = await fetch(`${base}/api/sessions/${sessionId}`, { headers: authHeader.value })
  if (!res.ok) { router.push('/'); return }
  session.value = await res.json()
}

async function loadMessages() {
  const res = await fetch(`${base}/api/sessions/${sessionId}/messages`, { headers: authHeader.value })
  if (res.ok) messages.value = await res.json()
}

function connectWs() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ws/session/${sessionId}`
  ws = new WebSocket(wsUrl)

  ws.onmessage = (ev) => {
    try {
      const payload = JSON.parse(ev.data)
      handleWsEvent(payload)
    } catch {}
  }

  ws.onclose = () => {
    wsPingInterval && clearInterval(wsPingInterval)
  }

  wsPingInterval = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 20000)
}

function handleWsEvent(payload: any) {
  switch (payload.type) {
    case 'message':
      // Avoid duplicate if we already added via REST
      if (!messages.value.find((m) => m.id === payload.data.id)) {
        messages.value.push(payload.data)
      }
      aiTyping.value = false
      scrollToBottom()
      break
    case 'ai_typing':
      aiTyping.value = true
      scrollToBottom()
      break
    case 'generating_doc':
      generatingDoc.value = true
      break
    case 'doc_ready':
      generatingDoc.value = false
      generatedDoc.value = payload.data
      if (session.value) {
        session.value.status = 'closed'
        session.value.generated_doc_id = payload.data.document_id
      }
      break
    case 'session_closed':
      if (session.value) session.value.status = 'closed'
      break
  }
}

async function sendMessage() {
  if (!inputText.value.trim() || sending.value) return
  if (session.value?.status === 'closed') return

  const content = inputText.value.trim()
  inputText.value = ''
  sending.value = true

  try {
    const res = await fetch(`${base}/api/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { ...authHeader.value, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
    if (res.ok) {
      const msg = await res.json()
      // WS will deliver the message; add locally as fallback
      if (!messages.value.find((m) => m.id === msg.id)) {
        messages.value.push(msg)
      }
      scrollToBottom()
    }
  } finally {
    sending.value = false
  }
}

async function generateDoc() {
  if (generatingDoc.value) return
  generatingDoc.value = true
  try {
    const res = await fetch(`${base}/api/sessions/${sessionId}/generate-doc`, {
      method: 'POST',
      headers: authHeader.value,
    })
    if (res.ok) {
      const data = await res.json()
      generatedDoc.value = data
      if (session.value) session.value.status = 'closed'
    }
  } catch {
    generatingDoc.value = false
  }
}

function goToDoc() {
  if (generatedDoc.value?.document_id) {
    router.push(`/project/${projectId}/doc/${generatedDoc.value.document_id}`)
  } else if (session.value?.generated_doc_id) {
    router.push(`/project/${projectId}/doc/${session.value.generated_doc_id}`)
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) {
      messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    }
  })
}

function formatTime(dt: string) {
  if (!dt) return ''
  const d = new Date(dt)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function renderMarkdown(text: string) {
  return marked.parse(text || '') as string
}

onMounted(async () => {
  await Promise.all([loadSession(), loadMessages()])
  loading.value = false
  scrollToBottom()
  connectWs()
})

onUnmounted(() => {
  wsPingInterval && clearInterval(wsPingInterval)
  ws?.close()
})
</script>

<template>
  <div class="session-root">
    <!-- Header -->
    <div class="session-header">
      <button class="back-btn" @click="router.push(`/project/${projectId}`)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
        返回项目
      </button>
      <div class="header-info">
        <div class="header-title">{{ session?.title || '加载中...' }}</div>
        <div class="header-sub">AI 访谈</div>
      </div>
      <div class="header-status">
        <span class="status-badge" :class="session?.status === 'closed' ? 'status-closed' : 'status-active'">
          {{ session?.status === 'closed' ? '已结束' : '进行中' }}
        </span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="session-loading">加载中...</div>

    <template v-else>
      <!-- Messages -->
      <div class="messages-area" ref="messagesEl">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="msg-row"
          :class="msg.role === 'ai' ? 'msg-row-ai' : msg.role === 'user' ? 'msg-row-user' : 'msg-row-system'"
        >
          <!-- AI message -->
          <template v-if="msg.role === 'ai'">
            <div class="avatar avatar-ai">AI</div>
            <div class="bubble bubble-ai">
              <div class="bubble-sender">AI 主持人</div>
              <div class="bubble-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
              <div class="bubble-time">{{ formatTime(msg.created_at) }}</div>
            </div>
          </template>

          <!-- User message -->
          <template v-else-if="msg.role === 'user'">
            <div class="bubble bubble-user">
              <div class="bubble-sender">{{ msg.display_name || msg.username || '参与者' }}</div>
              <div class="bubble-content">{{ msg.content }}</div>
              <div class="bubble-time">{{ formatTime(msg.created_at) }}</div>
            </div>
            <div class="avatar avatar-user">
              {{ (msg.display_name || msg.username || '?').charAt(0).toUpperCase() }}
            </div>
          </template>

          <!-- System message -->
          <template v-else>
            <div class="system-msg">{{ msg.content }}</div>
          </template>
        </div>

        <!-- AI typing indicator -->
        <div v-if="aiTyping" class="msg-row msg-row-ai">
          <div class="avatar avatar-ai">AI</div>
          <div class="bubble bubble-ai bubble-typing">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>
      </div>

      <!-- Generated Doc Banner -->
      <div v-if="generatedDoc || session?.generated_doc_id" class="doc-banner">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span>文档已生成：{{ generatedDoc?.title || '阶段文档' }}</span>
        <button class="btn-doc-link" @click="goToDoc">查看文档 →</button>
      </div>

      <!-- Input Area -->
      <div class="input-area">
        <div v-if="session?.status === 'closed'" class="session-closed-notice">
          会话已结束
          <button v-if="session?.generated_doc_id || generatedDoc" class="btn-doc-link-sm" @click="goToDoc">查看生成的文档</button>
        </div>
        <template v-else>
          <div class="input-row">
            <textarea
              v-model="inputText"
              class="msg-input"
              placeholder="输入你的想法或回答..."
              rows="2"
              @keydown.meta.enter.prevent="sendMessage"
              @keydown.ctrl.enter.prevent="sendMessage"
            ></textarea>
            <button class="send-btn" @click="sendMessage" :disabled="sending || !inputText.trim()">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <div class="input-actions">
            <span class="input-hint">Ctrl+Enter 发送</span>
            <button
              class="gen-doc-btn"
              :disabled="generatingDoc"
              @click="generateDoc"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
              {{ generatingDoc ? 'AI 生成文档中...' : '生成阶段文档' }}
            </button>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.session-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8f8fa;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* Header */
.session-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}
.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}
.back-btn:hover { background: #f9fafb; }
.header-info { flex: 1; min-width: 0; }
.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-sub { font-size: 12px; color: #6b7280; margin-top: 2px; }
.status-badge {
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.status-active { background: #d1fae5; color: #065f46; }
.status-closed { background: #f3f4f6; color: #6b7280; }

/* Messages */
.session-loading { padding: 40px; text-align: center; color: #9ca3af; }
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.msg-row-ai { flex-direction: row; }
.msg-row-user { flex-direction: row-reverse; }
.msg-row-system { justify-content: center; }

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}
.avatar-ai { background: #7C3AED; color: #fff; }
.avatar-user { background: #3b82f6; color: #fff; }

.bubble {
  max-width: 68%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.bubble-ai {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 2px 12px 12px 12px;
}
.bubble-user {
  background: #7C3AED;
  color: #fff;
  border-radius: 12px 2px 12px 12px;
}
.bubble-sender {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 4px;
}
.bubble-user .bubble-sender { color: rgba(255,255,255,0.7); }
.bubble-content { word-break: break-word; }
.bubble-time {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 6px;
  text-align: right;
}
.bubble-user .bubble-time { color: rgba(255,255,255,0.6); }

/* Typing indicator */
.bubble-typing {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 14px;
  min-width: 60px;
}
.typing-dot {
  width: 8px;
  height: 8px;
  background: #9ca3af;
  border-radius: 50%;
  animation: typing 1.2s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-4px); }
}

/* System message */
.system-msg {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 13px;
}

/* Doc Banner */
.doc-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f0fdf4;
  border-top: 1px solid #bbf7d0;
  padding: 10px 20px;
  font-size: 14px;
  color: #065f46;
  flex-shrink: 0;
}
.btn-doc-link {
  margin-left: auto;
  padding: 4px 12px;
  background: #059669;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.btn-doc-link:hover { background: #047857; }

/* Input Area */
.input-area {
  background: #fff;
  border-top: 1px solid #e5e7eb;
  padding: 12px 20px;
  flex-shrink: 0;
}
.session-closed-notice {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #6b7280;
  font-size: 14px;
  padding: 8px 0;
}
.btn-doc-link-sm {
  padding: 4px 10px;
  background: #7C3AED;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.msg-input {
  flex: 1;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 14px;
  resize: none;
  font-family: inherit;
  outline: none;
  line-height: 1.5;
}
.msg-input:focus { border-color: #7C3AED; box-shadow: 0 0 0 2px rgba(124,58,237,0.1); }
.send-btn {
  width: 40px;
  height: 40px;
  background: #7C3AED;
  color: #fff;
  border: none;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.send-btn:hover { background: #6d28d9; }
.send-btn:disabled { background: #d1d5db; cursor: not-allowed; }
.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.input-hint { font-size: 12px; color: #9ca3af; }
.gen-doc-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid #7C3AED;
  border-radius: 8px;
  background: #fff;
  color: #7C3AED;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
}
.gen-doc-btn:hover { background: #f5f3ff; }
.gen-doc-btn:disabled { border-color: #e5e7eb; color: #9ca3af; cursor: not-allowed; }

/* Markdown */
:deep(.markdown-body) {
  font-size: 14px;
  line-height: 1.7;
}
:deep(.markdown-body p) { margin: 0 0 8px 0; }
:deep(.markdown-body p:last-child) { margin-bottom: 0; }
:deep(.markdown-body strong) { font-weight: 600; }
:deep(.markdown-body ul), :deep(.markdown-body ol) {
  padding-left: 18px;
  margin: 6px 0;
}
:deep(.markdown-body li) { margin: 2px 0; }
:deep(.markdown-body h1), :deep(.markdown-body h2), :deep(.markdown-body h3) {
  margin: 10px 0 6px;
  font-weight: 600;
  line-height: 1.4;
}
</style>
