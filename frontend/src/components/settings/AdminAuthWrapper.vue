<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAdminAuth } from '@/composables/useAdminAuth';
import { Lock } from 'lucide-vue-next';

const { apiRequest, login } = useAdminAuth();
const authed = ref(false);
const checking = ref(true);
const username = ref('');
const password = ref('');
const loginError = ref('');
const loggingIn = ref(false);

onMounted(async () => {
  try {
    await apiRequest('/auth/me');
    authed.value = true;
  } catch { authed.value = false; }
  checking.value = false;
});

async function doLogin() {
  loggingIn.value = true; loginError.value = '';
  try {
    await login(username.value, password.value);
    authed.value = true;
  } catch (e: any) { loginError.value = e.message || '登录失败'; }
  finally { loggingIn.value = false; }
}
</script>

<template>
  <div v-if="checking" class="auth-loading">验证管理员权限...</div>
  <div v-else-if="!authed" class="admin-login-box">
    <div class="login-icon"><Lock :size="20" /></div>
    <p class="login-hint">此功能需要管理员权限，请登录管理后台账号</p>
    <form @submit.prevent="doLogin" class="login-form">
      <input v-model="username" placeholder="管理员用户名" class="input" />
      <input v-model="password" type="password" placeholder="密码" class="input" />
      <button class="btn-login" :disabled="loggingIn || !username || !password">{{ loggingIn ? '登录中...' : '登录' }}</button>
      <p v-if="loginError" class="login-err">{{ loginError }}</p>
    </form>
  </div>
  <slot v-else />
</template>

<style scoped>
.auth-loading { padding: 40px; text-align: center; color: #9ca3af; }
.admin-login-box { max-width: 320px; margin: 40px auto; text-align: center; }
.login-icon { margin-bottom: 12px; color: #6b7280; }
.login-hint { font-size: 13px; color: #6b7280; margin-bottom: 16px; }
.login-form { display: flex; flex-direction: column; gap: 10px; }
.input { padding: 8px 12px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 14px; }
.input:focus { outline: none; border-color: #3b82f6; }
.btn-login { padding: 8px; font-size: 14px; font-weight: 500; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-login:hover:not(:disabled) { background: #2563eb; }
.btn-login:disabled { opacity: 0.5; }
.login-err { font-size: 12px; color: #dc2626; margin: 0; }
</style>
