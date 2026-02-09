<script setup lang="ts">
import { computed } from 'vue'
import type { Agent } from '@/types'
import { getAgentDisplayName, getAgentAvatar } from '@/utils/agents'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = withDefaults(defineProps<{
  speaker: Agent | null
  content: string
  isStreaming?: boolean
}>(), {
  isStreaming: false,
})

const displayName = computed(() => {
  if (!props.speaker) return ''
  return getAgentDisplayName(props.speaker.role)
})

const avatarUrl = computed(() => {
  if (!props.speaker) return ''
  return getAgentAvatar(props.speaker.role)
})

const roleIcon = computed(() => {
  if (!props.speaker) return '💬'
  return props.speaker.role === 'lead_planner' ? '👑' : '👤'
})

const renderedContent = computed(() => {
  if (!props.content) return ''
  try {
    const html = marked(props.content) as string
    return DOMPurify.sanitize(html)
  } catch {
    return props.content
  }
})

const hasContent = computed(() => {
  return props.content && props.content.trim().length > 0
})
</script>

<template>
  <div class="current-speech">
    <!-- Header -->
    <div class="speech-header">
      <span class="header-icon">💬</span>
      <span class="header-title">当前发言</span>
      <span v-if="isStreaming" class="streaming-indicator">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </span>
    </div>

    <!-- Content -->
    <div class="speech-content">
      <template v-if="speaker && hasContent">
        <!-- Speaker info -->
        <div class="speaker-info">
          <div class="speaker-avatar">
            <img
              v-if="avatarUrl"
              :src="avatarUrl"
              :alt="displayName"
              class="avatar-image"
            />
            <span v-else class="avatar-fallback">{{ roleIcon }}</span>
          </div>
          <span class="speaker-name">{{ displayName }}:</span>
        </div>

        <!-- Speech bubble -->
        <div class="speech-bubble">
          <div
            class="speech-text markdown-content"
            v-html="renderedContent"
          ></div>
          <span v-if="isStreaming" class="typing-cursor">|</span>
        </div>
      </template>

      <template v-else>
        <div class="no-speech">
          <span class="no-speech-icon">🎙️</span>
          <span class="no-speech-text">等待发言...</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.current-speech {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.speech-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
}

.header-icon {
  font-size: 16px;
}

.header-title {
  font-weight: 600;
  color: var(--text-primary);
}

.streaming-indicator {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.streaming-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-color);
  animation: bounce 1.4s infinite ease-in-out both;
}

.streaming-indicator .dot:nth-child(1) {
  animation-delay: -0.32s;
}

.streaming-indicator .dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.speech-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.speaker-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.speaker-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--bg-tertiary);
  border: 2px solid var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-fallback {
  font-size: 18px;
}

.speaker-name {
  font-weight: 600;
  font-size: 16px;
  color: var(--text-primary);
}

.speech-bubble {
  background: var(--bg-tertiary);
  border-radius: 8px;
  padding: 16px;
  position: relative;
}

.speech-bubble::before {
  content: '';
  position: absolute;
  top: -8px;
  left: 24px;
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-bottom: 8px solid var(--bg-tertiary);
}

.speech-text {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.7;
}

/* Markdown content styles */
.speech-text :deep(p) {
  margin: 0 0 12px;
}

.speech-text :deep(p:last-child) {
  margin-bottom: 0;
}

.speech-text :deep(h1),
.speech-text :deep(h2),
.speech-text :deep(h3),
.speech-text :deep(h4) {
  color: var(--text-primary);
  margin: 16px 0 8px;
}

.speech-text :deep(ul),
.speech-text :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.speech-text :deep(li) {
  margin: 4px 0;
}

.speech-text :deep(strong) {
  color: var(--primary-color);
}

.speech-text :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
}

.speech-text :deep(blockquote) {
  border-left: 3px solid var(--border-color);
  margin: 12px 0;
  padding-left: 12px;
  color: var(--text-secondary);
}

.typing-cursor {
  display: inline-block;
  color: var(--primary-color);
  animation: blink 1s step-end infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.no-speech {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
  color: var(--text-weak);
  gap: 12px;
}

.no-speech-icon {
  font-size: 48px;
  opacity: 0.4;
}

.no-speech-text {
  font-size: 14px;
}
</style>
