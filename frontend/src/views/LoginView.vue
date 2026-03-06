<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const activeTab = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const displayName = ref('')
const showPassword = ref(false)
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''
  if (!username.value || !password.value) return
  loading.value = true
  try {
    if (activeTab.value === 'login') {
      await userStore.login(username.value, password.value)
    } else {
      if (password.value !== confirmPassword.value) {
        error.value = '两次密码不一致'
        return
      }
      await userStore.register(username.value, password.value, displayName.value || undefined)
    }
    router.push('/')
  } catch (e: any) {
    error.value = e.message || (activeTab.value === 'login' ? '登录失败' : '注册失败')
  } finally {
    loading.value = false
  }
}

function switchTab(tab: 'login' | 'register') {
  activeTab.value = tab
  error.value = ''
}
</script>

<template>
  <div class="login-root">
    <!-- Left Brand Panel -->
    <div class="left-panel">
      <div class="deco deco-1" />
      <div class="deco deco-2" />
      <div class="deco deco-3" />
      <div class="deco deco-4" />
      <div class="brand-wrap">
        <div class="brand-group">
          <div class="brand-title">BW-Work</div>
          <div class="brand-sub">百万工作台</div>
        </div>
        <div class="desc-group">
          <div class="desc-text">AI驱动的协作讨论平台</div>
          <div class="desc-text">让创意碰撞，让决策更智慧</div>
        </div>
      </div>
    </div>

    <!-- Right Form Panel -->
    <div class="right-panel">
      <div class="form-card">
        <!-- Tabs -->
        <div class="tabs-container">
          <div
            class="tab"
            :class="{ active: activeTab === 'login' }"
            @click="switchTab('login')"
          >登录</div>
          <div
            class="tab"
            :class="{ active: activeTab === 'register' }"
            @click="switchTab('register')"
          >注册</div>
        </div>

        <!-- Fields -->
        <div class="form-fields">
          <div v-if="activeTab === 'register'" class="field-group">
            <label class="field-label">显示名称 <span class="opt">（可选）</span></label>
            <input
              v-model="displayName"
              class="field-input"
              type="text"
              placeholder="你想被怎么称呼？"
            />
          </div>
          <div class="field-group">
            <label class="field-label">用户名</label>
            <input
              v-model="username"
              class="field-input"
              type="text"
              placeholder="请输入用户名"
              autofocus
              @keydown.enter="handleSubmit"
            />
          </div>
          <div class="field-group">
            <label class="field-label">密码</label>
            <div class="input-wrap">
              <input
                v-model="password"
                class="field-input"
                :type="showPassword ? 'text' : 'password'"
                placeholder="请输入密码"
                @keydown.enter="handleSubmit"
              />
              <button class="eye-btn" type="button" @click="showPassword = !showPassword">
                <svg v-if="!showPassword" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
            </div>
          </div>
          <div v-if="activeTab === 'register'" class="field-group">
            <label class="field-label">确认密码</label>
            <input
              v-model="confirmPassword"
              class="field-input"
              type="password"
              placeholder="再次输入密码"
              @keydown.enter="handleSubmit"
            />
          </div>
          <div v-if="activeTab === 'login'" class="options-row">
            <label class="remember-label">
              <input type="checkbox" style="accent-color:#7C3AED" /> 记住我
            </label>
          </div>
        </div>

        <!-- Error -->
        <p v-if="error" class="error-msg">{{ error }}</p>

        <!-- Submit -->
        <button
          class="submit-btn"
          :disabled="loading || !username || !password"
          @click="handleSubmit"
        >
          {{ loading ? '处理中...' : (activeTab === 'login' ? '登录' : '注册') }}
        </button>

        <!-- Switch -->
        <div class="switch-row">
          <span class="switch-text">{{ activeTab === 'login' ? '还没有账号？' : '已有账号？' }}</span>
          <span class="switch-link" @click="switchTab(activeTab === 'login' ? 'register' : 'login')">
            {{ activeTab === 'login' ? '注册' : '去登录' }}
          </span>
        </div>
      </div>
      <div class="copyright">© 2026 BW-Work</div>
    </div>
  </div>
</template>

<style scoped>
.login-root {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  font-family: 'Inter', sans-serif;
}

/* ── Left Brand Panel ── */
.left-panel {
  width: 50%;
  flex-shrink: 0;
  background: linear-gradient(180deg, #7C3AED 0%, #9F67FF 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}
.deco {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}
.deco-1 { width: 180px; height: 180px; background: rgba(255,255,255,0.06); top: 50px; left: 30px; }
.deco-2 { width: 120px; height: 120px; background: rgba(255,255,255,0.05); bottom: 40px; right: 40px; }
.deco-3 { width: 80px; height: 80px; background: rgba(255,255,255,0.05); bottom: 80px; left: 80px; }
.deco-4 { width: 60px; height: 60px; background: rgba(255,255,255,0.04); top: 200px; right: 60px; }

.brand-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 0 60px;
  z-index: 1;
}
.brand-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.brand-title {
  font-size: 48px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -1px;
  text-align: center;
}
.brand-sub {
  font-size: 24px;
  font-weight: 600;
  color: rgba(255,255,255,0.8);
  text-align: center;
}
.desc-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.desc-text {
  font-size: 16px;
  color: rgba(255,255,255,0.7);
  text-align: center;
}

/* ── Right Panel ── */
.right-panel {
  flex: 1;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 80px;
  gap: 16px;
}
.form-card {
  display: flex;
  flex-direction: column;
  gap: 24px;
  width: 100%;
  max-width: 360px;
}

/* Tabs */
.tabs-container {
  display: flex;
  background: #F4F4F5;
  border-radius: 999px;
  padding: 4px;
  height: 44px;
  width: 240px;
  margin: 0 auto;
}
.tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 500;
  color: #71717A;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}
.tab.active {
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  color: #18181B;
  font-weight: 600;
}

/* Form */
.form-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field-label {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}
.opt { color: #9CA3AF; font-weight: 400; }
.field-input {
  height: 44px;
  border-radius: 10px;
  border: 1.5px solid #D1D5DB;
  padding: 0 14px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
}
.field-input:focus { border-color: #7C3AED; box-shadow: 0 0 0 3px rgba(124,58,237,0.1); }
.input-wrap { position: relative; }
.input-wrap .field-input { padding-right: 44px; }
.eye-btn {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: #9CA3AF;
  display: flex;
  align-items: center;
  padding: 0;
}
.options-row { display: flex; align-items: center; justify-content: space-between; }
.remember-label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #6B7280; cursor: pointer; }

.error-msg { font-size: 13px; color: #DC2626; margin: 0; }

.submit-btn {
  height: 48px;
  border-radius: 12px;
  background: #7C3AED;
  border: none;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: opacity 0.15s;
  width: 100%;
}
.submit-btn:hover:not(:disabled) { opacity: 0.9; }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.switch-row {
  display: flex;
  justify-content: center;
  gap: 4px;
  font-size: 13px;
}
.switch-text { color: #6B7280; }
.switch-link { color: #7C3AED; font-weight: 600; cursor: pointer; }
.switch-link:hover { text-decoration: underline; }

.copyright { font-size: 12px; color: #9CA3AF; text-align: center; }

@media (max-width: 768px) {
  .left-panel { display: none; }
  .right-panel { padding: 0 24px; }
}
</style>
