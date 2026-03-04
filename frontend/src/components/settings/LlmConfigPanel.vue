<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAdminAuth } from '@/composables/useAdminAuth';
import AdminAuthWrapper from './AdminAuthWrapper.vue';
import { Plus, Pencil, Trash2, Zap, Check, PlayCircle, AlertCircle } from 'lucide-vue-next';

const { apiRequest } = useAdminAuth();

interface LlmProfile {
  id: string; name: string; provider: string; model: string;
  api_key?: string; base_url?: string; is_active: boolean;
  temperature?: number; max_tokens?: number;
}

const profiles = ref<LlmProfile[]>([]);
const loading = ref(true);
const showForm = ref(false);
const editing = ref<LlmProfile | null>(null);
const testResult = ref<{ok:boolean;msg:string}|null>(null);
const testingId = ref('');

// Form
const form = ref({ name:'', provider:'openai', model:'', api_key:'', base_url:'', temperature:0.7, max_tokens:4096 });

async function load() {
  loading.value = true;
  try { profiles.value = await apiRequest<LlmProfile[]>('/config/llm/profiles'); }
  catch {}
  loading.value = false;
}

function startAdd() { editing.value = null; form.value = { name:'', provider:'openai', model:'', api_key:'', base_url:'', temperature:0.7, max_tokens:4096 }; showForm.value = true; }
function startEdit(p: LlmProfile) { editing.value = p; form.value = { name:p.name, provider:p.provider, model:p.model, api_key:'', base_url:p.base_url||'', temperature:p.temperature||0.7, max_tokens:p.max_tokens||4096 }; showForm.value = true; }

async function save() {
  const body: any = { ...form.value };
  if (!body.api_key) delete body.api_key;
  if (!body.base_url) delete body.base_url;
  try {
    if (editing.value) { await apiRequest(`/config/llm/profiles/${editing.value.id}`, { method:'PUT', body:JSON.stringify(body) }); }
    else { await apiRequest('/config/llm/profiles', { method:'POST', body:JSON.stringify(body) }); }
    showForm.value = false; await load();
  } catch {}
}

async function activate(id: string) {
  await apiRequest(`/config/llm/profiles/${id}/activate`, { method:'POST' }); await load();
}

async function remove(id: string) {
  if (!confirm('确认删除？')) return;
  await apiRequest(`/config/llm/profiles/${id}`, { method:'DELETE' }); await load();
}

async function test(id: string) {
  testingId.value = id; testResult.value = null;
  try {
    const r = await apiRequest<{success:boolean;message?:string;error?:string}>(`/config/test/llm/${id}`, { method:'POST' });
    testResult.value = { ok: r.success, msg: r.message || r.error || '' };
  } catch (e:any) { testResult.value = { ok:false, msg: e.message }; }
  testingId.value = '';
}

onMounted(load);
</script>

