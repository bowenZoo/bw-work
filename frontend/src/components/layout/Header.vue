<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { Wifi, WifiOff, LogOut, User, ChevronDown } from 'lucide-vue-next';
import { useUserStore } from '@/stores/user';
import LoginModal from '@/components/auth/LoginModal.vue';
import type { ConnectionStatus } from '@/types';

const props = defineProps<{
  connectionStatus?: ConnectionStatus;
}>();

const userStore = useUserStore();
const showLoginModal = ref(false);
const showUserMenu = ref(false);

const connectionStatusText = computed(() => {
  switch (props.connectionStatus) {
    case 'connected': return '已连接';
    case 'connecting': return '连接中...';
    case 'disconnected': return '已断开';
    case 'error': return '连接错误';
    default: return '离线';
  }
});

const connectionStatusClass = computed(() => {
  switch (props.connectionStatus) {
    case 'connected': return 'conn-ok';
    case 'connecting': return 'conn-ing';
    case 'error': return 'conn-err';
    default: return 'conn-off';
  }
});

const isConnected = computed(() => props.connectionStatus === 'connected');

function closeMenu(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest('.user-area')) {
    showUserMenu.value = false;
  }
}
onMounted(() => document.addEventListener('click', closeMenu));
onUnmounted(() => document.removeEventListener('click', closeMenu));

function handleLogout() {
  showUserMenu.value = false;
  userStore.logout();
}
</script>

<template>
  <header class="header-bar">
    <div class="header-inner">
      <!-- Logo -->
      <div class="header-logo">
        <div class="logo-icon">
          <span class="logo-text">BW</span>
        </div>
      </div>

      <!-- Center: topic slot -->
      <div class="header-center">
        <slot name="topic" />
      </div>

      <!-- Right: user area + connection status -->
      <div class="header-right">
        <slot name="extra" />

        <!-- User area -->
        <template v-if="userStore.isAuthenticated">
          <div class="user-area" @click="showUserMenu = !showUserMenu">
            <span class="user-name">{{ userStore.user?.display_name || userStore.user?.username }}</span>
            <span v-if="userStore.isAdmin" class="role-tag">管理员</span>
            <ChevronDown :size="14" />

            <Transition name="dropdown">
              <div v-if="showUserMenu" class="user-dropdown">
                <button class="dropdown-item" @click="handleLogout">
                  <LogOut :size="14" />
                  <span>退出登录</span>
                </button>
              </div>
            </Transition>
          </div>
        </template>
        <template v-else>
          <button class="login-btn" @click="showLoginModal = true">登录</button>
        </template>

        <div class="connection-status" :class="connectionStatusClass">
          <component :is="isConnected ? Wifi : WifiOff" class="conn-icon" />
          <span class="conn-label">{{ connectionStatusText }}</span>
        </div>
      </div>
    </div>

    <!-- Login modal -->
    <Teleport to="body">
      <LoginModal v-if="showLoginModal" @close="showLoginModal = false" />
    </Teleport>
  </header>
</template>

<style scoped>
.header-bar {
  background: var(--bg-primary, #fff);
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  padding: 0 16px;
  flex-shrink: 0;
}
.header-inner {
  display: flex;
  align-items: center;
  height: 44px;
  gap: 12px;
}
.header-logo { flex-shrink: 0; }
.logo-icon {
  width: 28px; height: 28px;
  background: #111827;
  border-radius: 6px;
  display: grid;
  place-items: center;
}
.logo-text { color: #fff; font-weight: 700; font-size: 11px; }
.header-center {
  flex: 1; min-width: 0;
  display: flex; align-items: center; gap: 10px;
}
.header-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

/* User area */
.user-area {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  position: relative;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.15s;
}
.user-area:hover { background: #f3f4f6; }
.user-name { font-size: 13px; font-weight: 500; color: var(--text-primary, #374151); }
.role-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: #fef3c7;
  color: #d97706;
  border-radius: 3px;
  font-weight: 500;
}
.user-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: white;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  min-width: 140px;
  z-index: 100;
  overflow: hidden;
}
.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--text-primary, #374151);
  transition: background 0.15s;
}
.dropdown-item:hover { background: #f9fafb; }
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }

.login-btn {
  padding: 5px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--primary-color, #3b82f6);
  border: 1px solid var(--primary-color, #3b82f6);
  border-radius: 6px;
  transition: all 0.15s;
}
.login-btn:hover {
  background: var(--primary-color, #3b82f6);
  color: white;
}

.connection-status { display: flex; align-items: center; gap: 4px; }
.conn-icon { width: 14px; height: 14px; }
.conn-label { font-size: 12px; }
.conn-ok { color: #059669; }
.conn-ing { color: #d97706; }
.conn-err { color: #dc2626; }
.conn-off { color: #6b7280; }
</style>
