<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useUserStore } from '@/stores/user'
import UserManagePanel from '@/components/admin/UserManagePanel.vue'
import ProfilePanel from '@/components/settings/ProfilePanel.vue'
import SystemSettingsPanel from '@/components/settings/SystemSettingsPanel.vue'
import AuditLogPanel from '@/components/settings/AuditLogPanel.vue'
import LlmConfigPanel from '@/components/settings/LlmConfigPanel.vue'
import LangfuseConfigPanel from '@/components/settings/LangfuseConfigPanel.vue'
import ImageConfigPanel from '@/components/settings/ImageConfigPanel.vue'

const userStore = useUserStore()
const activeSection = ref('')

const settingSections = ['profile', 'my-discussions', 'system-settings', 'llm-config', 'langfuse-config', 'image-config', 'audit-logs', 'user-manage']
const drawerOpen = computed(() => settingSections.includes(activeSection.value))

const drawerTitle = computed(() => {
  const map: Record<string, string> = {
    'profile': '个人资料',
    'my-discussions': '我的讨论',
    'system-settings': '系统设置',
    'llm-config': 'LLM 配置',
    'langfuse-config': 'Langfuse',
    'image-config': '图片模型',
    'audit-logs': '审计日志',
    'user-manage': '用户管理',
  }
  return map[activeSection.value] || ''
})

function onOpenPanel(section: string) {
  activeSection.value = activeSection.value === section ? '' : section
}

function closeDrawer() {
  activeSection.value = ''
}

onMounted(() => {
  userStore.init()
})
</script>

<template>
  <div class="app-root">
    <router-view @open-panel="onOpenPanel" />
    <!-- Settings Drawer Overlay -->
    <Transition name="drawer">
      <div v-if="drawerOpen" class="drawer-overlay" @click.self="closeDrawer">
        <div class="drawer-panel">
          <div class="drawer-header">
            <h2>{{ drawerTitle }}</h2>
            <button class="drawer-close" @click="closeDrawer">&times;</button>
          </div>
          <div class="drawer-body">
            <UserManagePanel v-if="activeSection === 'user-manage'" />
            <ProfilePanel v-else-if="activeSection === 'profile'" />
            <SystemSettingsPanel v-else-if="activeSection === 'system-settings'" />
            <LlmConfigPanel v-else-if="activeSection === 'llm-config'" />
            <LangfuseConfigPanel v-else-if="activeSection === 'langfuse-config'" />
            <ImageConfigPanel v-else-if="activeSection === 'image-config'" />
            <AuditLogPanel v-else-if="activeSection === 'audit-logs'" />
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.app-root {
  min-height: 100vh;
}

/* Drawer overlay */
.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0,0,0,0.3);
  display: flex;
  justify-content: flex-end;
}
.drawer-panel {
  width: min(520px, 90vw);
  height: 100vh;
  background: #fff;
  box-shadow: -4px 0 24px rgba(0,0,0,0.12);
  display: flex;
  flex-direction: column;
}
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}
.drawer-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}
.drawer-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #6b7280;
  background: none;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.drawer-close:hover { background: #f3f4f6; color: #111; }
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* Transition */
.drawer-enter-active, .drawer-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-enter-active .drawer-panel, .drawer-leave-active .drawer-panel {
  transition: transform 0.25s ease;
}
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer-panel, .drawer-leave-to .drawer-panel {
  transform: translateX(100%);
}
</style>
