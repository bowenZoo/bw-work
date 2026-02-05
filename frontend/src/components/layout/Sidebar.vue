<script setup lang="ts">
import { AgentStatus } from '@/components/agent';
import { CostPanel } from '@/components/monitoring';

defineProps<{
  isOpen?: boolean;
  discussionId?: string | null;
}>();
</script>

<template>
  <aside
    :class="[
      'w-64 bg-gray-50 border-l border-gray-200 flex flex-col overflow-y-auto transition-all duration-300',
      isOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0',
    ]"
  >
    <div class="p-4">
      <AgentStatus />
    </div>

    <div class="px-4 pb-4">
      <CostPanel v-if="discussionId" :discussion-id="discussionId" />
    </div>

    <!-- Additional sidebar content can go here -->
    <div class="flex-1"></div>

  </aside>
</template>
