<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft } from 'lucide-vue-next';
import { Header, Sidebar } from '@/components/layout';
import { HistoryList, ContinueDiscussionModal } from '@/components/history';
import type { DiscussionSummary } from '@/types';
import api from '@/api';

const router = useRouter();

// Search filter
const searchQuery = ref('');

// Continue discussion modal state
const showContinueModal = ref(false);
const selectedDiscussion = ref<DiscussionSummary | null>(null);
const continueError = ref<string | null>(null);

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

// Handle continue discussion click
function handleContinueClick(discussion: DiscussionSummary) {
  selectedDiscussion.value = discussion;
  showContinueModal.value = true;
  continueError.value = null;
}

// Handle continue confirm
async function handleContinueConfirm(followUp: string) {
  if (!selectedDiscussion.value) return;

  try {
    const response = await api.post(
      `/api/discussions/${selectedDiscussion.value.id}/continue`,
      {
        follow_up: followUp,
        rounds: 2,
      }
    );

    if (response.data.new_discussion_id) {
      showContinueModal.value = false;
      selectedDiscussion.value = null;
      // Navigate to the new discussion
      router.push({ name: 'discussion' });
    }
  } catch (error: any) {
    console.error('Failed to continue discussion:', error);
    continueError.value =
      error.response?.data?.detail || '继续讨论失败，请重试';
  }
}

// Handle continue modal close
function handleContinueClose() {
  showContinueModal.value = false;
  selectedDiscussion.value = null;
  continueError.value = null;
}

// Clear search
function clearSearch() {
  searchQuery.value = '';
}
</script>

<template>
  <div class="h-screen flex flex-col bg-gray-100">
    <!-- Header -->
    <Header>
      <template #extra>
        <router-link
          to="/"
          class="flex items-center gap-2 px-3 py-1.5 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft class="w-4 h-4" />
          <span class="text-sm">返回首页</span>
        </router-link>
      </template>
    </Header>

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
              placeholder="搜索讨论..."
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
          :search-query="filteredQuery"
          @select="handleSelectDiscussion"
          @continue="handleContinueClick"
        />
      </main>

      <!-- Sidebar -->
      <Sidebar :is-open="true" />
    </div>

    <!-- Continue Discussion Modal -->
    <ContinueDiscussionModal
      :visible="showContinueModal"
      :discussion="selectedDiscussion"
      @confirm="handleContinueConfirm"
      @close="handleContinueClose"
    />

    <!-- Error toast -->
    <Teleport to="body">
      <Transition name="toast">
        <div
          v-if="continueError"
          class="fixed bottom-4 right-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg shadow-lg z-50 flex items-center gap-2"
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
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{{ continueError }}</span>
          <button
            class="ml-2 text-red-500 hover:text-red-700"
            @click="continueError = null"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
