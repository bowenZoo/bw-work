<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { Download, FileText, ChevronDown, ChevronRight } from 'lucide-vue-next';

const props = defineProps<{
  projectId: string;
  moduleId?: string;
  content?: string;
}>();

const emit = defineEmits<{
  export: [format: 'markdown' | 'pdf'];
}>();

const isLoading = ref(false);
const documentContent = ref('');
const showToc = ref(true);

// Parse headings for TOC
const headings = computed(() => {
  if (!documentContent.value) return [];

  const lines = documentContent.value.split('\n');
  const result: Array<{ level: number; text: string; id: string }> = [];

  for (const line of lines) {
    const match = line.match(/^(#{1,6})\s+(.+)$/);
    if (match) {
      const level = match[1]!.length;
      const text = match[2]!.replace(/\*\*/g, ''); // Remove bold markers
      const id = text.toLowerCase().replace(/[^\w\u4e00-\u9fa5]+/g, '-');
      result.push({ level, text, id });
    }
  }

  return result;
});

// Simple markdown to HTML conversion
const htmlContent = computed(() => {
  if (!documentContent.value) return '';

  let html = documentContent.value
    // Headers with IDs
    .replace(/^(#{1,6})\s+(.+)$/gm, (_, hashes, text) => {
      const level = hashes.length;
      const id = text.toLowerCase().replace(/[^\w\u4e00-\u9fa5]+/g, '-');
      return `<h${level} id="${id}" class="heading-${level}">${text}</h${level}>`;
    })
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    // Blockquotes
    .replace(/^>\s*(.+)$/gm, '<blockquote>$1</blockquote>')
    // Unordered lists
    .replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
    // Ordered lists
    .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
    // Checkboxes
    .replace(/- \[ \]\s*(.+)$/gm, '<li class="checkbox unchecked">$1</li>')
    .replace(/- \[x\]\s*(.+)$/gm, '<li class="checkbox checked">$1</li>')
    // Tables
    .replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').filter(Boolean);
      if (cells.every((c) => c.trim().match(/^-+$/))) {
        return ''; // Separator row
      }
      return `<tr>${cells.map((c) => `<td>${c.trim()}</td>`).join('')}</tr>`;
    })
    // Paragraphs (lines that aren't already wrapped)
    .replace(/^(?!<[h|p|l|b|t|u|d]|$)(.+)$/gm, '<p>$1</p>')
    // Line breaks
    .replace(/\n\n+/g, '\n');

  // Wrap consecutive li elements in ul
  html = html.replace(/(<li(?:\s[^>]*)?>[\s\S]*?<\/li>\s*)+/g, '<ul>$&</ul>');

  // Wrap consecutive tr elements in table
  html = html.replace(/(<tr>[\s\S]*?<\/tr>\s*)+/g, '<table class="md-table">$&</table>');

  return html;
});

watch(
  () => props.content,
  (newContent) => {
    if (newContent) {
      documentContent.value = newContent;
    }
  },
  { immediate: true }
);

async function loadDocument() {
  if (!props.projectId || !props.moduleId) return;

  isLoading.value = true;
  try {
    const response = await fetch(`/api/projects/${props.projectId}/design/${props.moduleId}`);
    if (response.ok) {
      const data = await response.json();
      documentContent.value = data.content;
    }
  } catch (error) {
    console.error('Failed to load document:', error);
  } finally {
    isLoading.value = false;
  }
}

function scrollToHeading(id: string) {
  const element = document.getElementById(id);
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function handleExport(format: 'markdown' | 'pdf') {
  emit('export', format);
}

// Load document if moduleId is provided
watch(
  () => props.moduleId,
  () => {
    if (props.moduleId && !props.content) {
      loadDocument();
    }
  },
  { immediate: true }
);
</script>

<template>
  <div class="flex h-full bg-white rounded-lg shadow-sm border overflow-hidden">
    <!-- TOC Sidebar -->
    <div
      v-if="showToc && headings.length > 0"
      class="w-64 border-r bg-gray-50 flex-shrink-0 overflow-hidden flex flex-col"
    >
      <div class="p-3 border-b bg-white">
        <h4 class="font-medium text-gray-700 text-sm">目录</h4>
      </div>
      <div class="flex-1 overflow-y-auto p-2">
        <nav class="space-y-1">
          <button
            v-for="heading in headings"
            :key="heading.id"
            type="button"
            class="block w-full text-left px-2 py-1 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
            :style="{ paddingLeft: `${(heading.level - 1) * 12 + 8}px` }"
            @click="scrollToHeading(heading.id)"
          >
            {{ heading.text }}
          </button>
        </nav>
      </div>
    </div>

    <!-- Main content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Header -->
      <div class="p-3 border-b bg-gray-50 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="p-1 text-gray-500 hover:text-gray-700 rounded"
            @click="showToc = !showToc"
          >
            <component :is="showToc ? ChevronDown : ChevronRight" class="w-5 h-5" />
          </button>
          <FileText class="w-5 h-5 text-gray-400" />
          <span class="font-medium text-gray-700">策划案预览</span>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-1 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded transition-colors"
            @click="handleExport('markdown')"
          >
            <Download class="w-4 h-4" />
            <span>Markdown</span>
          </button>
        </div>
      </div>

      <!-- Document content -->
      <div class="flex-1 overflow-y-auto p-6">
        <div v-if="isLoading" class="text-center py-12 text-gray-500">
          加载中...
        </div>
        <div v-else-if="!documentContent" class="text-center py-12 text-gray-400">
          暂无内容
        </div>
        <article v-else class="prose prose-gray max-w-none" v-html="htmlContent" />
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.prose) {
  @apply text-gray-700;
}

:deep(.prose h1) {
  @apply text-2xl font-bold text-gray-900 mt-8 mb-4 pb-2 border-b;
}

:deep(.prose h2) {
  @apply text-xl font-semibold text-gray-800 mt-6 mb-3;
}

:deep(.prose h3) {
  @apply text-lg font-medium text-gray-800 mt-4 mb-2;
}

:deep(.prose h4) {
  @apply text-base font-medium text-gray-700 mt-3 mb-2;
}

:deep(.prose p) {
  @apply mb-4 leading-relaxed;
}

:deep(.prose ul) {
  @apply mb-4 pl-6 list-disc;
}

:deep(.prose li) {
  @apply mb-1;
}

:deep(.prose blockquote) {
  @apply border-l-4 border-gray-300 pl-4 italic text-gray-600 my-4;
}

:deep(.prose .code-block) {
  @apply bg-gray-800 text-gray-100 p-4 rounded-lg overflow-x-auto my-4;
}

:deep(.prose .inline-code) {
  @apply bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm;
}

:deep(.prose .md-table) {
  @apply w-full border-collapse my-4;
}

:deep(.prose .md-table td) {
  @apply border border-gray-300 px-3 py-2;
}

:deep(.prose .md-table tr:first-child) {
  @apply bg-gray-50 font-medium;
}

:deep(.prose .checkbox) {
  @apply list-none relative pl-6;
}

:deep(.prose .checkbox::before) {
  content: '';
  @apply absolute left-0 top-1 w-4 h-4 border border-gray-300 rounded;
}

:deep(.prose .checkbox.checked::before) {
  @apply bg-blue-500 border-blue-500;
}

:deep(.prose .checkbox.checked::after) {
  content: '';
  @apply absolute left-1 top-1.5 w-2 h-1 border-l-2 border-b-2 border-white transform -rotate-45;
}
</style>
