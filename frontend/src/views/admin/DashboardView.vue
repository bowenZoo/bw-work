<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-white">Dashboard</h1>
      <p class="text-gray-400 mt-1">System overview and status</p>
    </div>

    <!-- Status Cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- LLM Status -->
      <div class="bg-gray-800 rounded-lg p-6">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="p-2 bg-blue-900/50 rounded-lg">
              <svg class="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h3 class="text-white font-medium">LLM Provider</h3>
              <p class="text-gray-400 text-sm">OpenAI API</p>
            </div>
          </div>
          <span
            :class="[
              'px-3 py-1 rounded-full text-sm',
              status.llm_configured
                ? 'bg-green-900/50 text-green-400'
                : 'bg-yellow-900/50 text-yellow-400'
            ]"
          >
            {{ status.llm_configured ? 'Active' : 'Not Configured' }}
          </span>
        </div>
      </div>

      <!-- Langfuse Status -->
      <div class="bg-gray-800 rounded-lg p-6">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="p-2 bg-purple-900/50 rounded-lg">
              <svg class="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div>
              <h3 class="text-white font-medium">Langfuse</h3>
              <p class="text-gray-400 text-sm">Monitoring</p>
            </div>
          </div>
          <span
            :class="[
              'px-3 py-1 rounded-full text-sm',
              status.langfuse_enabled
                ? 'bg-green-900/50 text-green-400'
                : status.langfuse_configured
                ? 'bg-yellow-900/50 text-yellow-400'
                : 'bg-gray-700 text-gray-400'
            ]"
          >
            {{ status.langfuse_enabled ? 'Enabled' : status.langfuse_configured ? 'Disabled' : 'Not Configured' }}
          </span>
        </div>
      </div>

      <!-- Image Service Status -->
      <div class="bg-gray-800 rounded-lg p-6">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="p-2 bg-green-900/50 rounded-lg">
              <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h3 class="text-white font-medium">Image Service</h3>
              <p class="text-gray-400 text-sm">{{ status.default_image_provider || 'DALL-E' }}</p>
            </div>
          </div>
          <span
            :class="[
              'px-3 py-1 rounded-full text-sm',
              status.image_configured
                ? 'bg-green-900/50 text-green-400'
                : 'bg-yellow-900/50 text-yellow-400'
            ]"
          >
            {{ status.image_configured ? 'Active' : 'Not Configured' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-lg font-semibold text-white mb-4">Quick Actions</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <router-link
          to="/admin/llm"
          class="p-4 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors text-center"
        >
          <svg class="w-8 h-8 text-blue-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span class="text-gray-300 text-sm">Configure LLM</span>
        </router-link>

        <router-link
          to="/admin/langfuse"
          class="p-4 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors text-center"
        >
          <svg class="w-8 h-8 text-purple-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <span class="text-gray-300 text-sm">Langfuse</span>
        </router-link>

        <router-link
          to="/admin/image"
          class="p-4 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors text-center"
        >
          <svg class="w-8 h-8 text-green-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span class="text-gray-300 text-sm">Image Service</span>
        </router-link>

        <router-link
          to="/admin/logs"
          class="p-4 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-colors text-center"
        >
          <svg class="w-8 h-8 text-orange-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span class="text-gray-300 text-sm">Audit Logs</span>
        </router-link>
      </div>
    </div>

    <!-- Recent Activity -->
    <div class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-lg font-semibold text-white mb-4">Recent Activity</h2>
      <div v-if="recentLogs.length === 0" class="text-gray-400 text-center py-8">
        No recent activity
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="log in recentLogs"
          :key="log.id"
          class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg"
        >
          <div class="flex items-center space-x-3">
            <div
              :class="[
                'p-2 rounded-full',
                getActionColor(log.action)
              ]"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path v-if="log.action === 'login'" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                <path v-else-if="log.action === 'logout'" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                <path v-else-if="log.action === 'config_update'" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <span class="text-white">{{ log.username }}</span>
              <span class="text-gray-400 mx-2">-</span>
              <span class="text-gray-400">{{ formatAction(log.action) }}</span>
              <span v-if="log.target" class="text-gray-500 ml-1">({{ log.target }})</span>
            </div>
          </div>
          <span class="text-gray-500 text-sm">{{ formatTime(log.timestamp) }}</span>
        </div>
      </div>
    </div>

    <!-- System Info -->
    <div class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-lg font-semibold text-white mb-4">System Information</h2>
      <div class="grid grid-cols-2 gap-4 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-400">Backend Version</span>
          <span class="text-white">0.1.0</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-400">Database</span>
          <span class="text-white">SQLite</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-400">API Port</span>
          <span class="text-white">18000</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-400">Admin Module</span>
          <span class="text-green-400">Active</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

interface ConfigStatus {
  llm_configured: boolean
  langfuse_configured: boolean
  langfuse_enabled: boolean
  image_configured: boolean
  default_image_provider: string | null
}

interface AuditLog {
  id: number
  timestamp: string
  action: string
  username: string
  target: string | null
}

const status = ref<ConfigStatus>({
  llm_configured: false,
  langfuse_configured: false,
  langfuse_enabled: false,
  image_configured: false,
  default_image_provider: null,
})

const recentLogs = ref<AuditLog[]>([])

function getActionColor(action: string): string {
  switch (action) {
    case 'login':
      return 'bg-green-900/50 text-green-400'
    case 'login_failed':
      return 'bg-red-900/50 text-red-400'
    case 'logout':
      return 'bg-yellow-900/50 text-yellow-400'
    case 'config_update':
    case 'config_delete':
      return 'bg-blue-900/50 text-blue-400'
    default:
      return 'bg-gray-700 text-gray-400'
  }
}

function formatAction(action: string): string {
  return action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

async function loadStatus() {
  try {
    const data = await apiRequest<ConfigStatus>('/config/status')
    status.value = data
  } catch (error) {
    console.error('Failed to load status:', error)
  }
}

async function loadRecentLogs() {
  try {
    const data = await apiRequest<{ items: AuditLog[] }>('/logs?page_size=5')
    recentLogs.value = data.items || []
  } catch (error) {
    console.error('Failed to load logs:', error)
  }
}

onMounted(() => {
  loadStatus()
  loadRecentLogs()
})
</script>
