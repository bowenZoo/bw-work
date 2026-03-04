<script setup lang="ts">
import { ref, computed } from 'vue';
import { MessageSquare, Users, Settings, BarChart3, FileText, User, ChevronLeft, ChevronRight, List } from 'lucide-vue-next';
import { useUserStore } from '@/stores/user';

const props = defineProps<{
  activeSection: string;
}>();

const emit = defineEmits<{
  select: [section: string];
}>();

const userStore = useUserStore();
const expanded = ref(false);

interface MenuItem {
  id: string;
  label: string;
  icon: any;
  adminOnly?: boolean;
  requireAuth?: boolean;
}

const menuItems = computed<MenuItem[]>(() => {
  const items: MenuItem[] = [
    { id: 'my-discussions', label: '我的讨论', icon: MessageSquare },
  ];
  if (userStore.isAuthenticated) {
    items.push({ id: 'profile', label: '个人中心', icon: User, requireAuth: true });
  }
  if (userStore.isAdmin) {
    items.push(
      { id: 'all-discussions', label: '全部讨论', icon: List, adminOnly: true },
      { id: 'user-manage', label: '用户管理', icon: Users, adminOnly: true },
      { id: 'system-settings', label: '系统设置', icon: Settings, adminOnly: true },
      { id: 'audit-logs', label: '审计日志', icon: FileText, adminOnly: true },
    );
  }
  return items;
});

function toggle() {
  expanded.value = !expanded.value;
}
</script>

<template>
  <aside :class="['side-panel', { expanded }]">
    <button class="toggle-btn" @click="toggle">
      <ChevronRight v-if="!expanded" :size="16" />
      <ChevronLeft v-else :size="16" />
    </button>

    <nav class="menu">
      <button
        v-for="item in menuItems"
        :key="item.id"
        :class="['menu-item', { active: activeSection === item.id }]"
        :title="item.label"
        @click="emit('select', item.id)"
      >
        <component :is="item.icon" :size="18" class="menu-icon" />
        <span v-if="expanded" class="menu-label">{{ item.label }}</span>
      </button>
    </nav>
  </aside>
</template>

<style scoped>
.side-panel {
  width: 48px;
  background: var(--bg-primary, #fff);
  border-right: 1px solid var(--border-color, #e5e7eb);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  flex-shrink: 0;
  overflow: hidden;
}
.side-panel.expanded {
  width: 200px;
}
.toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  color: var(--text-secondary, #9ca3af);
  transition: color 0.15s;
  flex-shrink: 0;
}
.toggle-btn:hover { color: var(--text-primary, #374151); }
.menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 6px;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 8px;
  border-radius: 8px;
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s;
  white-space: nowrap;
  overflow: hidden;
}
.menu-item:hover {
  background: #f3f4f6;
  color: var(--text-primary, #374151);
}
.menu-item.active {
  background: #eff6ff;
  color: var(--primary-color, #3b82f6);
}
.menu-icon { flex-shrink: 0; }
.menu-label { overflow: hidden; text-overflow: ellipsis; }
</style>
