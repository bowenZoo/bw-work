<script setup lang="ts">
import { ref, computed } from 'vue';
import { X, RefreshCw } from 'lucide-vue-next';
import { useUserStore } from '@/stores/user';

const emit = defineEmits<{ close: [] }>();
const userStore = useUserStore();

const activeTab = ref<'login' | 'register'>('login');
const username = ref('');
const password = ref('');
const confirmPassword = ref('');
const displayName = ref('');
const allAvatars = Array.from({length: 20}, (_, i) => `/avatars/avatar_${String(i+1).padStart(2,'0')}.png`);

function pickRandom(exclude?: string): string {
  const pool = exclude ? allAvatars.filter(a => a !== exclude) : allAvatars;
  return pool[Math.floor(Math.random() * pool.length)];
}

const selectedAvatar = ref(pickRandom());

const DISPLAY_COUNT = 8;
const candidateSeed = ref(0);
const candidates = computed(() => {
  void candidateSeed.value;
  const pool = allAvatars.filter(a => a !== selectedAvatar.value);
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, DISPLAY_COUNT);
});

function refreshCandidates() { candidateSeed.value++; }

function selectAvatar(src: string) {
  selectedAvatar.value = src;
  candidateSeed.value++;
}

const error = ref('');
const loading = ref(false);

async function handleLogin() {
  error.value = '';
  loading.value = true;
  try {
    await userStore.login(username.value, password.value);
    emit('close');
  } catch (e: any) {
    error.value = e.message || '登录失败';
  } finally { loading.value = false; }
}

async function handleRegister() {
  error.value = '';
  if (password.value !== confirmPassword.value) { error.value = '两次密码输入不一致'; return; }
  loading.value = true;
  try {
    await userStore.register(username.value, password.value, displayName.value || undefined, selectedAvatar.value || undefined);
    emit('close');
  } catch (e: any) {
    error.value = e.message || '注册失败';
  } finally { loading.value = false; }
}

function handleSubmit() {
  if (activeTab.value === 'login') handleLogin();
  else handleRegister();
}

function switchTab(tab: 'login' | 'register') {
  activeTab.value = tab;
  error.value = '';
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-content" @keydown.enter="handleSubmit">
      <div class="modal-header">
        <div class="tabs">
          <button :class="['tab', { active: activeTab === 'login' }]" @click="switchTab('login')">登录</button>
          <button :class="['tab', { active: activeTab === 'register' }]" @click="switchTab('register')">注册</button>
        </div>
        <button class="close-btn" @click="emit('close')"><X :size="18" /></button>
      </div>

      <div class="modal-body">
        <!-- 注册：头像选择在顶部 -->
        <template v-if="activeTab === 'register'">
          <div class="avatar-section">
            <div class="avatar-main">
              <div class="avatar-selected">
                <img :src="selectedAvatar" alt="avatar" />
              </div>
              <span class="avatar-hint">选择你的头像</span>
            </div>
            <div class="avatar-candidates">
              <div v-for="src in candidates" :key="src" class="avatar-option" @click="selectAvatar(src)">
                <img :src="src" alt="avatar" />
              </div>
              <button class="avatar-refresh" @click="refreshCandidates" title="换一批">
                <RefreshCw :size="16" />
              </button>
            </div>
          </div>
        </template>

        <div class="field">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="请输入用户名" autofocus />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" />
        </div>

        <template v-if="activeTab === 'register'">
          <div class="field">
            <label>确认密码</label>
            <input v-model="confirmPassword" type="password" placeholder="再次输入密码" />
          </div>
          <div class="field">
            <label>显示名称 <span class="optional">（可选）</span></label>
            <input v-model="displayName" type="text" placeholder="你想被怎么称呼？" />
          </div>
        </template>

        <p v-if="error" class="error">{{ error }}</p>
        <button class="submit-btn" :disabled="loading || !username || !password" @click="handleSubmit">
          {{ loading ? '处理中...' : (activeTab === 'login' ? '登录' : '注册') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 2000; }
.modal-content { background: var(--bg-primary, #fff); border-radius: 12px; width: 380px; max-width: 95vw; box-shadow: 0 20px 40px rgba(0,0,0,0.15); overflow: hidden; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px 0; }
.tabs { display: flex; }
.tab { padding: 8px 20px; font-size: 14px; font-weight: 500; color: var(--text-secondary, #9ca3af); border-bottom: 2px solid transparent; transition: all 0.2s; background: none; border-radius: 0; }
.tab.active { color: var(--primary-color, #3b82f6); border-bottom-color: var(--primary-color, #3b82f6); }
.close-btn { color: var(--text-secondary, #9ca3af); padding: 4px; border-radius: 6px; }
.close-btn:hover { background: #f3f4f6; }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }

/* Avatar */
.avatar-section { display: flex; flex-direction: column; align-items: center; gap: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color, #f0f0f0); }
.avatar-main { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.avatar-selected { width: 72px; height: 72px; border-radius: 50%; overflow: hidden; border: 3px solid var(--primary-color, #3b82f6); box-shadow: 0 4px 12px rgba(59,130,246,0.25); transition: transform 0.2s; }
.avatar-selected:hover { transform: scale(1.05); }
.avatar-selected img { width: 100%; height: 100%; object-fit: cover; }
.avatar-hint { font-size: 12px; color: var(--text-secondary, #9ca3af); }
.avatar-candidates { display: flex; align-items: center; justify-content: center; gap: 6px; flex-wrap: wrap; }
.avatar-option { width: 36px; height: 36px; border-radius: 50%; overflow: hidden; cursor: pointer; border: 2px solid transparent; transition: all 0.2s; flex-shrink: 0; }
.avatar-option img { width: 100%; height: 100%; object-fit: cover; }
.avatar-option:hover { border-color: rgba(59,130,246,0.5); transform: scale(1.15); }
.avatar-refresh { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: var(--text-secondary, #9ca3af); border: 2px dashed var(--border-color, #e5e7eb); transition: all 0.2s; cursor: pointer; background: none; flex-shrink: 0; }
.avatar-refresh:hover { border-color: var(--primary-color, #3b82f6); color: var(--primary-color, #3b82f6); background: rgba(59,130,246,0.05); }

.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 13px; font-weight: 500; color: var(--text-primary, #374151); }
.optional { color: var(--text-secondary, #9ca3af); font-weight: 400; }
.field input { padding: 9px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; font-size: 14px; transition: border-color 0.2s; }
.field input:focus { outline: none; border-color: var(--primary-color, #3b82f6); box-shadow: 0 0 0 3px rgba(59,130,246,0.1); }
.error { color: #dc2626; font-size: 13px; margin: 0; }
.submit-btn { padding: 10px; background: var(--primary-color, #3b82f6); color: #fff; border-radius: 8px; font-size: 14px; font-weight: 500; transition: background 0.2s; }
.submit-btn:hover:not(:disabled) { background: #2563eb; }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
