<script setup lang="ts">
import { computed } from 'vue';
import { Wifi, WifiOff } from 'lucide-vue-next';
import type { ConnectionStatus } from '@/types';

const props = defineProps<{
  connectionStatus?: ConnectionStatus;
}>();

const connectionStatusText = computed(() => {
  switch (props.connectionStatus) {
    case 'connected':
      return '已连接';
    case 'connecting':
      return '连接中...';
    case 'disconnected':
      return '已断开';
    case 'error':
      return '连接错误';
    default:
      return '离线';
  }
});

const connectionStatusClass = computed(() => {
  switch (props.connectionStatus) {
    case 'connected':
      return 'conn-ok';
    case 'connecting':
      return 'conn-ing';
    case 'error':
      return 'conn-err';
    default:
      return 'conn-off';
  }
});

const isConnected = computed(() => props.connectionStatus === 'connected');
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

      <!-- Center: topic slot (replaces old topic-bar) -->
      <div class="header-center">
        <slot name="topic" />
      </div>

      <!-- Right: extra slot + connection status -->
      <div class="header-right">
        <slot name="extra" />
        <div class="connection-status" :class="connectionStatusClass">
          <component :is="isConnected ? Wifi : WifiOff" class="conn-icon" />
          <span class="conn-label">{{ connectionStatusText }}</span>
        </div>
      </div>
    </div>
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

.header-logo {
  flex-shrink: 0;
}

.logo-icon {
  width: 28px;
  height: 28px;
  background: #111827;
  border-radius: 6px;
  display: grid;
  place-items: center;
}

.logo-text {
  color: #fff;
  font-weight: 700;
  font-size: 11px;
}

.header-center {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 4px;
}

.conn-icon {
  width: 14px;
  height: 14px;
}

.conn-label {
  font-size: 12px;
}

.conn-ok { color: #059669; }
.conn-ing { color: #d97706; }
.conn-err { color: #dc2626; }
.conn-off { color: #6b7280; }
</style>
