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
  router.push('/login')
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
              <svg v-if="n.type === 'access_request'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 17H2a3 3 0 0 0 3-3V9a7 7 0 0 1 14 0v5a3 3 0 0 0 3 3zm-8.27 4a2 2 0 0 1-3.46 0"/></svg>
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
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          个人资料
        </button>
        <button class="menu-item" @click="openPanel('my-discussions')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
          我的讨论
        </button>
        <template v-if="userStore.isAdmin">
          <div class="menu-divider"></div>
          <button class="menu-item" @click="openPanel('system-settings')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            系统设置
          </button>
          <button class="menu-item" @click="openPanel('llm-config')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
            LLM 配置
          </button>
          <button class="menu-item" @click="openPanel('langfuse-config')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
            Langfuse
          </button>
          <button class="menu-item" @click="openPanel('image-config')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            图片模型
          </button>
          <button class="menu-item" @click="openPanel('audit-logs')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="13" y2="16"/></svg>
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
/* ===== Style C — Design Token Aligned (ytzkC) ===== */

.user-menu {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}

.notif-bell {
  position: relative;
  display: inline-flex;
  align-items: center;
  background: none;
  border: none;
  color: #374151;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 8px;
  transition: background 0.15s;
}

.notif-bell:hover { background: #F0EDE8; }

/* Notification badge — token: #EF4444, 20×20, radius 10px */
.notif-badge {
  position: absolute;
  top: -2px;
  right: -4px;
  min-width: 20px;
  height: 20px;
  background: #EF4444;
  color: #FFFFFF;
  font-size: 12px;
  font-weight: 600;
  border-radius: 10px;
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
  border: 1px solid #F0EBE4;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #374151;
  transition: background 0.15s;
}

.user-menu-trigger:hover { background: #F0EDE8; }

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

/* User dropdown — token: 280px, radius 16px, shadow 0 8px 24px #00000018, border #F0EDE8 */
.menu-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 280px;
  background: #FFFFFF;
  border: 1px solid #F0EDE8;
  border-radius: 16px;
  box-shadow: 0 8px 24px #00000018;
  padding: 6px 0;
  z-index: 100;
}

/* Menu items — token: padding 10px 16px, color #2D2D2D */
.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 16px;
  background: none;
  border: none;
  text-align: left;
  font-size: 14px;
  color: #2D2D2D;
  cursor: pointer;
  transition: background 0.1s;
  font-family: Inter, sans-serif;
}

.menu-item:hover { background: #F0EDE8; }
.menu-item.logout { color: #EF4444; }

/* Dividers — token: #F0EDE8 */
.menu-divider { height: 1px; background: #F0EDE8; margin: 4px 0; }

/* Notification panel — token: 300px, radius 12px, shadow 0 8px 24px #00000012, border #F0EDE8 */
.notif-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 300px;
  max-height: 400px;
  background: #FFFFFF;
  border: 1px solid #F0EDE8;
  border-radius: 12px;
  box-shadow: 0 8px 24px #00000012;
  z-index: 100;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.notif-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 14px 16px;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid #F0EDE8;
  color: #18181B;
  font-family: Inter, sans-serif;
}

.notif-empty {
  padding: 24px 16px;
  text-align: center;
  color: #9CA3AF;
  font-size: 13px;
}

.notif-list {
  overflow-y: auto;
  flex: 1;
}

/* Notification items — token: padding 12px 16px, gap 10px */
.notif-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.1s;
  border-bottom: 1px solid #F0EDE8;
}

.notif-item:hover { background: #FAFAFA; }
/* Unread tint — soft brand overlay */
.notif-unread { background: #EDE9FE; }
.notif-unread:hover { background: #DDD6FE; }
.notif-icon { font-size: 16px; flex-shrink: 0; margin-top: 2px; }
.notif-body { flex: 1; min-width: 0; }
.notif-msg { font-size: 13px; color: #374151; line-height: 1.4; }
.notif-time { font-size: 11px; color: #9CA3AF; margin-top: 2px; }

/* Notification dot — token: #3B82F6, 8×8, radius 4px */
.notif-dot {
  width: 8px;
  height: 8px;
  background: #3B82F6;
  border-radius: 4px;
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
