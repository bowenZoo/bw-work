<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAdminAuth } from '@/composables/useAdminAuth';
import AdminAuthWrapper from './AdminAuthWrapper.vue';
import { Save, Check, AlertCircle } from 'lucide-vue-next';

const { apiRequest } = useAdminAuth();
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref('');

const config = ref({
  provider: 'dall-e',
  api_key: '',
  model: 'dall-e-3',
  size: '1024x1024',
  quality: 'standard',
});

async function load() {
  loading.value = true;
  try {
    const data = await apiRequest<any>('/config/image');
    if (data) Object.assign(config.value, data);
  } catch {}
  loading.value = false;
}

async function save_() {
  saving.value = true; error.value = ''; saved.value = false;
  try {
    await apiRequest('/config/image', { method:'PUT', body:JSON.stringify(config.value) });
    saved.value = true; setTimeout(() => saved.value = false, 2000);
  } catch (e:any) { error.value = e.message || '保存失败'; }
  finally { saving.value = false; }
}

onMounted(load);
</script>

<template>
<AdminAuthWrapper>
  <div class="img-panel">
    <h2 class="title">图片模型配置</h2>
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else class="card">
      <div class="field"><label>Provider</label>
        <select v-model="config.provider" class="input">
          <option value="dall-e">DALL-E</option>
          <option value="stability">Stability AI</option>
          <option value="midjourney">Midjourney</option>
        </select>
      </div>
      <div class="field"><label>Model</label><input v-model="config.model" class="input" placeholder="dall-e-3" /></div>
      <div class="field"><label>API Key</label><input v-model="config.api_key" type="password" class="input" /></div>
      <div class="field-row">
        <div class="field"><label>尺寸</label>
          <select v-model="config.size" class="input">
            <option>1024x1024</option><option>1792x1024</option><option>1024x1792</option>
          </select>
        </div>
        <div class="field"><label>质量</label>
          <select v-model="config.quality" class="input">
            <option value="standard">Standard</option><option value="hd">HD</option>
          </select>
        </div>
      </div>
      <div class="actions">
        <button class="btn-save" :disabled="saving" @click="save_"><Save :size="14" /> {{ saving?'保存中...':'保存' }}</button>
        <span v-if="saved" class="msg-ok"><Check :size="14" /> 已保存</span>
        <span v-if="error" class="msg-err"><AlertCircle :size="14" /> {{ error }}</span>
      </div>
    </div>
  </div>
</AdminAuthWrapper>
</template>

<style scoped>
.img-panel { max-width:480px; }
.title { font-size:20px; font-weight:700; margin:0 0 16px; }
.loading { padding:40px; text-align:center; color:#9ca3af; }
.card { padding:18px; background:#f9fafb; border-radius:10px; }
.field { display:flex; flex-direction:column; gap:4px; margin-bottom:12px; }
.field label { font-size:12px; font-weight:500; color:#6b7280; }
.field-row { display:flex; gap:12px; }
.input { padding:7px 10px; border:1px solid #e5e7eb; border-radius:6px; font-size:14px; }
.input:focus { outline:none; border-color:#3b82f6; }
.actions { display:flex; align-items:center; gap:8px; margin-top:4px; }
.btn-save { display:inline-flex; align-items:center; gap:4px; padding:7px 14px; font-size:13px; font-weight:500; background:#3b82f6; color:#fff; border:none; border-radius:6px; cursor:pointer; }
.btn-save:hover { background:#2563eb; }
.msg-ok { font-size:12px; color:#16a34a; display:flex; align-items:center; gap:3px; }
.msg-err { font-size:12px; color:#dc2626; display:flex; align-items:center; gap:3px; }
</style>
