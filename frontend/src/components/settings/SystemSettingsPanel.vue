<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAdminApi } from './useAdminApi';

import { Settings, Save, Check, AlertCircle, Zap, Eye, BarChart3 } from 'lucide-vue-next';

const { adminRequest } = useAdminApi();
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref('');

// Status overview
const status = ref<any>({});

// Discussion settings
const discussion = ref({ default_rounds: 10, pause_interval: 5, max_agents: 6 });

async function load() {
  loading.value = true;
  try {
    status.value = await apiRequest<any>('/config/status');
    try {
      const disc = await apiRequest<any>('/config/discussion');
      if (disc) Object.assign(discussion.value, disc);
    } catch {}
  } catch {}
  loading.value = false;
}

async function saveDiscussion() {
  saving.value = true; error.value = ''; saved.value = false;
  try {
    await adminRequest('/config/discussion', { method:'PUT', body:JSON.stringify(discussion.value) });
    saved.value = true; setTimeout(() => saved.value = false, 2000);
  } catch (e:any) { error.value = e.message || '保存失败'; }
  finally { saving.value = false; }
}

onMounted(load);
</script>

<template>
  <div class="sys-panel">
    <h2 class="title"><Settings :size="20" /> 系统设置</h2>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <!-- Status cards -->
      <div class="status-grid">
        <div class="stat-card">
          <Zap :size="16" class="stat-icon blue" />
          <div><div class="stat-label">LLM</div><div class="stat-val"><span :class="status.llm_configured ? 'ok-dot' : 'err-dot'">{{ status.llm_configured ? '已配置' : '未配置' }}</span></div></div>
        </div>
        <div class="stat-card">
          <Eye :size="16" class="stat-icon purple" />
          <div><div class="stat-label">Langfuse</div><div class="stat-val"><span :class="status.langfuse_enabled ? 'ok-dot' : status.langfuse_configured ? 'warn-dot' : 'err-dot'">{{ status.langfuse_enabled ? '已启用' : status.langfuse_configured ? '已禁用' : '未配置' }}</span></div></div>
        </div>
        <div class="stat-card">
          <BarChart3 :size="16" class="stat-icon green" />
          <div><div class="stat-label">图片模型</div><div class="stat-val"><span :class="status.image_configured ? 'ok-dot' : 'err-dot'">{{ status.image_configured ? '已配置' : '未配置' }}</span></div><div class="stat-sub">{{ status.default_image_provider || '-' }}</div></div>
        </div>
      </div>

      <!-- Discussion settings -->
      <div class="card">
        <h3 class="card-title">讨论设置</h3>
        <div class="form-grid">
          <div class="field">
            <label>默认轮次</label>
            <input v-model.number="discussion.default_rounds" type="number" min="1" max="100" class="input short" />
          </div>
          <div class="field">
            <label>暂停间隔</label>
            <div class="input-row"><input v-model.number="discussion.pause_interval" type="number" min="0" max="50" class="input short" /><span class="hint">{{ discussion.pause_interval > 0 ? `每${discussion.pause_interval}轮暂停` : '不暂停' }}</span></div>
          </div>
          <div class="field">
            <label>最大 Agent 数</label>
            <input v-model.number="discussion.max_agents" type="number" min="1" max="20" class="input short" />
          </div>
        </div>
        <div class="actions">
          <button class="btn-save" :disabled="saving" @click="saveDiscussion"><Save :size="14" /> {{ saving?'保存中...':'保存' }}</button>
          <span v-if="saved" class="msg-ok"><Check :size="14" /> 已保存</span>
          <span v-if="error" class="msg-err"><AlertCircle :size="14" /> {{ error }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.sys-panel { max-width:640px; }
.title { display:flex; align-items:center; gap:8px; font-size:20px; font-weight:700; margin:0 0 20px; }
.loading { padding:40px; text-align:center; color:#9ca3af; }
.status-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:20px; }
.stat-card { display:flex; gap:10px; align-items:flex-start; padding:14px; background:#f9fafb; border-radius:8px; }
.stat-icon { flex-shrink:0; margin-top:2px; }
.stat-icon.blue { color:#3b82f6; }
.stat-icon.purple { color:#7c3aed; }
.stat-icon.green { color:#16a34a; }
.stat-label { font-size:11px; color:#6b7280; font-weight:500; }
.stat-val { font-size:13px; font-weight:600; }
.stat-sub { font-size:11px; color:#9ca3af; }
.ok-dot { color:#16a34a; font-weight:600; }
.err-dot { color:#dc2626; font-weight:600; }
.warn-dot { color:#d97706; font-weight:600; }
.card { padding:18px; background:#f9fafb; border-radius:10px; margin-bottom:16px; }
.card-title { font-size:14px; font-weight:600; margin:0 0 12px; }
.form-grid { display:flex; flex-direction:column; gap:12px; }
.field { display:flex; flex-direction:column; gap:4px; }
.field label { font-size:12px; font-weight:500; color:#6b7280; }
.input { padding:7px 10px; border:1px solid #e5e7eb; border-radius:6px; font-size:14px; }
.input:focus { outline:none; border-color:#3b82f6; }
.input.short { width:100px; }
.input-row { display:flex; align-items:center; gap:8px; }
.hint { font-size:11px; color:#9ca3af; }
.actions { display:flex; align-items:center; gap:8px; margin-top:14px; }
.btn-save { display:inline-flex; align-items:center; gap:4px; padding:7px 14px; font-size:13px; font-weight:500; background:#3b82f6; color:#fff; border:none; border-radius:6px; cursor:pointer; }
.btn-save:hover { background:#2563eb; }
.btn-save:disabled { opacity:0.5; }
.msg-ok { font-size:12px; color:#16a34a; display:flex; align-items:center; gap:3px; }
.msg-err { font-size:12px; color:#dc2626; display:flex; align-items:center; gap:3px; }
</style>
