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
  if (!props.speaker) return 'chat'
  return props.speaker.role === 'lead_planner' ? 'star' : 'user'
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
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>
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
            <span v-else class="avatar-fallback">
              <svg v-if="roleIcon === 'star'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </span>
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
          <svg class="no-speech-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
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
  color: var(--text-secondary);
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
  opacity: 0.4;
  color: var(--text-weak);
}

.no-speech-text {
  font-size: 14px;
}
</style>
