<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  currentIndex: number;
  totalMessages: number;
  isPlaying: boolean;
  speed: number;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  play: [];
  pause: [];
  seek: [index: number];
  speedChange: [speed: number];
}>();

// Progress percentage
const progress = computed(() => {
  if (props.totalMessages === 0) return 0;
  return (props.currentIndex / (props.totalMessages - 1)) * 100;
});

// Current position text
const positionText = computed(() => {
  return `${props.currentIndex + 1} / ${props.totalMessages}`;
});

// Speed options
const speedOptions = [0.5, 1, 1.5, 2];

// Handle play/pause toggle
function togglePlayPause() {
  if (props.isPlaying) {
    emit('pause');
  } else {
    emit('play');
  }
}

// Handle progress bar click
function handleProgressClick(event: MouseEvent) {
  const target = event.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const clickX = event.clientX - rect.left;
  const percentage = clickX / rect.width;
  const newIndex = Math.round(percentage * (props.totalMessages - 1));
  emit('seek', Math.max(0, Math.min(newIndex, props.totalMessages - 1)));
}

// Handle speed change
function handleSpeedChange(newSpeed: number) {
  emit('speedChange', newSpeed);
}

// Step forward/backward
function stepBackward() {
  if (props.currentIndex > 0) {
    emit('seek', props.currentIndex - 1);
  }
}

function stepForward() {
  if (props.currentIndex < props.totalMessages - 1) {
    emit('seek', props.currentIndex + 1);
  }
}

// Go to start/end
function goToStart() {
  emit('seek', 0);
}

function goToEnd() {
  emit('seek', props.totalMessages - 1);
}
</script>

<template>
  <div class="bg-white border-t border-gray-200 p-4">
    <!-- Progress bar -->
    <div
      class="relative h-2 bg-gray-200 rounded-full cursor-pointer mb-4"
      @click="handleProgressClick"
    >
      <div
        class="absolute h-full bg-blue-500 rounded-full transition-all duration-150"
        :style="{ width: `${progress}%` }"
      />
      <!-- Thumb indicator -->
      <div
        class="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-blue-500 rounded-full border-2 border-white shadow transition-all duration-150"
        :style="{ left: `calc(${progress}% - 8px)` }"
      />
    </div>

    <!-- Controls -->
    <div class="flex items-center justify-between">
      <!-- Left: Navigation controls -->
      <div class="flex items-center gap-2">
        <!-- Go to start -->
        <button
          class="p-2 text-gray-500 hover:text-gray-700 disabled:opacity-50"
          :disabled="currentIndex === 0"
          title="Go to start"
          @click="goToStart"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>

        <!-- Step backward -->
        <button
          class="p-2 text-gray-500 hover:text-gray-700 disabled:opacity-50"
          :disabled="currentIndex === 0"
          title="Previous message"
          @click="stepBackward"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <!-- Play/Pause -->
        <button
          class="p-3 bg-blue-500 text-white rounded-full hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          :disabled="currentIndex >= totalMessages - 1 && !isPlaying"
          @click="togglePlayPause"
        >
          <!-- Play icon -->
          <svg
            v-if="!isPlaying"
            class="w-6 h-6"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M8 5v14l11-7z" />
          </svg>
          <!-- Pause icon -->
          <svg
            v-else
            class="w-6 h-6"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
          </svg>
        </button>

        <!-- Step forward -->
        <button
          class="p-2 text-gray-500 hover:text-gray-700 disabled:opacity-50"
          :disabled="currentIndex >= totalMessages - 1"
          title="Next message"
          @click="stepForward"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>

        <!-- Go to end -->
        <button
          class="p-2 text-gray-500 hover:text-gray-700 disabled:opacity-50"
          :disabled="currentIndex >= totalMessages - 1"
          title="Go to end"
          @click="goToEnd"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      <!-- Center: Position indicator -->
      <div class="text-sm text-gray-600 font-medium">
        {{ positionText }}
      </div>

      <!-- Right: Speed selector -->
      <div class="flex items-center gap-2">
        <span class="text-sm text-gray-500">Speed:</span>
        <div class="flex gap-1">
          <button
            v-for="s in speedOptions"
            :key="s"
            :class="[
              'px-2 py-1 text-sm rounded',
              speed === s
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
            ]"
            @click="handleSpeedChange(s)"
          >
            {{ s }}x
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
