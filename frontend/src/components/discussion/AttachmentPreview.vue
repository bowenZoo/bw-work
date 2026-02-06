<script setup lang="ts">
import { computed } from 'vue';
import { toSanitizedMarkdownHtml } from '@/utils/markdown';

export interface AttachmentPreviewProps {
  visible: boolean;
  filename: string;
  content: string;
}

const props = defineProps<AttachmentPreviewProps>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const renderedContent = computed(() => {
  return toSanitizedMarkdownHtml(props.content);
});

function handleClose() {
  emit('close');
}

function handleOverlayClick(event: MouseEvent) {
  if (event.target === event.currentTarget) {
    handleClose();
  }
}

function handleDownload() {
  const blob = new Blob([props.content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = props.filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click="handleOverlayClick"
    >
      <div class="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] mx-4 flex flex-col">
        <!-- 标题栏 -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span class="font-medium text-gray-900">{{ filename }}</span>
          </div>
          <button
            class="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            @click="handleClose"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- 内容区 -->
        <div class="flex-1 overflow-y-auto p-6">
          <article
            class="prose prose-sm max-w-none"
            v-html="renderedContent"
          />
        </div>

        <!-- 底部操作栏 -->
        <div class="flex justify-end gap-3 px-4 py-3 border-t border-gray-200 bg-gray-50 rounded-b-lg">
          <button
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
            @click="handleDownload"
          >
            <span class="flex items-center gap-2">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              下载
            </span>
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
            @click="handleClose"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* Prose 样式覆盖 */
.prose :deep(h1) {
  @apply text-2xl font-bold text-gray-900 mb-4 mt-6;
}

.prose :deep(h2) {
  @apply text-xl font-semibold text-gray-900 mb-3 mt-5;
}

.prose :deep(h3) {
  @apply text-lg font-medium text-gray-900 mb-2 mt-4;
}

.prose :deep(p) {
  @apply text-gray-700 mb-3 leading-relaxed;
}

.prose :deep(ul),
.prose :deep(ol) {
  @apply pl-5 mb-3;
}

.prose :deep(li) {
  @apply text-gray-700 mb-1;
}

.prose :deep(code) {
  @apply bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-gray-800;
}

.prose :deep(pre) {
  @apply bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto mb-4;
}

.prose :deep(pre code) {
  @apply bg-transparent p-0 text-gray-100;
}

.prose :deep(blockquote) {
  @apply border-l-4 border-gray-300 pl-4 py-1 my-4 text-gray-600 italic;
}

.prose :deep(table) {
  @apply w-full border-collapse mb-4;
}

.prose :deep(th),
.prose :deep(td) {
  @apply border border-gray-300 px-3 py-2 text-left;
}

.prose :deep(th) {
  @apply bg-gray-100 font-semibold;
}

.prose :deep(a) {
  @apply text-blue-600 hover:underline;
}
</style>
