import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { Discussion, Message, DiscussionStatus } from '@/types';

export const useDiscussionStore = defineStore('discussion', () => {
  // State
  const currentDiscussion = ref<Discussion | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  // Getters
  const discussionId = computed(() => currentDiscussion.value?.id ?? null);

  const topic = computed(() => currentDiscussion.value?.topic ?? '');

  const messages = computed(() => currentDiscussion.value?.messages ?? []);

  const status = computed(() => currentDiscussion.value?.status ?? 'pending');

  const isInProgress = computed(() => {
    if (!currentDiscussion.value) return false;
    return status.value === 'pending' || status.value === 'running';
  });

  const isCompleted = computed(() => status.value === 'completed');

  // Actions
  function setDiscussion(discussion: Discussion) {
    currentDiscussion.value = discussion;
    error.value = null;
  }

  function addMessage(message: Message) {
    if (currentDiscussion.value) {
      currentDiscussion.value.messages.push(message);
    }
  }

  function setStatus(newStatus: DiscussionStatus) {
    if (currentDiscussion.value) {
      currentDiscussion.value.status = newStatus;
    }
  }

  function startDiscussion() {
    if (currentDiscussion.value) {
      currentDiscussion.value.status = 'running';
    }
  }

  function endDiscussion() {
    if (currentDiscussion.value) {
      currentDiscussion.value.status = 'completed';
    }
  }

  function setLoading(loading: boolean) {
    isLoading.value = loading;
  }

  function setError(errorMessage: string | null) {
    error.value = errorMessage;
  }

  function clearDiscussion() {
    currentDiscussion.value = null;
    error.value = null;
  }

  return {
    // State
    currentDiscussion,
    isLoading,
    error,
    // Getters
    discussionId,
    topic,
    messages,
    status,
    isInProgress,
    isCompleted,
    // Actions
    setDiscussion,
    addMessage,
    setStatus,
    startDiscussion,
    endDiscussion,
    setLoading,
    setError,
    clearDiscussion,
  };
});
