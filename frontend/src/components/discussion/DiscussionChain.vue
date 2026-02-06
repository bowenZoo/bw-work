<script setup lang="ts">
import { computed } from 'vue';
import type { DiscussionChainItem } from '@/types';

interface Props {
  chain: DiscussionChainItem[];
  currentIndex: number;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  select: [discussionId: string];
}>();

// Format chain item label
const chainLabels = computed(() => {
  return props.chain.map((item, index) => {
    if (item.is_origin) {
      return '[原]';
    }
    return `[续${index}]`;
  });
});

// Get truncated topic
function getTruncatedTopic(topic: string, maxLength: number = 20): string {
  // Remove [继续] prefix if present
  const cleanTopic = topic.replace(/^\[继续\]\s*/, '').replace(/\s*-\s*.+$/, '');
  if (cleanTopic.length <= maxLength) return cleanTopic;
  return cleanTopic.slice(0, maxLength) + '...';
}

// Handle item click
function handleItemClick(item: DiscussionChainItem, index: number) {
  if (index !== props.currentIndex) {
    emit('select', item.id);
  }
}
</script>

<template>
  <div v-if="chain.length > 1" class="discussion-chain">
    <span class="chain-label">讨论链：</span>
    <div class="chain-items">
      <template v-for="(item, index) in chain" :key="item.id">
        <!-- Separator arrow -->
        <svg
          v-if="index > 0"
          class="chain-arrow"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 5l7 7-7 7"
          />
        </svg>

        <!-- Chain item -->
        <button
          :class="[
            'chain-item',
            { 'is-current': index === currentIndex },
            { 'is-origin': item.is_origin },
          ]"
          :title="item.topic"
          @click="handleItemClick(item, index)"
        >
          <span class="item-label">{{ chainLabels[index] }}</span>
          <span class="item-topic">{{ getTruncatedTopic(item.topic) }}</span>
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.discussion-chain {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: rgba(59, 130, 246, 0.1);
  border-radius: 8px;
  font-size: 13px;
  overflow-x: auto;
}

.chain-label {
  color: #6b7280;
  white-space: nowrap;
  flex-shrink: 0;
}

.chain-items {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chain-arrow {
  width: 16px;
  height: 16px;
  color: #9ca3af;
  flex-shrink: 0;
}

.chain-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background-color: white;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  color: #374151;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
}

.chain-item:hover:not(.is-current) {
  background-color: #f3f4f6;
  border-color: #d1d5db;
}

.chain-item.is-current {
  background-color: #3b82f6;
  border-color: #3b82f6;
  color: white;
  cursor: default;
}

.chain-item.is-origin .item-label {
  color: #f59e0b;
}

.chain-item.is-current .item-label {
  color: #fde68a;
}

.item-label {
  font-weight: 500;
}

.item-topic {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Responsive */
@media (max-width: 768px) {
  .discussion-chain {
    padding: 6px 8px;
  }

  .item-topic {
    max-width: 100px;
  }
}
</style>
