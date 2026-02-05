<script setup lang="ts">
import { computed, ref } from 'vue';
import type { Message } from '@/types';
import { useAgentsStore } from '@/stores';
import { normalizeAgentRole } from '@/utils/agents';
import { toSanitizedMarkdownHtml } from '@/utils/markdown';

const props = defineProps<{
  message: Message;
  isStreaming?: boolean;
}>();

const agentsStore = useAgentsStore();
const copied = ref(false);

const normalizedRole = computed(() => normalizeAgentRole(props.message.agentRole));

// Get agent info based on role
const agent = computed(() => {
  const role = normalizedRole.value ?? props.message.agentRole;
  return role ? agentsStore.getAgentByRole(role) : undefined;
});

const displayName = computed(() => agent.value?.name ?? props.message.agentRole ?? 'Unknown');

// Format timestamp
const formattedTime = computed(() => {
  const date = new Date(props.message.timestamp);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
});

// Get avatar initial
const avatarInitial = computed(() => {
  return displayName.value.charAt(0) ?? '?';
});

// Get role class for styling
const roleClass = computed(() => normalizedRole.value ?? 'other');

// Render markdown content
const htmlContent = computed(() => {
  return toSanitizedMarkdownHtml(props.message.content);
});

// Copy message content
async function copyMessage() {
  try {
    await navigator.clipboard.writeText(props.message.content);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch (err) {
    console.error('Failed to copy:', err);
  }
}
</script>

<template>
  <div :class="['chat-group', roleClass]">
    <!-- Avatar -->
    <div :class="['chat-avatar', roleClass]">
      <img
        v-if="agent?.avatarUrl"
        :src="agent.avatarUrl"
        :alt="displayName"
        class="chat-avatar"
      />
      <span v-else>{{ avatarInitial }}</span>
    </div>

    <!-- Messages -->
    <div class="chat-group-messages">
      <!-- Message bubble -->
      <div
        :class="[
          'chat-bubble',
          'has-copy',
          'fade-in',
          { streaming: isStreaming },
        ]"
      >
        <!-- Copy button -->
        <button
          :class="['chat-copy-btn', { copied }]"
          @click="copyMessage"
          :title="copied ? '已复制' : '复制'"
        >
          <svg
            v-if="!copied"
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          <svg
            v-else
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </button>

        <!-- Content with markdown -->
        <div class="chat-text" v-html="htmlContent" />
      </div>

      <!-- Footer -->
      <div class="chat-group-footer">
        <span class="chat-sender-name">{{ displayName }}</span>
        <span class="chat-group-timestamp">{{ formattedTime }}</span>
      </div>
    </div>
  </div>
</template>
