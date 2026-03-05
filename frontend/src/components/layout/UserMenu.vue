<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import LetterAvatar from '@/components/common/LetterAvatar.vue'

const emit = defineEmits<{
  (e: 'open-panel', section: string): void
}>()

const userStore = useUserStore()
const router = useRouter()
const open = ref(false)

function toggle() {
  open.value = !open.value
}

function close() {
  open.value = false
}

function openPanel(section: string) {
  emit('open-panel', section)
  close()
}

async function doLogout() {
  await userStore.logout()
  close()
  router.push('/')
  // HallView will detect !isAuthenticated and show login
}
</script>

<template>
  <div class="user-menu" v-if="userStore.isAuthenticated">
    <button class="user-menu-trigger" @click="toggle">
      <LetterAvatar :name="userStore.user?.display_name || userStore.user?.username || ''" :size="24" />
      <span class="username">{{ userStore.user?.display_name || userStore.user?.username }}</span>
    </button>
    <Transition name="fade">
      <div v-if="open" class="menu-backdrop" @click="close"></div>
    </Transition>
    <Transition name="dropdown">
      <div v-if="open" class="menu-dropdown">
        <button class="menu-item" @click="openPanel('profile')">📝 个人资料</button>
        <button class="menu-item" @click="openPanel('my-discussions')">📊 我的讨论</button>
        <template v-if="userStore.isAdmin">
          <div class="menu-divider"></div>
          <button class="menu-item" @click="openPanel('system-settings')">⚙️ 系统设置</button>
          <button class="menu-item" @click="openPanel('llm-config')">🤖 LLM 配置</button>
          <button class="menu-item" @click="openPanel('langfuse-config')">📊 Langfuse</button>
          <button class="menu-item" @click="openPanel('image-config')">🖼️ 图片模型</button>
          <button class="menu-item" @click="openPanel('audit-logs')">📋 审计日志</button>
          <button class="menu-item" @click="openPanel('user-manage')">👥 用户管理</button>
        </template>
        <div class="menu-divider"></div>
        <button class="menu-item logout" @click="doLogout">🚪 退出登录</button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.user-menu {
  position: relative;
}
.user-menu-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #374151;
  transition: background 0.15s;
}
.user-menu-trigger:hover {
  background: #f3f4f6;
}
.username {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 99;
}
.menu-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 200px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  padding: 6px 0;
  z-index: 100;
}
.menu-item {
  display: block;
  width: 100%;
  padding: 8px 16px;
  background: none;
  border: none;
  text-align: left;
  font-size: 14px;
  color: #374151;
  cursor: pointer;
  transition: background 0.1s;
}
.menu-item:hover {
  background: #f3f4f6;
}
.menu-item.logout {
  color: #ef4444;
}
.menu-divider {
  height: 1px;
  background: #e5e7eb;
  margin: 4px 0;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.dropdown-enter-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-leave-active { transition: opacity 0.1s, transform 0.1s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 768px) {
  .username {
    display: none;
  }
  .user-menu-trigger {
    padding: 4px 6px;
  }
  .menu-dropdown {
    right: 0;
    left: auto;
    max-width: calc(100vw - 24px);
    min-width: 180px;
  }
}
</style>
