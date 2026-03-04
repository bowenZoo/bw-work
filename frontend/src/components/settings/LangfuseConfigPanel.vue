<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAdminApi } from './useAdminApi';

import { Save, Check, AlertCircle, PlayCircle } from 'lucide-vue-next';

const { adminRequest } = useAdminApi();
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref('');
const testing = ref(false);
const testResult = ref<{ok:boolean;msg:string}|null>(null);

const config = ref({
  enabled: false,
  public_key: '',
  secret_key: '',
  host: 'https://cloud.langfuse.com',
});

async function load() {
  loading.value = true;
  try {
    const data = await apiRequest<any>('/config/langfuse');
    if (data) Object.assign(config.value, data);
  } catch {}
  loading.value = false;
}

async function save_() {
  saving.value = true; error.value = ''; saved.value = false;
  try {
    await adminRequest('/config/langfuse', { method:'PUT', body:JSON.stringify(config.value) });
    saved.value = true; setTimeout(() => saved.value = false, 2000);
  } catch (e:any) { error.value = e.message || '保存失败'; }
  finally { saving.value = false; }
}

async function test_() {
  testing.value = true; testResult.value = null;
  try {
    const r = await apiRequest<{success:boolean;message?:string;error?:string}>('/config/test', { method:'POST', body:JSON.stringify({category:'langfuse'}) });
    testResult.value = { ok: r.success, msg: r.message || r.error || '' };
  } catch (e:any) { testResult.value = { ok:false, msg: e.message }; }
  finally { testing.value = false; }
}

onMounted(load);
</script>

<template>
  <div class="lfuse-panel">
    <h2 class="title">Langfuse 配置</h2>
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else class="card">
      <div class="field toggle-field">
        <label>启用 Langfuse</label>
        <label class="switch"><input type="checkbox" v-model="config.enabled" /><span class="slider" /></label>
      </div>
      <div class="field"><label>Host</label><input v-model="config.host" class="input" /></div>
      <div class="field"><label>Public Key</label><input v-model="config.public_key" class="input" /></div>
      <div class="field"><label>Secret Key</label><input v-model="config.secret_key" type="password" class="input" /></div>
      <div class="actions">
        <button class="btn-save" :disabled="saving" @click="save_"><Save :size="14" /> {{ saving?'保存中...':'保存' }}</button>
        <button class="btn-test" :disabled="testing" @click="test_"><PlayCircle :size="14" /> {{ testing?'测试中...':'测试连接' }}</button>
        <span v-if="saved" class="msg-ok"><Check :size="14" /> 已保存</span>
        <span v-if="error" class="msg-err"><AlertCircle :size="14" /> {{ error }}</span>
      </div>
      <div v-if="testResult" class="test-result" :class="{ok:testResult.ok}">{{ testResult.ok?'✅ 连接成功':'❌ '+testResult.msg }}</div>
    </div>
  </div>
</template>

<style scoped>
.lfuse-panel { max-width:560px; }
.title { font-size:20px; font-weight:700; margin:0 0 16px; }
.loading { padding:40px; text-align:center; color:#9ca3af; }
.card { padding:18px; background:#f9fafb; border-radius:10px; }
.field { display:flex; flex-direction:column; gap:4px; margin-bottom:12px; }
.field label { font-size:12px; font-weight:500; color:#6b7280; }
.toggle-field { flex-direction:row; align-items:center; justify-content:space-between; }
.switch { position:relative; width:40px; height:22px; }
.switch input { opacity:0; width:0; height:0; }
.slider { position:absolute; inset:0; background:#d1d5db; border-radius:11px; cursor:pointer; transition:.2s; }
.slider::before { content:''; position:absolute; width:18px; height:18px; left:2px; bottom:2px; background:#fff; border-radius:50%; transition:.2s; }
.switch input:checked + .slider { background:#3b82f6; }
.switch input:checked + .slider::before { transform:translateX(18px); }
.input { padding:7px 10px; border:1px solid #e5e7eb; border-radius:6px; font-size:14px; }
.input:focus { outline:none; border-color:#3b82f6; }
.actions { display:flex; align-items:center; gap:8px; margin-top:4px; }
.btn-save,.btn-test { display:inline-flex; align-items:center; gap:4px; padding:7px 14px; font-size:13px; font-weight:500; border:none; border-radius:6px; cursor:pointer; }
.btn-save { background:#3b82f6; color:#fff; }
.btn-test { background:#f3f4f6; color:#374151; }
.btn-save:hover { background:#2563eb; }
.btn-test:hover { background:#e5e7eb; }
.msg-ok { font-size:12px; color:#16a34a; display:flex; align-items:center; gap:3px; }
.msg-err { font-size:12px; color:#dc2626; display:flex; align-items:center; gap:3px; }
.test-result { margin-top:10px; font-size:12px; padding:6px 10px; border-radius:4px; background:#f3f4f6; }
.test-result.ok { background:#f0fdf4; color:#16a34a; }
</style>
