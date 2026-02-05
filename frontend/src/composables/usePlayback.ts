import { ref, computed, onUnmounted } from 'vue';
import type { Message, DiscussionSummary } from '@/types';
import { getDiscussionMessages } from '@/api/discussion';

/**
 * Playback state management composable
 *
 * Implements:
 * - Message sequence playback with configurable speed
 * - Play/pause/seek controls
 * - Timer-based auto-advance
 *
 * Time semantics: Fixed interval mode
 * - Each message interval = BASE_INTERVAL / speed
 * - Example: At 1x speed, each message displays for 1.5 seconds
 */

// Base interval in milliseconds (at 1x speed)
const BASE_INTERVAL = 1500;

export interface PlaybackState {
  discussion: DiscussionSummary | null;
  messages: Message[];
  currentIndex: number;
  isPlaying: boolean;
  speed: number;
  isLoading: boolean;
  error: string | null;
}

export function usePlayback() {
  // State
  const discussion = ref<DiscussionSummary | null>(null);
  const messages = ref<Message[]>([]);
  const currentIndex = ref(0);
  const isPlaying = ref(false);
  const speed = ref(1);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  // Timer reference
  let playbackTimer: ReturnType<typeof setTimeout> | null = null;

  // Computed: visible messages up to current index
  const visibleMessages = computed(() => {
    return messages.value.slice(0, currentIndex.value + 1);
  });

  // Computed: current interval based on speed
  const interval = computed(() => {
    return BASE_INTERVAL / speed.value;
  });

  // Computed: is at end of messages
  const isAtEnd = computed(() => {
    return currentIndex.value >= messages.value.length - 1;
  });

  // Computed: total message count
  const totalMessages = computed(() => {
    return messages.value.length;
  });

  /**
   * Load discussion messages for playback
   */
  async function loadDiscussion(discussionId: string) {
    isLoading.value = true;
    error.value = null;

    // Reset playback state
    stop();
    currentIndex.value = 0;
    messages.value = [];
    discussion.value = null;

    try {
      const response = await getDiscussionMessages(discussionId);
      discussion.value = response.discussion;
      // Transform API message format (snake_case) to frontend format (camelCase)
      messages.value = response.messages.map((m) => ({
        id: m.id,
        agentId: m.agent_id,
        agentRole: m.agent_role,
        content: m.content,
        timestamp: m.timestamp,
      }));
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load discussion';
      console.error('Failed to load discussion for playback:', e);
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Start playback
   */
  function play() {
    if (messages.value.length === 0) return;

    // If at end, restart from beginning
    if (isAtEnd.value) {
      currentIndex.value = 0;
    }

    isPlaying.value = true;
    scheduleNextMessage();
  }

  /**
   * Pause playback
   */
  function pause() {
    isPlaying.value = false;
    clearTimer();
  }

  /**
   * Stop playback and reset to beginning
   */
  function stop() {
    isPlaying.value = false;
    currentIndex.value = 0;
    clearTimer();
  }

  /**
   * Seek to specific message index
   */
  function seek(index: number) {
    const clampedIndex = Math.max(0, Math.min(index, messages.value.length - 1));
    currentIndex.value = clampedIndex;

    // If playing and seeking, reschedule timer
    if (isPlaying.value) {
      clearTimer();
      scheduleNextMessage();
    }
  }

  /**
   * Set playback speed
   */
  function setSpeed(newSpeed: number) {
    speed.value = newSpeed;

    // If playing, reschedule with new speed
    if (isPlaying.value) {
      clearTimer();
      scheduleNextMessage();
    }
  }

  /**
   * Schedule next message display
   */
  function scheduleNextMessage() {
    if (!isPlaying.value) return;
    if (isAtEnd.value) {
      // Reached end, stop playback
      isPlaying.value = false;
      return;
    }

    playbackTimer = setTimeout(() => {
      if (isPlaying.value) {
        currentIndex.value++;
        scheduleNextMessage();
      }
    }, interval.value);
  }

  /**
   * Clear playback timer
   */
  function clearTimer() {
    if (playbackTimer) {
      clearTimeout(playbackTimer);
      playbackTimer = null;
    }
  }

  // Watch for speed changes (handled in setSpeed)

  // Cleanup on unmount
  onUnmounted(() => {
    clearTimer();
  });

  return {
    // State
    discussion,
    messages,
    currentIndex,
    isPlaying,
    speed,
    isLoading,
    error,

    // Computed
    visibleMessages,
    isAtEnd,
    totalMessages,

    // Methods
    loadDiscussion,
    play,
    pause,
    stop,
    seek,
    setSpeed,
  };
}
