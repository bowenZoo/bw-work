<script setup lang="ts">
import { computed } from 'vue'
import type { AgendaItem } from '@/types'

const props = defineProps<{
  visible: boolean
  item: AgendaItem | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'download', item: AgendaItem): void
}>()

const hasDetails = computed(() => {
  return props.item?.summary_details !== null
})

function handleClose() {
  emit('close')
}

function handleDownload() {
  if (props.item) {
    emit('download', props.item)
  }
}

function downloadAsMarkdown() {
  if (!props.item || !props.item.summary) return

  const blob = new Blob([props.item.summary], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `议题小结-${props.item.title}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function handleOverlayClick(event: MouseEvent) {
  if ((event.target as HTMLElement).classList.contains('modal-overlay')) {
    handleClose()
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="modal-overlay"
      @click="handleOverlayClick"
    >
      <div class="modal-container">
        <!-- Header -->
        <div class="modal-header">
          <h3 class="modal-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="title-icon"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>
            议题小结
          </h3>
          <button class="btn-close" @click="handleClose" title="关闭">
            ✕
          </button>
        </div>

        <!-- Content -->
        <div class="modal-content">
          <template v-if="item">
            <!-- Item Title -->
            <div class="item-header">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="item-status"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
              <h4 class="item-title">{{ item.title }}</h4>
            </div>

            <!-- Summary Content (Markdown) -->
            <div
              v-if="item.summary"
              class="summary-content markdown-body"
              v-html="renderMarkdown(item.summary)"
            ></div>

            <!-- Structured Details (if available) -->
            <div v-if="hasDetails && item.summary_details" class="summary-details">
              <!-- Conclusions -->
              <div v-if="item.summary_details.conclusions?.length" class="detail-section">
                <h5 class="section-title">讨论结论</h5>
                <ul class="detail-list">
                  <li v-for="(conclusion, idx) in item.summary_details.conclusions" :key="idx">
                    {{ conclusion }}
                  </li>
                </ul>
              </div>

              <!-- Viewpoints -->
              <div v-if="Object.keys(item.summary_details.viewpoints || {}).length" class="detail-section">
                <h5 class="section-title">各方观点</h5>
                <div class="viewpoints-list">
                  <div
                    v-for="(viewpoint, role) in item.summary_details.viewpoints"
                    :key="role"
                    class="viewpoint-item"
                  >
                    <span class="viewpoint-role">{{ role }}:</span>
                    <span class="viewpoint-content">{{ viewpoint }}</span>
                  </div>
                </div>
              </div>

              <!-- Open Questions -->
              <div v-if="item.summary_details.open_questions?.length" class="detail-section">
                <h5 class="section-title">遗留问题</h5>
                <ul class="detail-list warning">
                  <li v-for="(question, idx) in item.summary_details.open_questions" :key="idx">
                    {{ question }}
                  </li>
                </ul>
              </div>

              <!-- Next Steps -->
              <div v-if="item.summary_details.next_steps?.length" class="detail-section">
                <h5 class="section-title">下一步行动</h5>
                <ul class="detail-list action">
                  <li v-for="(step, idx) in item.summary_details.next_steps" :key="idx">
                    {{ step }}
                  </li>
                </ul>
              </div>
            </div>

            <div v-if="!item.summary" class="no-summary">
              暂无小结内容
            </div>
          </template>

          <template v-else>
            <div class="no-item">
              未选择议题
            </div>
          </template>
        </div>

        <!-- Footer -->
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="handleClose">
            关闭
          </button>
          <button
            v-if="item?.summary"
            class="btn btn-primary"
            @click="downloadAsMarkdown"
          >
            下载 Markdown
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script lang="ts">
// Simple markdown rendering helper
function renderMarkdown(text: string): string {
  if (!text) return ''

  // Very basic markdown to HTML conversion
  return text
    // Headers
    .replace(/^### (.+)$/gm, '<h5>$1</h5>')
    .replace(/^## (.+)$/gm, '<h4>$1</h4>')
    .replace(/^# (.+)$/gm, '<h3>$1</h3>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Lists
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Wrap lists
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    // Line breaks
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    // Wrap in paragraph
    .replace(/^(.+)$/, '<p>$1</p>')
}

export default {
  methods: {
    renderMarkdown
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-container {
  background: var(--bg-secondary, #1a1a2e);
  border-radius: 12px;
  width: 90%;
  max-width: 700px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color, #2d2d44);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color, #2d2d44);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 18px;
  color: var(--text-primary, #e0e0e0);
}

.title-icon {
  color: var(--text-secondary, #888);
  flex-shrink: 0;
}

.btn-close {
  background: transparent;
  border: none;
  color: var(--text-secondary, #888);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
}

.btn-close:hover {
  background: var(--bg-tertiary, #16162a);
  color: var(--text-primary, #e0e0e0);
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color, #2d2d44);
}

.item-status {
  flex-shrink: 0;
}

.item-title {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary, #e0e0e0);
}

.summary-content {
  color: var(--text-primary, #e0e0e0);
  line-height: 1.6;
}

.summary-content :deep(h3),
.summary-content :deep(h4),
.summary-content :deep(h5) {
  color: var(--text-primary, #e0e0e0);
  margin-top: 16px;
  margin-bottom: 8px;
}

.summary-content :deep(ul) {
  margin: 8px 0;
  padding-left: 24px;
}

.summary-content :deep(li) {
  margin: 4px 0;
}

.summary-content :deep(strong) {
  color: var(--primary-color, #6366f1);
}

.summary-details {
  margin-top: 24px;
}

.detail-section {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary, #888);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-list {
  margin: 0;
  padding-left: 20px;
  list-style: disc;
}

.detail-list li {
  margin: 8px 0;
  color: var(--text-primary, #e0e0e0);
  line-height: 1.5;
}

.detail-list.warning li {
  color: var(--warning-color, #f59e0b);
}

.detail-list.action li {
  color: var(--success-color, #22c55e);
}

.viewpoints-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.viewpoint-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--bg-tertiary, #16162a);
  border-radius: 8px;
}

.viewpoint-role {
  font-weight: 600;
  color: var(--primary-color, #6366f1);
  font-size: 13px;
}

.viewpoint-content {
  color: var(--text-primary, #e0e0e0);
  font-size: 14px;
  line-height: 1.5;
}

.no-summary,
.no-item {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary, #888);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-color, #2d2d44);
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary {
  background: var(--bg-tertiary, #16162a);
  border: 1px solid var(--border-color, #2d2d44);
  color: var(--text-primary, #e0e0e0);
}

.btn-secondary:hover {
  background: var(--bg-hover, #1f1f3a);
}

.btn-primary {
  background: var(--primary-color, #6366f1);
  border: none;
  color: white;
}

.btn-primary:hover {
  background: var(--primary-hover, #4f46e5);
}
</style>
