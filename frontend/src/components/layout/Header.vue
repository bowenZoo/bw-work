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
      return 'Connected';
    case 'connecting':
      return 'Connecting...';
    case 'disconnected':
      return 'Disconnected';
    case 'error':
      return 'Connection Error';
    default:
      return 'Offline';
  }
});

const connectionStatusClass = computed(() => {
  switch (props.connectionStatus) {
    case 'connected':
      return 'text-green-600';
    case 'connecting':
      return 'text-yellow-600';
    case 'error':
      return 'text-red-600';
    default:
      return 'text-gray-500';
  }
});

const isConnected = computed(() => props.connectionStatus === 'connected');
</script>

<template>
  <header class="bg-white border-b border-gray-200 px-4 py-3">
    <div class="flex items-center justify-between">
      <!-- Logo and title -->
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-sm">AI</span>
        </div>
        <div>
          <h1 class="text-lg font-semibold text-gray-900">Game Planning AI Team</h1>
          <p class="text-xs text-gray-500">Multi-agent discussion system</p>
        </div>
      </div>

      <!-- Extra slot and connection status -->
      <div class="flex items-center gap-4">
        <!-- Extra slot for additional content -->
        <slot name="extra" />

        <!-- Connection status -->
        <div class="flex items-center gap-2" :class="connectionStatusClass">
          <component :is="isConnected ? Wifi : WifiOff" class="w-4 h-4" />
          <span class="text-sm">{{ connectionStatusText }}</span>
        </div>
      </div>
    </div>
  </header>
</template>
