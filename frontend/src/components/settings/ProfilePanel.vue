<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useUserStore } from '@/stores/user';
import LetterAvatar from '@/components/common/LetterAvatar.vue';
import { Check, AlertCircle } from 'lucide-vue-next';

const userStore = useUserStore();
const displayName = ref('');
const email = ref('');
const saving = ref(false);
const saved = ref(false);
const error = ref('');

// Password change
const oldPw = ref('');
const newPw = ref('');
const confirmPw = ref('');
const pwSaving = ref(false);
const pwMsg = ref('');
const pwError = ref('');

onMounted(() => {
  displayName.value = userStore.user?.display_name || '';
  email.value = (userStore.user as any)?.email || '';
});

async function saveProfile() {
  saving.value = true; error.value = ''; saved.value = false;
  try {
    await userStore.updateProfile({ display_name: displayName.value, email: email.value || undefined });
    saved.value = true;
    setTimeout(() => saved.value = false, 2000);
  } catch (e: any) { error.value = e.message || '保存失败'; }
  finally { saving.value = false; }
}

async function savePw() {
  pwError.value = ''; pwMsg.value = '';
  if (newPw.value !== confirmPw.value) { pwError.value = '两次密码不一致'; return; }
  if (newPw.value.length < 4) { pwError.value = '密码至少4位'; return; }
  pwSaving.value = true;
  try {
    await userStore.changePassword(oldPw.value, newPw.value);
    pwMsg.value = '密码修改成功';
    oldPw.value = ''; newPw.value = ''; confirmPw.value = '';
    setTimeout(() => pwMsg.value = '', 3000);
  } catch (e: any) { pwError.value = e.message || '修改失败'; }
  finally { pwSaving.value = false; }
}
</script>

<template>
  <div class="profile-panel">
    <h2 class="section-title">个人中心</h2>

    <div class="profile-card">
      <div class="avatar-area">
        <LetterAvatar :name="displayName || userStore.user?.username || '?'" :size="64" />
      </div>
      <div class="info-area">
        <div class="field">
          <label>用户名</label>
          <input :value="userStore.user?.username" disabled class="input disabled" />
        </div>
        <div class="field">
          <label>显示名称</label>
          <input v-model="displayName" class="input" placeholder="你想被怎么称呼？" />
        </div>
        <div class="field">
          <label>邮箱 <span class="opt">(可选)</span></label>
          <input v-model="email" type="email" class="input" placeholder="your@email.com" />
        </div>
        <div class="field">
          <label>角色</label>
          <span class="role-badge">{{ userStore.user?.role === 'superadmin' ? '超级管理员' : '普通用户' }}</span>
        </div>
        <div class="actions">
          <button class="btn-save" :disabled="saving" @click="saveProfile">{{ saving ? '保存中...' : '保存' }}</button>
          <span v-if="saved" class="msg-ok"><Check :size="14" /> 已保存</span>
          <span v-if="error" class="msg-err"><AlertCircle :size="14" /> {{ error }}</span>
        </div>
      </div>
    </div>

    <h3 class="sub-title">修改密码</h3>
    <div class="pw-card">
      <div class="field"><label>当前密码</label><input v-model="oldPw" type="password" class="input" /></div>
      <div class="field"><label>新密码</label><input v-model="newPw" type="password" class="input" /></div>
      <div class="field"><label>确认新密码</label><input v-model="confirmPw" type="password" class="input" /></div>
      <div class="actions">
        <button class="btn-save" :disabled="pwSaving || !oldPw || !newPw" @click="savePw">{{ pwSaving ? '修改中...' : '修改密码' }}</button>
        <span v-if="pwMsg" class="msg-ok"><Check :size="14" /> {{ pwMsg }}</span>
        <span v-if="pwError" class="msg-err"><AlertCircle :size="14" /> {{ pwError }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-panel { max-width: 600px; }
.section-title { font-size: 20px; font-weight: 700; margin: 0 0 20px; }
.sub-title { font-size: 15px; font-weight: 600; margin: 24px 0 12px; }
.profile-card { display: flex; gap: 24px; padding: 20px; background: #f9fafb; border-radius: 10px; }
.avatar-area { flex-shrink: 0; padding-top: 4px; }
.info-area { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.pw-card { display: flex; flex-direction: column; gap: 12px; padding: 20px; background: #f9fafb; border-radius: 10px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; font-weight: 500; color: #6b7280; }
.opt { color: #9ca3af; font-weight: 400; }
.input { padding: 8px 10px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 14px; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
.input.disabled { background: #f3f4f6; color: #9ca3af; cursor: not-allowed; }
.role-badge { display: inline-block; padding: 2px 8px; font-size: 12px; background: #e0e7ff; color: #4338ca; border-radius: 4px; font-weight: 500; }
.actions { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.btn-save { padding: 7px 16px; font-size: 13px; font-weight: 500; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-save:hover:not(:disabled) { background: #2563eb; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.msg-ok { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #16a34a; }
.msg-err { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #dc2626; }
</style>
