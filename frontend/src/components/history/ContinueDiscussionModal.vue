<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import type { DiscussionSummary } from '@/types';

interface Props {
  visible: boolean;
  discussion: DiscussionSummary | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  confirm: [followUp: string];
  close: [];
}>();

// Form state
const followUp = ref('');
const isSubmitting = ref(false);

// Reset form when modal opens
watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      followUp.value = '';
      isSubmitting.value = false;
    }
  }
);

// Computed
const canSubmit = computed(() => {
  return followUp.value.trim().length > 0 && !isSubmitting.value;
});

const truncatedSummary = computed(() => {
  if (!props.discussion?.summary) return null;
  const summary = props.discussion.summary;
  if (summary.length <= 200) return summary;
  return summary.slice(0, 200) + '...';
});

// Handlers
function handleConfirm() {
  if (!canSubmit.value) return;
  isSubmitting.value = true;
  emit('confirm', followUp.value.trim());
}

function handleClose() {
  if (isSubmitting.value) return;
  emit('close');
}

function handleBackdropClick(event: MouseEvent) {
  if (event.target === event.currentTarget) {
    handleClose();
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="visible"
        class="modal-backdrop"
        @click="handleBackdropClick"
      >
        <div class="modal-container">
          <!-- Header -->
          <div class="modal-header">
            <h3 class="modal-title">继续讨论</h3>
            <button
              class="close-btn"
              :disabled="isSubmitting"
              @click="handleClose"
            >
              <svg
                class="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          <!-- Content -->
          <div class="modal-content">
            <!-- Original topic -->
            <div class="info-section">
              <label class="info-label">原议题</label>
              <p class="info-value topic">{{ discussion?.topic }}</p>
            </div>

            <!-- Original summary -->
            <div v-if="truncatedSummary" class="info-section">
              <label class="info-label">原讨论摘要</label>
              <p class="info-value summary">{{ truncatedSummary }}</p>
            </div>

            <!-- Divider -->
            <div class="divider" />

            <!-- Follow-up input -->
            <div class="input-section">
              <label class="input-label" for="follow-up">
                追加问题/方向
              </label>
              <textarea
                id="follow-up"
                v-model="followUp"
                class="follow-up-input"
                placeholder="例如：想深入讨论装备强化的数值平衡..."
                :disabled="isSubmitting"
                rows="4"
              />
            </div>
          </div>

          <!-- Footer -->
          <div class="modal-footer">
            <button
              class="btn btn-secondary"
              :disabled="isSubmitting"
              @click="handleClose"
            >
              取消
            </button>
            <button
              class="btn btn-primary"
              :disabled="!canSubmit"
              @click="handleConfirm"
            >
              <svg
                v-if="isSubmitting"
                class="animate-spin w-4 h-4 mr-2"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                />
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              {{ isSubmitting ? '创建中...' : '继续讨论' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1),
    0 10px 10px -5px rgba(0, 0, 0, 0.04);
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
  margin: 16px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.close-btn {
  padding: 4px;
  color: #6b7280;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-btn:hover:not(:disabled) {
  background-color: #f3f4f6;
  color: #374151;
}

.close-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.modal-content {
  padding: 20px;
}

.info-section {
  margin-bottom: 16px;
}

.info-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  margin-bottom: 4px;
}

.info-value {
  color: #111827;
}

.info-value.topic {
  font-size: 16px;
  font-weight: 500;
}

.info-value.summary {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.5;
}

.divider {
  height: 1px;
  background-color: #e5e7eb;
  margin: 20px 0;
}

.input-section {
  margin-bottom: 8px;
}

.input-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

.follow-up-input {
  width: 100%;
  padding: 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.follow-up-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.follow-up-input:disabled {
  background-color: #f9fafb;
  cursor: not-allowed;
}

.follow-up-input::placeholder {
  color: #9ca3af;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
  background-color: #f9fafb;
  border-radius: 0 0 12px 12px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  transition: all 0.2s;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: white;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #f9fafb;
}

.btn-primary {
  background-color: #10b981;
  color: white;
  border: none;
}

.btn-primary:hover:not(:disabled) {
  background-color: #059669;
}

/* Transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