<template>
<AdminAuthWrapper>
  <div class="llm-panel">
    <div class="header-row">
      <h2 class="title">LLM 配置</h2>
      <button class="btn-add" @click="startAdd"><Plus :size="14" /> 新增配置</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else class="profile-list">
      <div v-for="p in profiles" :key="p.id" class="profile-card" :class="{active: p.is_active}">
        <div class="profile-header">
          <span class="profile-name">{{ p.name || p.model }}</span>
          <span v-if="p.is_active" class="active-badge"><Zap :size="12" /> 当前使用</span>
        </div>
        <div class="profile-meta">
          <span>{{ p.provider }}</span> · <span>{{ p.model }}</span>
          <span v-if="p.base_url"> · {{ p.base_url }}</span>
        </div>
        <div class="profile-actions">
          <button v-if="!p.is_active" class="act-btn" @click="activate(p.id)"><Check :size="12" /> 激活</button>
          <button class="act-btn" @click="test(p.id)" :disabled="testingId===p.id"><PlayCircle :size="12" /> {{ testingId===p.id?'测试中...':'测试' }}</button>
          <button class="act-btn" @click="startEdit(p)"><Pencil :size="12" /> 编辑</button>
          <button class="act-btn danger" @click="remove(p.id)" :disabled="p.is_active"><Trash2 :size="12" /> 删除</button>
        </div>
        <div v-if="testResult && testingId==='' && profiles.indexOf(p)===profiles.findIndex(x=>x.id===p.id)" class="test-result" :class="{ok:testResult.ok}">
          {{ testResult.ok ? '✅ 测试通过' : '❌ ' + testResult.msg }}
        </div>
      </div>
    </div>

    <!-- Form modal -->
    <div v-if="showForm" class="form-overlay" @click.self="showForm=false">
      <div class="form-box">
        <h3>{{ editing ? '编辑配置' : '新增配置' }}</h3>
        <div class="field"><label>名称</label><input v-model="form.name" class="input" placeholder="My GPT-4" /></div>
        <div class="field"><label>Provider</label>
          <select v-model="form.provider" class="input">
            <option value="openai">OpenAI</option><option value="azure">Azure</option>
            <option value="anthropic">Anthropic</option><option value="ollama">Ollama</option>
            <option value="deepseek">DeepSeek</option><option value="custom">Custom</option>
          </select>
        </div>
        <div class="field"><label>Model</label><input v-model="form.model" class="input" placeholder="gpt-4o" /></div>
        <div class="field"><label>API Key {{ editing ? '(留空不改)' : '' }}</label><input v-model="form.api_key" type="password" class="input" /></div>
        <div class="field"><label>Base URL (可选)</label><input v-model="form.base_url" class="input" placeholder="https://api.openai.com/v1" /></div>
        <div class="field-row">
          <div class="field"><label>Temperature</label><input v-model.number="form.temperature" type="number" step="0.1" min="0" max="2" class="input short" /></div>
          <div class="field"><label>Max Tokens</label><input v-model.number="form.max_tokens" type="number" class="input short" /></div>
        </div>
        <div class="form-actions">
          <button class="btn-save" @click="save">保存</button>
          <button class="btn-cancel" @click="showForm=false">取消</button>
        </div>
      </div>
    </div>
  </div>
</AdminAuthWrapper>
</template>

<style scoped>
.llm-panel { max-width: 640px; }
.header-row { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.title { font-size:20px; font-weight:700; margin:0; }
.btn-add { display:inline-flex; align-items:center; gap:4px; padding:6px 14px; font-size:13px; background:#3b82f6; color:#fff; border:none; border-radius:6px; cursor:pointer; }
.btn-add:hover { background:#2563eb; }
.loading { padding:40px; text-align:center; color:#9ca3af; }
.profile-list { display:flex; flex-direction:column; gap:10px; }
.profile-card { padding:14px; background:#f9fafb; border-radius:8px; border:1px solid #f3f4f6; }
.profile-card.active { border-color:#3b82f6; background:#eff6ff; }
.profile-header { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
.profile-name { font-weight:600; font-size:14px; }
.active-badge { display:inline-flex; align-items:center; gap:3px; font-size:11px; color:#2563eb; background:#dbeafe; padding:2px 6px; border-radius:4px; }
.profile-meta { font-size:12px; color:#6b7280; margin-bottom:8px; }
.profile-actions { display:flex; gap:6px; }
.act-btn { display:inline-flex; align-items:center; gap:3px; padding:4px 8px; font-size:12px; background:#fff; border:1px solid #e5e7eb; border-radius:4px; cursor:pointer; color:#374151; }
.act-btn:hover { background:#f3f4f6; }
.act-btn.danger { color:#dc2626; }
.act-btn.danger:hover { background:#fef2f2; }
.act-btn:disabled { opacity:0.4; cursor:not-allowed; }
.test-result { margin-top:8px; font-size:12px; padding:6px 10px; border-radius:4px; background:#f3f4f6; }
.test-result.ok { background:#f0fdf4; color:#16a34a; }
.form-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center; z-index:100; }
.form-box { background:#fff; padding:24px; border-radius:10px; width:400px; max-height:80vh; overflow-y:auto; }
.form-box h3 { margin:0 0 16px; font-size:16px; }
.field { display:flex; flex-direction:column; gap:4px; margin-bottom:10px; }
.field label { font-size:12px; font-weight:500; color:#6b7280; }
.input { padding:7px 10px; border:1px solid #e5e7eb; border-radius:6px; font-size:14px; }
.input:focus { outline:none; border-color:#3b82f6; }
.input.short { width:120px; }
.field-row { display:flex; gap:12px; }
.form-actions { display:flex; gap:8px; margin-top:14px; }
.btn-save { padding:7px 16px; font-size:13px; background:#3b82f6; color:#fff; border:none; border-radius:6px; cursor:pointer; }
.btn-cancel { padding:7px 16px; font-size:13px; background:#f3f4f6; color:#374151; border:none; border-radius:6px; cursor:pointer; }
</style>
