<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { Activity, Coins, ChevronDown, ChevronUp } from 'lucide-vue-next';
import { getDiscussionCost, type CostResponse } from '@/api/monitoring';

const props = defineProps<{
  discussionId: string;
  refreshInterval?: number; // Default 5000ms
}>();

const costData = ref<CostResponse | null>(null);
const isLoading = ref(false);
const error = ref<string | null>(null);
const isExpanded = ref(false);
let refreshTimer: ReturnType<typeof setInterval> | null = null;

const effectiveRefreshInterval = computed(() => props.refreshInterval ?? 5000);

const totalTokens = computed(() => costData.value?.total_tokens ?? 0);
const promptTokens = computed(() => costData.value?.prompt_tokens ?? 0);
const completionTokens = computed(() => costData.value?.completion_tokens ?? 0);

const modelBreakdown = computed(() => {
  if (!costData.value?.model_breakdown) return [];
  return Object.entries(costData.value.model_breakdown).map(([model, tokens]) => ({
    model,
    tokens,
    percentage: totalTokens.value > 0 ? (tokens / totalTokens.value) * 100 : 0,
  }));
});

const promptPercentage = computed(() => {
  if (totalTokens.value === 0) return 50;
  return (promptTokens.value / totalTokens.value) * 100;
});

async function fetchCostData() {
  if (!props.discussionId) return;

  isLoading.value = true;
  error.value = null;

  try {
    costData.value = await getDiscussionCost(props.discussionId);
    if (costData.value.error) {
      error.value = costData.value.error;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to fetch cost data';
  } finally {
    isLoading.value = false;
  }
}

function startRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }
  refreshTimer = setInterval(fetchCostData, effectiveRefreshInterval.value);
}

function stopRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function toggleExpanded() {
  isExpanded.value = !isExpanded.value;
}

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
}

watch(
  () => props.discussionId,
  (newId) => {
    if (newId) {
      fetchCostData();
      startRefresh();
    } else {
      stopRefresh();
      costData.value = null;
    }
  },
  { immediate: true }
);

onMounted(() => {
  if (props.discussionId) {
    fetchCostData();
    startRefresh();
  }
});

onUnmounted(() => {
  stopRefresh();
});
</script>

<template>
  <div class="bg-white border border-gray-200 rounded-lg shadow-sm">
    <!-- Header - always visible -->
    <div
      class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50"
      @click="toggleExpanded"
    >
      <div class="flex items-center gap-2">
        <Coins class="w-4 h-4 text-gray-500" />
        <span class="text-sm font-medium text-gray-700">Token Usage</span>
      </div>
      <div class="flex items-center gap-3">
        <div v-if="isLoading" class="flex items-center gap-1 text-gray-400">
          <Activity class="w-3 h-3 animate-pulse" />
        </div>
        <span class="text-sm font-semibold text-gray-900">{{ formatNumber(totalTokens) }}</span>
        <component :is="isExpanded ? ChevronUp : ChevronDown" class="w-4 h-4 text-gray-400" />
      </div>
    </div>

    <!-- Expanded content -->
    <div v-if="isExpanded" class="px-4 pb-4 border-t border-gray-100">
      <!-- Error message -->
      <div v-if="error" class="mt-3 text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded">
        {{ error }}
      </div>

      <!-- Token breakdown bar -->
      <div class="mt-4">
        <div class="flex justify-between text-xs text-gray-500 mb-1">
          <span>Prompt: {{ formatNumber(promptTokens) }}</span>
          <span>Completion: {{ formatNumber(completionTokens) }}</span>
        </div>
        <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            class="h-full bg-blue-500 transition-all duration-300"
            :style="{ width: `${promptPercentage}%` }"
          ></div>
        </div>
      </div>

      <!-- Model breakdown -->
      <div v-if="modelBreakdown.length > 0" class="mt-4">
        <div class="text-xs font-medium text-gray-500 mb-2">By Model</div>
        <div class="space-y-2">
          <div
            v-for="item in modelBreakdown"
            :key="item.model"
            class="flex items-center gap-2"
          >
            <div class="flex-1">
              <div class="flex justify-between text-xs mb-1">
                <span class="text-gray-600 truncate" :title="item.model">
                  {{ item.model }}
                </span>
                <span class="text-gray-500">{{ formatNumber(item.tokens) }}</span>
              </div>
              <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  class="h-full bg-indigo-400 transition-all duration-300"
                  :style="{ width: `${item.percentage}%` }"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Data source indicator -->
      <div class="mt-4 text-xs text-gray-400 flex items-center gap-1">
        <span>Source:</span>
        <span class="font-medium">{{ costData?.source ?? 'langfuse' }}</span>
      </div>
    </div>
  </div>
</template>
