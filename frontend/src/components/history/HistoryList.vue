<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import type { DiscussionSummary } from '@/types';
import { getDiscussionHistory } from '@/api/discussion';
import HistoryCard from './HistoryCard.vue';

const emit = defineEmits<{
  select: [discussion: DiscussionSummary];
}>();

// State
const discussions = ref<DiscussionSummary[]>([]);
const isLoading = ref(false);
const hasMore = ref(true);
const page = ref(1);
const error = ref<string | null>(null);

// Constants
const PAGE_SIZE = 20;

// Computed
const isEmpty = computed(() => !isLoading.value && discussions.value.length === 0);

// Load discussions
async function loadDiscussions(reset: boolean = false) {
  if (isLoading.value) return;
  if (!reset && !hasMore.value) return;

  isLoading.value = true;
  error.value = null;

  try {
    if (reset) {
      page.value = 1;
      discussions.value = [];
    }

    const response = await getDiscussionHistory(page.value, PAGE_SIZE);
    discussions.value = [...discussions.value, ...response.items];
    hasMore.value = response.hasMore;
    page.value++;
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load discussions';
    console.error('Failed to load discussions:', e);
  } finally {
    isLoading.value = false;
  }
}

// Infinite scroll handler
function handleScroll(event: Event) {
  const target = event.target as HTMLElement;
  const scrollBottom = target.scrollHeight - target.scrollTop - target.clientHeight;

  if (scrollBottom < 100 && hasMore.value && !isLoading.value) {
    loadDiscussions();
  }
}

// Select a discussion
function handleSelect(discussion: DiscussionSummary) {
  emit('select', discussion);
}

// Load initial data
onMounted(() => {
  loadDiscussions(true);
});

// Expose refresh method
defineExpose({
  refresh: () => loadDiscussions(true),
});
</script>

<template>
  <div
    class="h-full overflow-y-auto"
    @scroll="handleScroll"
  >
    <!-- Error state -->
    <div
      v-if="error"
      class="p-4 text-center"
    >
      <p class="text-red-500 mb-2">{{ error }}</p>
      <button
        class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        @click="loadDiscussions(true)"
      >
        Retry
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="isEmpty"
      class="p-8 text-center text-gray-500"
    >
      <svg
        class="w-16 h-16 mx-auto mb-4 text-gray-300"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
        />
      </svg>
      <p class="text-lg font-medium">No discussions yet</p>
      <p class="text-sm mt-1">Start a new discussion to see it here</p>
    </div>

    <!-- Discussion list -->
    <div
      v-else
      class="divide-y divide-gray-200"
    >
      <HistoryCard
        v-for="discussion in discussions"
        :key="discussion.id"
        :discussion="discussion"
        @click="handleSelect(discussion)"
      />
    </div>

    <!-- Loading indicator -->
    <div
      v-if="isLoading"
      class="p-4 text-center"
    >
      <div class="inline-flex items-center gap-2 text-gray-500">
        <svg
          class="animate-spin h-5 w-5"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          />
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
        <span>Loading...</span>
      </div>
    </div>

    <!-- Load more hint -->
    <div
      v-if="hasMore && !isLoading"
      class="p-4 text-center text-gray-400 text-sm"
    >
      Scroll for more
    </div>
  </div>
</template>
