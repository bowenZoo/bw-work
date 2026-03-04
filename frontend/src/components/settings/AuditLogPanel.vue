<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useUserStore } from '@/stores/user';
import { FileText, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-vue-next';

const userStore = useUserStore();

interface LogEntry {
  id: number;
  action: string;
  username: string;
  ip_address: string;
  details: string;
  created_at: string;
}

const logs = ref<LogEntry[]>([]);
const loading = ref(true);
const error = ref('');
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const filterAction = ref('');

const actionLabels: Record<string, string> = {
  login: '登录',
  login_failed: '登录失败',
  logout: '退出',
  config_update: '配置更新',
  config_delete: '配置删除',
  bootstrap_setup: '初始化',
};

const actionColors: Record<string, string> = {
  login: '#16a34a',
  login_failed: '#dc2626',
  logout: '#6b7280',
  config_update: '#2563eb',
  config_delete: '#ea580c',
  bootstrap_setup: '#7c3aed',
};

async function loadLogs() {
  loading.value = true; error.value = '';
  try {
    const params = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) });
    if (filterAction.value) params.set('action', filterAction.value);
    const resp = await fetch(`/admin/api/logs?${params}`, {
      headers: { 'Authorization': `Bearer ${userStore.accessToken}` }
    });
    if (!resp.ok) throw new Error('加载失败');
    const data = await resp.json();
    logs.value = data.items || data.logs || [];
    total.value = data.total || logs.value.length;
  } catch (e: any) { error.value = e.message; }
  finally { loading.value = false; }
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

const totalPages = ref(1);

onMounted(loadLogs);
</script>

<template>
  <div class="audit-panel">
    <div class="header-row">
      <h2 class="section-title"><FileText :size="20" /> 审计日志</h2>
      <div class="header-actions">
        <select v-model="filterAction" class="filter-select" @change="page=1; loadLogs()">
          <option value="">全部操作</option>
          <option v-for="(label, key) in actionLabels" :key="key" :value="key">{{ label }}</option>
        </select>
        <button class="btn-refresh" @click="loadLogs" :disabled="loading"><RefreshCw :size="14" :class="{spin:loading}" /> 刷新</button>
      </div>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div v-if="loading && logs.length === 0" class="loading">加载中...</div>

    <table v-else-if="logs.length > 0" class="log-table">
      <thead>
        <tr><th>时间</th><th>操作</th><th>用户</th><th>IP</th><th>详情</th></tr>
      </thead>
      <tbody>
        <tr v-for="log in logs" :key="log.id">
          <td class="col-time">{{ formatTime(log.created_at) }}</td>
          <td>
            <span class="action-tag" :style="{color: actionColors[log.action] || '#6b7280', background: (actionColors[log.action]||'#6b7280')+'18'}">
              {{ actionLabels[log.action] || log.action }}
            </span>
          </td>
          <td>{{ log.username || '-' }}</td>
          <td class="col-ip">{{ log.ip_address || '-' }}</td>
          <td class="col-detail">{{ log.details || '-' }}</td>
        </tr>
      </tbody>
    </table>

    <div v-else class="empty">暂无日志</div>

    <div v-if="total > pageSize" class="pagination">
      <button :disabled="page <= 1" @click="page--; loadLogs()"><ChevronLeft :size="14" /></button>
      <span class="page-info">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button :disabled="page * pageSize >= total" @click="page++; loadLogs()"><ChevronRight :size="14" /></button>
    </div>
  </div>
</template>

<style scoped>
.audit-panel { max-width: 800px; }
.header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.section-title { display: flex; align-items: center; gap: 8px; font-size: 20px; font-weight: 700; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.filter-select { padding: 6px 10px; border: 1px solid #e5e7eb; border-radius: 6px; font-size: 13px; background: #fff; }
.btn-refresh { display: inline-flex; align-items: center; gap: 4px; padding: 6px 12px; font-size: 13px; border: 1px solid #e5e7eb; border-radius: 6px; background: #fff; cursor: pointer; }
.btn-refresh:hover { background: #f3f4f6; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.loading, .empty { padding: 40px; text-align: center; color: #9ca3af; font-size: 14px; }
.error-msg { padding: 10px; background: #fef2f2; color: #dc2626; border-radius: 6px; font-size: 13px; margin-bottom: 12px; }

.log-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.log-table th { text-align: left; padding: 8px 10px; font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; border-bottom: 2px solid #f3f4f6; }
.log-table td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; color: #374151; }
.log-table tr:hover td { background: #f9fafb; }
.col-time { font-size: 12px; color: #6b7280; white-space: nowrap; }
.col-ip { font-family: monospace; font-size: 12px; color: #9ca3af; }
.col-detail { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: #6b7280; }
.action-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }

.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 16px; }
.pagination button { padding: 4px 8px; border: 1px solid #e5e7eb; border-radius: 4px; background: #fff; cursor: pointer; }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 13px; color: #6b7280; }
</style>
