<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-white">操作日志</h1>
      <p class="text-gray-400 mt-1">查看系统活动和安全事件</p>
    </div>

    <!-- Filters -->
    <div class="bg-gray-800 rounded-lg p-4">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <!-- Action Filter -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1">操作类型</label>
          <select
            v-model="filters.action"
            @change="loadLogs"
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">全部操作</option>
            <option value="login">登录</option>
            <option value="login_failed">登录失败</option>
            <option value="logout">退出</option>
            <option value="config_update">配置更新</option>
            <option value="config_delete">配置删除</option>
            <option value="bootstrap_setup">初始设置</option>
          </select>
        </div>

        <!-- Username Filter -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1">用户名</label>
          <input
            v-model="filters.username"
            @input="debouncedLoadLogs"
            type="text"
            placeholder="按用户名筛选..."
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <!-- Start Date -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1">开始日期</label>
          <input
            v-model="filters.start_date"
            @change="loadLogs"
            type="date"
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <!-- End Date -->
        <div>
          <label class="block text-sm font-medium text-gray-300 mb-1">结束日期</label>
          <input
            v-model="filters.end_date"
            @change="loadLogs"
            type="date"
            class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <!-- Clear Filters -->
      <div class="mt-3 flex justify-end">
        <button
          @click="clearFilters"
          class="text-sm text-gray-400 hover:text-white transition-colors"
        >
          清除筛选
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-12">
      <svg class="animate-spin h-8 w-8 text-blue-500" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
      </svg>
    </div>

    <!-- Logs Table -->
    <div v-else class="bg-gray-800 rounded-lg overflow-hidden">
      <div v-if="logs.length === 0" class="text-center py-12 text-gray-400">
        暂无日志记录
      </div>

      <table v-else class="w-full">
        <thead class="bg-gray-700/50">
          <tr>
            <th class="px-4 py-3 text-left text-sm font-medium text-gray-300">时间</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-gray-300">操作</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-gray-300">用户</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-gray-300">目标</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-gray-300">IP 地址</th>
            <th class="px-4 py-3 text-left text-sm font-medium text-gray-300">详情</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-700">
          <tr
            v-for="log in logs"
            :key="log.id"
            class="hover:bg-gray-700/30 transition-colors"
          >
            <td class="px-4 py-3 text-sm text-gray-300">
              {{ formatDateTime(log.timestamp) }}
            </td>
            <td class="px-4 py-3">
              <span
                :class="[
                  'px-2 py-1 rounded text-xs font-medium',
                  getActionBadgeClass(log.action)
                ]"
              >
                {{ formatAction(log.action) }}
              </span>
            </td>
            <td class="px-4 py-3 text-sm text-white">
              {{ log.username }}
            </td>
            <td class="px-4 py-3 text-sm text-gray-400">
              {{ log.target || '-' }}
            </td>
            <td class="px-4 py-3 text-sm text-gray-400 font-mono">
              {{ log.ip_address || '-' }}
            </td>
            <td class="px-4 py-3 text-sm">
              <button
                v-if="log.before_value || log.after_value || log.details"
                @click="showDetails(log)"
                class="text-blue-400 hover:text-blue-300 transition-colors"
              >
                查看
              </button>
              <span v-else class="text-gray-500">-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between">
      <div class="text-sm text-gray-400">
        显示第 {{ (currentPage - 1) * pageSize + 1 }} 至 {{ Math.min(currentPage * pageSize, totalItems) }} 条，共 {{ totalItems }} 条
      </div>
      <div class="flex items-center space-x-2">
        <button
          @click="goToPage(currentPage - 1)"
          :disabled="currentPage === 1"
          class="px-3 py-1 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          上一页
        </button>
        <span class="text-gray-400">
          第 {{ currentPage }} / {{ totalPages }} 页
        </span>
        <button
          @click="goToPage(currentPage + 1)"
          :disabled="currentPage === totalPages"
          class="px-3 py-1 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          下一页
        </button>
      </div>
    </div>

    <!-- Details Modal -->
    <div
      v-if="selectedLog"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="selectedLog = null"
    >
      <div class="bg-gray-800 rounded-lg p-6 max-w-lg w-full mx-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-white">日志详情</h3>
          <button
            @click="selectedLog = null"
            class="text-gray-400 hover:text-white transition-colors"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="space-y-4">
          <div v-if="selectedLog.before_value">
            <label class="block text-sm font-medium text-gray-400 mb-1">修改前</label>
            <div class="p-3 bg-gray-900 rounded-lg text-red-400 font-mono text-sm break-all">
              {{ selectedLog.before_value }}
            </div>
          </div>

          <div v-if="selectedLog.after_value">
            <label class="block text-sm font-medium text-gray-400 mb-1">修改后</label>
            <div class="p-3 bg-gray-900 rounded-lg text-green-400 font-mono text-sm break-all">
              {{ selectedLog.after_value }}
            </div>
          </div>

          <div v-if="selectedLog.details">
            <label class="block text-sm font-medium text-gray-400 mb-1">详细信息</label>
            <div class="p-3 bg-gray-900 rounded-lg text-gray-300 text-sm">
              {{ selectedLog.details }}
            </div>
          </div>

          <div v-if="selectedLog.user_agent">
            <label class="block text-sm font-medium text-gray-400 mb-1">用户代理</label>
            <div class="p-3 bg-gray-900 rounded-lg text-gray-400 text-xs break-all">
              {{ selectedLog.user_agent }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

interface AuditLog {
  id: number
  timestamp: string
  action: string
  username: string
  target: string | null
  ip_address: string | null
  user_agent: string | null
  before_value: string | null
  after_value: string | null
  details: string | null
}

const logs = ref<AuditLog[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalItems = ref(0)
const totalPages = ref(0)
const selectedLog = ref<AuditLog | null>(null)

const filters = reactive({
  action: '',
  username: '',
  start_date: '',
  end_date: '',
})

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function debouncedLoadLogs() {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
  debounceTimer = setTimeout(() => {
    loadLogs()
  }, 300)
}

async function loadLogs() {
  loading.value = true

  try {
    const params = new URLSearchParams()
    params.append('page', currentPage.value.toString())
    params.append('page_size', pageSize.value.toString())

    if (filters.action) {
      params.append('action', filters.action)
    }
    if (filters.username) {
      params.append('username', filters.username)
    }
    if (filters.start_date) {
      params.append('start_time', new Date(filters.start_date).toISOString())
    }
    if (filters.end_date) {
      // End of day
      const endDate = new Date(filters.end_date)
      endDate.setHours(23, 59, 59, 999)
      params.append('end_time', endDate.toISOString())
    }

    const response = await apiRequest<{
      items: AuditLog[]
      total: number
      page: number
      page_size: number
      total_pages: number
    }>(`/logs?${params.toString()}`)

    logs.value = response.items
    totalItems.value = response.total
    totalPages.value = response.total_pages
  } catch (error) {
    console.error('Failed to load logs:', error)
  } finally {
    loading.value = false
  }
}

function goToPage(page: number) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    loadLogs()
  }
}

function clearFilters() {
  filters.action = ''
  filters.username = ''
  filters.start_date = ''
  filters.end_date = ''
  currentPage.value = 1
  loadLogs()
}

function showDetails(log: AuditLog) {
  selectedLog.value = log
}

function formatDateTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleString()
}

function formatAction(action: string): string {
  return action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

function getActionBadgeClass(action: string): string {
  switch (action) {
    case 'login':
      return 'bg-green-900/50 text-green-400'
    case 'login_failed':
      return 'bg-red-900/50 text-red-400'
    case 'logout':
      return 'bg-yellow-900/50 text-yellow-400'
    case 'config_update':
      return 'bg-blue-900/50 text-blue-400'
    case 'config_delete':
      return 'bg-orange-900/50 text-orange-400'
    case 'bootstrap_setup':
      return 'bg-purple-900/50 text-purple-400'
    default:
      return 'bg-gray-700 text-gray-400'
  }
}

onMounted(() => {
  loadLogs()
})
</script>
