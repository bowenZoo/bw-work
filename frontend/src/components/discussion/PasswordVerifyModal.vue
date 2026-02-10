<script setup lang="ts">
import { ref } from 'vue'
import { verifyDiscussionPassword } from '@/api/discussion'

const props = defineProps<{
  discussionId: string
  topic?: string
}>()

const emit = defineEmits<{
  verified: []
  cancel: []
}>()

const password = ref('')
const error = ref('')
const loading = ref(false)
const showPassword = ref(false)

async function verify() {
  if (!password.value.trim()) {
    error.value = '请输入密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const result = await verifyDiscussionPassword(props.discussionId, password.value)
    if (result.verified) {
      const verified = JSON.parse(sessionStorage.getItem('verified_discussions') || '{}')
      verified[props.discussionId] = true
      sessionStorage.setItem('verified_discussions', JSON.stringify(verified))
      emit('verified')
    } else {
      error.value = '密码错误，请重试'
    }
  } catch {
    error.value = '验证失败，请重试'
  } finally {
    loading.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') verify()
}

function handleOverlayClick(event: MouseEvent) {
  if ((event.target as HTMLElement).classList.contains('password-overlay')) {
    emit('cancel')
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="password-overlay" @click="handleOverlayClick">
      <div class="password-modal">
        <!-- Lock icon -->
        <div class="modal-icon">
          <svg class="lock-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>

        <!-- Title -->
        <h3 class="modal-title">需要密码访问</h3>
        <p v-if="props.topic" class="modal-topic" :title="props.topic">{{ props.topic }}</p>
        <p v-else class="modal-topic">此讨论已设置密码保护</p>

        <!-- Password input -->
        <div class="input-group">
          <div class="input-wrapper">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              class="password-input"
              placeholder="请输入访问密码"
              :disabled="loading"
              autofocus
              @keydown="onKeydown"
            />
            <button
              class="toggle-visibility"
              type="button"
              @click="showPassword = !showPassword"
              :title="showPassword ? '隐藏密码' : '显示密码'"
            >
              <!-- Eye icon (show) -->
              <svg v-if="!showPassword" class="eye-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              <!-- Eye-off icon (hide) -->
              <svg v-else class="eye-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
            </button>
          </div>
          <p v-if="error" class="error-text">{{ error }}</p>
        </div>

        <!-- Actions -->
        <div class="modal-actions">
          <button class="btn-cancel" @click="emit('cancel')" :disabled="loading">
            返回首页
          </button>
          <button class="btn-verify" :disabled="loading" @click="verify">
            <svg v-if="loading" class="spinner" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>{{ loading ? '验证中...' : '确认' }}</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.password-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(6px);
}

.password-modal {
  background: var(--bg-secondary, #ffffff);
  border-radius: 12px;
  width: 380px;
  max-width: 90vw;
  padding: 32px 28px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1px solid var(--border-color, #e5e7eb);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.modal-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--bg-tertiary, #f3f4f6);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.lock-icon {
  width: 24px;
  height: 24px;
  color: var(--text-secondary, #737373);
}

.modal-title {
  margin: 0 0 6px;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary, #171717);
}

.modal-topic {
  margin: 0 0 20px;
  font-size: 13px;
  color: var(--text-secondary, #737373);
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.input-group {
  width: 100%;
  margin-bottom: 20px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.password-input {
  width: 100%;
  padding: 10px 40px 10px 14px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-primary, #171717);
  background: var(--bg-primary, #fafafa);
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.password-input:focus {
  outline: none;
  border-color: var(--primary-color, #0a0a0a);
  box-shadow: 0 0 0 2px rgba(10, 10, 10, 0.08);
}

.password-input::placeholder {
  color: var(--text-weak, #a3a3a3);
}

.password-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-visibility {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-weak, #a3a3a3);
  transition: color 0.15s;
}

.toggle-visibility:hover {
  color: var(--text-secondary, #737373);
}

.eye-icon {
  width: 18px;
  height: 18px;
}

.error-text {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--danger-color, #dc2626);
}

.modal-actions {
  display: flex;
  gap: 10px;
  width: 100%;
}

.btn-cancel {
  flex: 1;
  padding: 9px 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary, #737373);
  background: var(--bg-primary, #fafafa);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-cancel:hover:not(:disabled) {
  background: var(--bg-tertiary, #f3f4f6);
}

.btn-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-verify {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 16px;
  font-size: 14px;
  font-weight: 500;
  color: white;
  background: var(--primary-color, #0a0a0a);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-verify:hover:not(:disabled) {
  background: #171717;
}

.btn-verify:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
