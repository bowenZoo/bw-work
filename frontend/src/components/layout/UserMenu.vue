<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import LetterAvatar from '@/components/common/LetterAvatar.vue'

const emit = defineEmits<{
  (e: 'open-panel', section: string): void
}>()

const userStore = useUserStore()
const router = useRouter()
const open = ref(false)
const showNotifications = ref(false)

// Notification state
const unreadCount = ref(0)
const notifications = ref<any[]>([])
const loadingNotifs = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const base = import.meta.env.VITE_API_BASE || ''

async function fetchUnreadCount() {
  try {
    const res = await fetch(`${base}/api/notifications/unread-count`, {
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    if (res.ok) {
      const data = await res.json()
      unreadCount.value = data.count || 0
    }
  } catch {}
}

async function fetchNotifications() {
  loadingNotifs.value = true
  try {
    const res = await fetch(`${base}/api/notifications`, {
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    if (res.ok) {
      notifications.value = await res.json()
      unreadCount.value = notifications.value.filter((n: any) => !n.read).length
    }
  } catch {} finally {
    loadingNotifs.value = false
  }
}

async function markRead(id: string) {
  try {
    await fetch(`${base}/api/notifications/${id}/read`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    const n = notifications.value.find((x: any) => x.id === id)
    if (n) n.read = true
    unreadCount.value = notifications.value.filter((x: any) => !x.read).length
  } catch {}
}

function toggleNotifications() {
  showNotifications.value = !showNotifications.value
  if (showNotifications.value) {
    open.value = false
    fetchNotifications()
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) showNotifications.value = false
}

function close() {
  open.value = false
  showNotifications.value = false
}

function openPanel(section: string) {
  emit('open-panel', section)
  close()
}

function onNotifClick(n: any) {
  if (!n.read) markRead(n.id)
  if (n.project_id) {
    router.push(`/project/${n.project_id}`)
    close()
  }
}

async function doLogout() {
  await userStore.logout()
  close()
  router.push('/')
}

function formatTime(dt: string) {
  if (!dt) return ''
  const d = new Date(dt)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

onMounted(() => {
  if (userStore.isAuthenticated) {
    fetchUnreadCount()
    pollTimer = setInterval(fetchUnreadCount, 30000)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="user-menu" v-if="userStore.isAuthenticated">
    <!-- Notification bell -->
    <button class="notif-bell" @click="toggleNotifications">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
      <span v-if="unreadCount > 0" class="notif-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
    </button>

    <button class="user-menu-trigger" @click="toggle">
      <LetterAvatar :name="userStore.user?.display_name || userStore.user?.username || ''" :size="24" />
      <span class="username">{{ userStore.user?.display_name || userStore.user?.username }}</span>
    </button>

    <Transition name="fade">
      <div v-if="open || showNotifications" class="menu-backdrop" @click="close"></div>
    </Transition>

    <!-- Notifications dropdown -->
    <Transition name="dropdown">
      <div v-if="showNotifications" class="notif-dropdown">
        <div class="notif-header">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
          通知
        </div>
        <div v-if="loadingNotifs" class="notif-empty">加载中...</div>
        <div v-else-if="notifications.length === 0" class="notif-empty">暂无通知</div>
        <div v-else class="notif-list">
          <div
            v-for="n in notifications"
            :key="n.id"
            class="notif-item"
            :class="{ 'notif-unread': !n.read }"
            @click="onNotifClick(n)"
          >
            <span class="notif-icon">
              <svg v-if="n.type === 'access_request'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            </span>
            <div class="notif-body">
              <div class="notif-msg">{{ n.message }}</div>
              <div class="notif-time">{{ formatTime(n.created_at) }}</div>
            </div>
            <span v-if="!n.read" class="notif-dot"></span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- User menu dropdown -->
    <Transition name="dropdown">
      <div v-if="open" class="menu-dropdown">
        <button class="menu-item" @click="openPanel('profile')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          个人资料
        </button>
        <button class="menu-item" @click="openPanel('my-discussions')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          我的讨论
        </button>
        <template v-if="userStore.isAdmin">
          <div class="menu-divider"></div>
          <button class="menu-item" @click="openPanel('system-settings')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
            系统设置
          </button>
          <button class="menu-item" @click="openPanel('llm-config')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/><path d="M7 8h.01M12 8h.01M17 8h.01M7 12h10"/></svg>
            LLM 配置
          </button>
          <button class="menu-item" @click="openPanel('langfuse-config')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            Langfuse
          </button>
          <button class="menu-item" @click="openPanel('image-config')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            图片模型
          </button>
          <button class="menu-item" @click="openPanel('audit-logs')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            审计日志
          </button>
          <button class="menu-item" @click="openPanel('user-manage')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            用户管理
          </button>
        </template>
        <div class="menu-divider"></div>
        <button class="menu-item logout" @click="doLogout">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          退出登录
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.user-menu {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}
.notif-bell {
  position: relative;
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 8px;
  border-radius: 8px;
  transition: background 0.15s;
  color: #6B7280;
  display: flex;
  align-items: center;
}
.notif-bell:hover { background: #f3f4f6; color: #374151; }
.notif-badge {
  position: absolute;
  top: -2px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  background: #ff4444;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  line-height: 1;
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
.user-menu-trigger:hover { background: #f3f4f6; }
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
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 14px;
  background: none;
  border: none;
  text-align: left;
  font-size: 13.5px;
  color: #374151;
  cursor: pointer;
  transition: background 0.1s;
}
.menu-item:hover { background: #f3f4f6; }
.menu-item.logout { color: #ef4444; }
.menu-item.logout:hover { background: #fef2f2; }
.menu-divider { height: 1px; background: #e5e7eb; margin: 4px 0; }

/* Notification dropdown */
.notif-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 340px;
  max-height: 400px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  z-index: 100;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.notif-header {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid #f0f0f0;
  color: #111827;
  display: flex;
  align-items: center;
  gap: 7px;
}
.notif-empty {
  padding: 24px 16px;
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
}
.notif-list {
  overflow-y: auto;
  flex: 1;
}
.notif-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.1s;
  border-bottom: 1px solid #f8f8f8;
}
.notif-item:hover { background: #f9fafb; }
.notif-unread { background: #eff6ff; }
.notif-unread:hover { background: #dbeafe; }
.notif-icon { flex-shrink: 0; margin-top: 2px; color: #6b7280; display: flex; align-items: center; }
.notif-body { flex: 1; min-width: 0; }
.notif-msg { font-size: 13px; color: #374151; line-height: 1.4; }
.notif-time { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.notif-dot {
  width: 8px;
  height: 8px;
  background: #3b82f6;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.dropdown-enter-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-leave-active { transition: opacity 0.1s, transform 0.1s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 768px) {
  .username { display: none; }
  .user-menu-trigger { padding: 4px 6px; }
  .notif-dropdown { width: calc(100vw - 24px); right: -40px; }
  .menu-dropdown { right: 0; left: auto; max-width: calc(100vw - 24px); min-width: 180px; }
}
</style>
