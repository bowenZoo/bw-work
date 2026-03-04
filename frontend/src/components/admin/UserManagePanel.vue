<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Search, Shield, ShieldOff, KeyRound, Trash2 } from 'lucide-vue-next';
import { useUserStore } from '@/stores/user';
import { usersApi, type UserInfo } from '@/api/auth';

const userStore = useUserStore();
const users = ref<UserInfo[]>([]);
const total = ref(0);
const page = ref(1);
const search = ref('');
const loading = ref(false);

async function loadUsers() {
  if (!userStore.accessToken) return;
  loading.value = true;
  try {
    const res = await usersApi.list(userStore.accessToken, page.value, 20, search.value || undefined);
    users.value = res.items;
    total.value = res.total;
  } catch { /* ignore */ }
  loading.value = false;
}

async function toggleRole(u: UserInfo) {
  if (!userStore.accessToken) return;
  const newRole = u.role === 'superadmin' ? 'user' : 'superadmin';
  await usersApi.update(userStore.accessToken, u.id, { role: newRole });
  await loadUsers();
}

async function toggleActive(u: UserInfo) {
  if (!userStore.accessToken) return;
  await usersApi.update(userStore.accessToken, u.id, { is_active: !u.is_active });
  await loadUsers();
}

async function resetPw(u: UserInfo) {
  if (!userStore.accessToken) return;
  const res = await usersApi.resetPassword(userStore.accessToken, u.id);
  alert(`新密码: ${res.new_password}`);
}

async function deleteUser(u: UserInfo) {
  if (!userStore.accessToken) return;
  if (!confirm(`确定要删除用户 ${u.username}？`)) return;
  await usersApi.delete(userStore.accessToken, u.id);
  await loadUsers();
}

function handleSearch() {
  page.value = 1;
  loadUsers();
}

onMounted(loadUsers);
</script>

<template>
  <div class="user-panel">
    <div class="panel-top">
      <h3>用户管理</h3>
      <div class="search-box">
        <Search :size="14" />
        <input v-model="search" placeholder="搜索用户..." @keydown.enter="handleSearch" />
      </div>
    </div>

    <div class="user-table-wrap">
      <table class="user-table">
        <thead>
          <tr>
            <th>用户名</th>
            <th>显示名</th>
            <th>角色</th>
            <th>状态</th>
            <th>注册时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td>{{ u.display_name || '-' }}</td>
            <td>
              <span :class="['role-badge', u.role]">{{ u.role === 'superadmin' ? '管理员' : '用户' }}</span>
            </td>
            <td>
              <span :class="['status-dot', u.is_active ? 'active' : 'disabled']" />
              {{ u.is_active ? '正常' : '已禁用' }}
            </td>
            <td>{{ new Date(u.created_at).toLocaleDateString('zh-CN') }}</td>
            <td class="actions">
              <button title="切换角色" @click="toggleRole(u)">
                <Shield v-if="u.role !== 'superadmin'" :size="14" />
                <ShieldOff v-else :size="14" />
              </button>
              <button title="切换状态" @click="toggleActive(u)">
                {{ u.is_active ? '禁用' : '启用' }}
              </button>
              <button title="重置密码" @click="resetPw(u)"><KeyRound :size="14" /></button>
              <button title="删除" class="danger" @click="deleteUser(u)"><Trash2 :size="14" /></button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-if="!loading && users.length === 0" class="empty">暂无用户</div>

    <div v-if="total > 20" class="pagination">
      <button :disabled="page <= 1" @click="page--; loadUsers()">上一页</button>
      <span>第 {{ page }} 页 / 共 {{ Math.ceil(total / 20) }} 页</span>
      <button :disabled="page * 20 >= total" @click="page++; loadUsers()">下一页</button>
    </div>
  </div>
</template>

<style scoped>
.user-panel { padding: 0; }
.panel-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.panel-top h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}
.search-box {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  font-size: 13px;
}
.search-box input {
  border: none;
  outline: none;
  font-size: 13px;
  width: 160px;
  background: transparent;
}
.user-table-wrap { overflow-x: auto; }
.user-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.user-table th {
  text-align: left;
  padding: 8px 12px;
  font-weight: 500;
  color: var(--text-secondary, #6b7280);
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}
.user-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color, #f3f4f6);
  color: var(--text-primary, #374151);
}
.role-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}
.role-badge.superadmin { background: #fef3c7; color: #d97706; }
.role-badge.user { background: #f0fdf4; color: #16a34a; }
.status-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  margin-right: 4px;
}
.status-dot.active { background: #10b981; }
.status-dot.disabled { background: #ef4444; }
.actions {
  display: flex;
  gap: 6px;
}
.actions button {
  padding: 4px 8px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  display: inline-flex;
  align-items: center;
  gap: 3px;
  transition: all 0.15s;
}
.actions button:hover { border-color: var(--primary-color, #3b82f6); color: var(--primary-color, #3b82f6); }
.actions button.danger:hover { border-color: #ef4444; color: #ef4444; }
.loading, .empty {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary, #9ca3af);
  font-size: 14px;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
  font-size: 13px;
}
.pagination button {
  padding: 4px 12px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  font-size: 13px;
}
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
