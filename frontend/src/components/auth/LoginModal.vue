<script setup lang="ts">
import { ref } from 'vue';
import { X } from 'lucide-vue-next';
import { useUserStore } from '@/stores/user';
import LetterAvatar from '@/components/common/LetterAvatar.vue';

const emit = defineEmits<{ close: [] }>();
const userStore = useUserStore();

const activeTab = ref<'login' | 'register'>('login');
const username = ref('');
const password = ref('');
const confirmPassword = ref('');
const displayName = ref('');
const error = ref('');
const loading = ref(false);

async function handleLogin() {
  error.value = '';
  loading.value = true;
  try {
    await userStore.login(username.value, password.value);
    emit('success');
    emit('close');
  } catch (e: any) { error.value = e.message || '登录失败'; }
  finally { loading.value = false; }
}

async function handleRegister() {
  error.value = '';
  if (password.value !== confirmPassword.value) { error.value = '两次密码不一致'; return; }
  loading.value = true;
  try {
    await userStore.register(username.value, password.value, displayName.value || undefined);
    emit('success');
    emit('close');
  } catch (e: any) { error.value = e.message || '注册失败'; }
  finally { loading.value = false; }
}

function handleSubmit() {
  if (activeTab.value === 'login') handleLogin(); else handleRegister();
}

function switchTab(tab: 'login' | 'register') { activeTab.value = tab; error.value = ''; }
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="modal" @keydown.enter="handleSubmit">
      <div class="modal-head">
        <div class="tabs">
          <button :class="['tab', {on: activeTab==='login'}]" @click="switchTab('login')">登录</button>
          <button :class="['tab', {on: activeTab==='register'}]" @click="switchTab('register')">注册</button>
        </div>
        <button class="close" @click="emit('close')"><X :size="18" /></button>
      </div>

      <div class="modal-body">
        <!-- Register: show letter avatar preview -->
        <div v-if="activeTab === 'register'" class="avatar-preview">
          <LetterAvatar :name="displayName || username || '?'" :size="64" />
          <span class="avatar-hint">头像将根据名称自动生成</span>
        </div>

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
            <label>显示名称 <span class="opt">（可选）</span></label>
            <input v-model="displayName" type="text" placeholder="你想被怎么称呼？" />
          </div>
        </template>

        <p v-if="error" class="error">{{ error }}</p>
        <button class="submit" :disabled="loading || !username || !password" @click="handleSubmit">
          {{ loading ? '处理中...' : (activeTab === 'login' ? '登录' : '注册') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 2000; }
.modal { background: #fff; border-radius: 12px; width: 380px; max-width: 95vw; box-shadow: 0 20px 40px rgba(0,0,0,0.15); overflow: hidden; }
.modal-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px 0; }
.tabs { display: flex; }
.tab { padding: 8px 20px; font-size: 14px; font-weight: 500; color: #9ca3af; border: none; border-bottom: 2px solid transparent; background: none; cursor: pointer; }
.tab.on { color: #3b82f6; border-bottom-color: #3b82f6; }
.close { color: #9ca3af; padding: 4px; border-radius: 6px; background: none; border: none; cursor: pointer; }
.close:hover { background: #f3f4f6; }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }

.avatar-preview { display: flex; flex-direction: column; align-items: center; gap: 8px; padding-bottom: 12px; border-bottom: 1px solid #f0f0f0; }
.avatar-hint { font-size: 12px; color: #9ca3af; }

.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 13px; font-weight: 500; color: #374151; }
.opt { color: #9ca3af; font-weight: 400; }
.field input { padding: 9px 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; }
.field input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.1); }
.error { color: #dc2626; font-size: 13px; margin: 0; }
.submit { padding: 10px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; }
.submit:hover:not(:disabled) { background: #2563eb; }
.submit:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
