<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { Header, Sidebar } from '@/components/layout';
import { HistoryList } from '@/components/history';
import type { DiscussionSummary } from '@/types';

const router = useRouter();

// Search filter
const searchQuery = ref('');
const historyListRef = ref<InstanceType<typeof HistoryList> | null>(null);

// Filter discussions (client-side filtering)
// Note: This works well for < 500 discussions. For larger datasets,
// consider implementing server-side search by adding a 'q' parameter.
const filteredQuery = computed(() => searchQuery.value.trim().toLowerCase());

// Handle discussion selection
function handleSelectDiscussion(discussion: DiscussionSummary) {
  // Navigate to discussion detail with playback mode
  router.push({
    name: 'discussion-playback',
    params: { id: discussion.id },
  });
}

// Clear search
function clearSearch() {
  searchQuery.value = '';
}
</script>

<template>
  <div class="h-screen flex flex-col bg-gray-100">
    <!-- Header -->
    <Header />

    <!-- Main content -->
    <div class="flex-1 flex overflow-hidden">
      <!-- History list area -->
      <main class="flex-1 flex flex-col bg-white">
        <!-- Search bar -->
        <div class="p-4 border-b border-gray-200">
          <div class="relative">
            <svg
              class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search discussions..."
              class="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              v-if="searchQuery"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              @click="clearSearch"
            >
              <svg
                class="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        <!-- History list -->
        <HistoryList
          ref="historyListRef"
          class="flex-1"
          @select="handleSelectDiscussion"
        />
      </main>

      <!-- Sidebar -->
      <Sidebar :is-open="true" />
    </div>
  </div>
</template>
