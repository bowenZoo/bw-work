<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { Play, Pause, SkipForward, CheckCircle2, Clock, Loader2 } from 'lucide-vue-next';

interface ModuleProgress {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'failed';
  round?: number;
}

const props = defineProps<{
  projectId: string;
  discussionId: string;
  modules: ModuleProgress[];
  totalModules: number;
  completedModules: number;
  currentModule?: string;
  currentRound: number;
  isRunning: boolean;
  isPaused: boolean;
}>();

const emit = defineEmits<{
  pause: [];
  resume: [];
  skip: [];
}>();

const messages = ref<Array<{ speaker: string; summary: string; timestamp: Date }>>([]);
const messagesContainer = ref<HTMLElement | null>(null);

const progress = computed(() => {
  if (props.totalModules === 0) return 0;
  return Math.round((props.completedModules / props.totalModules) * 100);
});

const currentModuleInfo = computed(() => {
  return props.modules.find((m) => m.id === props.currentModule);
});

const statusText = computed(() => {
  if (props.isPaused) return '已暂停';
  if (!props.isRunning) return '等待开始';
  if (currentModuleInfo.value) {
    return `讨论中: ${currentModuleInfo.value.name} (第 ${props.currentRound} 轮)`;
  }
  return '准备中...';
});

function handlePause() {
  emit('pause');
}

function handleResume() {
  emit('resume');
}

function handleSkip() {
  emit('skip');
}

function addMessage(speaker: string, summary: string) {
  messages.value.push({
    speaker,
    summary,
    timestamp: new Date(),
  });

  // Auto scroll to bottom
  if (messagesContainer.value) {
    setTimeout(() => {
      messagesContainer.value?.scrollTo({
        top: messagesContainer.value.scrollHeight,
        behavior: 'smooth',
      });
    }, 100);
  }
}

// Expose for parent component
defineExpose({ addMessage });

function getStatusIcon(status: ModuleProgress['status']) {
  switch (status) {
    case 'completed':
      return CheckCircle2;
    case 'running':
      return Loader2;
    case 'skipped':
      return SkipForward;
    default:
      return Clock;
  }
}

function getStatusColor(status: ModuleProgress['status']) {
  switch (status) {
    case 'completed':
      return 'text-green-500';
    case 'running':
      return 'text-blue-500';
    case 'skipped':
      return 'text-yellow-500';
    case 'failed':
      return 'text-red-500';
    default:
      return 'text-gray-400';
  }
}
</script>

<template>
  <div class="w-full bg-white rounded-lg shadow-sm border">
    <!-- Header -->
    <div class="p-4 border-b">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-lg font-medium text-gray-900">讨论进度</h3>
        <div class="flex items-center gap-2">
          <button
            v-if="isRunning && !isPaused"
            type="button"
            class="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
            title="暂停"
            @click="handlePause"
          >
            <Pause class="w-5 h-5" />
          </button>
          <button
            v-if="isPaused"
            type="button"
            class="p-2 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors"
            title="继续"
            @click="handleResume"
          >
            <Play class="w-5 h-5" />
          </button>
          <button
            v-if="isRunning && !isPaused"
            type="button"
            class="p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
            title="跳过当前模块"
            @click="handleSkip"
          >
            <SkipForward class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Progress bar -->
      <div class="relative h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          class="absolute inset-y-0 left-0 bg-blue-500 transition-all duration-500"
          :style="{ width: `${progress}%` }"
        />
      </div>
      <div class="flex justify-between mt-2 text-sm text-gray-500">
        <span>{{ statusText }}</span>
        <span>{{ completedModules }} / {{ totalModules }} 模块</span>
      </div>
    </div>

    <!-- Module list -->
    <div class="p-4 border-b max-h-48 overflow-y-auto">
      <div class="space-y-2">
        <div
          v-for="module in modules"
          :key="module.id"
          class="flex items-center gap-3 p-2 rounded"
          :class="{
            'bg-blue-50': module.status === 'running',
            'bg-green-50': module.status === 'completed',
          }"
        >
          <component
            :is="getStatusIcon(module.status)"
            class="w-5 h-5"
            :class="[
              getStatusColor(module.status),
              { 'animate-spin': module.status === 'running' },
            ]"
          />
          <span
            class="flex-1 text-sm"
            :class="{
              'text-gray-900 font-medium': module.status === 'running',
              'text-gray-500': module.status === 'pending',
              'text-gray-700': module.status === 'completed',
            }"
          >
            {{ module.name }}
          </span>
          <span v-if="module.status === 'running' && module.round" class="text-xs text-blue-600">
            第 {{ module.round }} 轮
          </span>
        </div>
      </div>
    </div>

    <!-- Message stream -->
    <div ref="messagesContainer" class="p-4 h-64 overflow-y-auto">
      <div v-if="messages.length === 0" class="text-center text-gray-400 py-8">
        讨论消息将在此显示...
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="text-sm"
        >
          <div class="flex items-baseline gap-2">
            <span class="font-medium text-gray-700">{{ msg.speaker }}</span>
            <span class="text-xs text-gray-400">
              {{ msg.timestamp.toLocaleTimeString() }}
            </span>
          </div>
          <p class="text-gray-600 mt-0.5">{{ msg.summary }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
