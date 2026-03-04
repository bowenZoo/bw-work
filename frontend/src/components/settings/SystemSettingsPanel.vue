<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useUserStore } from '@/stores/user';
import { Settings, Save, Check, AlertCircle } from 'lucide-vue-next';

const userStore = useUserStore();
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref('');

// Settings data
const llmConfig = ref({ provider: '', model: '', api_key_masked: '' });
const discussionConfig = ref({ default_rounds: 10, auto_pause: 5, max_agents: 6 });

onMounted(async () => {
  try {
    const resp = await fetch('/admin/api/config', {
      headers: { 'Authorization': `Bearer ${userStore.accessToken}` }
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.llm) llmConfig.value = { provider: data.llm.provider || '', model: data.llm.model || '', api_key_masked: '••••••' };
      if (data.discussion) Object.assign(discussionConfig.value, data.discussion);
    }
  } catch {}
  loading.value = false;
});

async function saveSettings() {
  saving.value = true; error.value = ''; saved.value = false;
  try {
    const resp = await fetch('/admin/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${userStore.accessToken}` },
      body: JSON.stringify({ discussion: discussionConfig.value }),
    });
    if (!resp.ok) throw new Error('保存失败');
    saved.value = true;
    setTimeout(() => saved.value = false, 2000);
  } catch (e: any) { error.value = e.message; }
  finally { saving.value = false; }
}
</script>

<template>
  <div class="settings-panel">
    <h2 class="section-title"><Settings :size="20" /> 系统设置</h2>

    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <!-- LLM Config (read-only display) -->
      <div class="card">
        <h3 class="card-title">LLM 配置</h3>
        <div class="config-grid">
          <div class="config-item"><span class="config-label">Provider</span><span class="config-value">{{ llmConfig.provider || '未配置' }}</span></div>
          <div class="config-item"><span class="config-label">Model</span><span class="config-value">{{ llmConfig.model || '未配置' }}</span></div>
          <div class="config-item"><span class="config-label">API Key</span><span class="config-value">{{ llmConfig.api_key_masked }}</span></div>
        </div>
        <p class="config-hint">LLM 配置请通过管理后台 /admin 修改</p>
      </div>

      <!-- Discussion Config -->
      <div class="card">
        <h3 class="card-title">讨论设置</h3>
        <div class="form-grid">
          <div class="field">
            <label>默认轮次</label>
            <input v-model.number="discussionConfig.default_rounds" type="number" min="1" max="100" class="input short" />
          </div>
          <div class="field">
            <label>自动暂停间隔</label>
            <div class="input-hint-row">
              <input v-model.number="discussionConfig.auto_pause" type="number" min="0" max="50" class="input short" />
              <span class="hint">{{ discussionConfig.auto_pause > 0 ? `每${discussionConfig.auto_pause}轮暂停` : '不自动暂停' }}</span>
            </div>
          </div>
          <div class="field">
            <label>最大 Agent 数</label>
            <input v-model.number="discussionConfig.max_agents" type="number" min="1" max="20" class="input short" />
          </div>
        </div>
        <div class="actions">
          <button class="btn-save" :disabled="saving" @click="saveSettings"><Save :size="14" /> {{ saving ? '保存中...' : '保存设置' }}</button>
          <span v-if="saved" class="msg-ok"><Check :size="14" /> 已保存</span>
          <span v-if="error" class="msg-err"><AlertCircle :size="14" /> {{ error }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.settings-panel { max-width: 640px; }
.section-title { display: flex; align-items: center; gap: 8px; font-size: 20px; font-weight: 700; margin: 0 0 20px; }
.loading { padding: 40px; text-align: center; color: #9ca3af; }
.card { padding: 18px; background: #f9fafb; border-radius: 10px; margin-bottom: 16px; }
.card-title { font-size: 14px; font-weight: 600; margin: 0 0 12px; }
.config-grid { display: flex; flex-direction: column; gap: 8px; }
.config-item { display: flex; align-items: center; gap: 8px; }
.config-label { font-size: 12px; font-weight: 500; color: #6b7280; min-width: 80px; }
.config-value { font-size: 13px; color: #374151; font-family: monospace; }
.config-hint { font-size: 11px; color: #9ca3af; margin: 10px 0 0; }
.form-grid { display: flex; flex-direction: column; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; font-weight: 500; color: #6b7280; }
.input { padding: 7px 10px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 14px; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
.input.short { width: 100px; }
.input-hint-row { display: flex; align-items: center; gap: 8px; }
.hint { font-size: 11px; color: #9ca3af; }
.actions { display: flex; align-items: center; gap: 10px; margin-top: 14px; }
.btn-save { display: inline-flex; align-items: center; gap: 5px; padding: 7px 16px; font-size: 13px; font-weight: 500; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-save:hover:not(:disabled) { background: #2563eb; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.msg-ok { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #16a34a; }
.msg-err { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #dc2626; }
</style>
