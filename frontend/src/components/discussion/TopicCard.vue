<script setup lang="ts">
import { computed } from 'vue';

export interface TopicCardProps {
  topic: string;
  status: 'pending' | 'running' | 'completed' | 'stopped' | 'failed';
  attachment?: {
    filename: string;
    content: string;
  };
}

const props = defineProps<TopicCardProps>();

const emit = defineEmits<{
  (e: 'preview-attachment'): void;
}>();

const statusConfig = computed(() => {
  switch (props.status) {
    case 'pending':
      return { iconType: 'hourglass', text: '待开始', class: 'text-gray-500' };
    case 'running':
      return { iconType: 'circle-blue', text: '进行中', class: 'text-blue-600' };
    case 'completed':
      return { iconType: 'check', text: '已完成', class: 'text-green-600' };
    case 'stopped':
      return { iconType: 'pause', text: '已停止', class: 'text-amber-600' };
    case 'failed':
      return { iconType: 'x', text: '已中断', class: 'text-red-500' };
    default:
      return { iconType: 'question', text: '未知', class: 'text-gray-400' };
  }
});

function handleAttachmentClick() {
  emit('preview-attachment');
}
</script>

<template>
  <div class="bg-white border border-gray-200 rounded-md">
    <!-- 标题栏 -->
    <div class="px-4 py-3 border-b border-gray-100 bg-gray-50 rounded-t-lg">
      <div class="flex items-center gap-2">
        <svg class="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        <span class="text-sm font-medium text-gray-600">讨论议题</span>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="p-4">
      <!-- 议题标题 -->
      <h3 class="text-lg font-semibold text-gray-900 mb-3">
        {{ topic }}
      </h3>

      <!-- 附件按钮 -->
      <div v-if="attachment" class="mb-3">
        <button
          class="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors"
          @click="handleAttachmentClick"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>{{ attachment.filename }}</span>
        </button>
      </div>

      <!-- 状态显示 -->
      <div class="flex items-center gap-2">
        <span class="text-sm text-gray-500">状态：</span>
        <span :class="['flex items-center gap-1 text-sm font-medium', statusConfig.class]">
          <svg v-if="statusConfig.iconType === 'check'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
          <svg v-else-if="statusConfig.iconType === 'circle-blue'" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="12" cy="12" r="10"/></svg>
          <svg v-else-if="statusConfig.iconType === 'pause'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="10" x2="10" y1="15" y2="9"/><line x1="14" x2="14" y1="15" y2="9"/></svg>
          <svg v-else-if="statusConfig.iconType === 'x'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/></svg>
          <svg v-else-if="statusConfig.iconType === 'hourglass'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 1 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>
          {{ statusConfig.text }}
        </span>
      </div>
    </div>
  </div>
</template>
