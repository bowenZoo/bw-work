<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">数据管理</h1>
        <p class="text-zinc-400 mt-1">管理所有讨论与项目</p>
      </div>
      <button @click="loadAll" class="flex items-center gap-2 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm text-white transition-colors">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        刷新
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-2">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        :class="[
          'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
          activeTab === tab.key
            ? 'bg-white text-black'
            : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
        ]"
      >
        {{ tab.label }}
        <span v-if="tab.key === 'discussion'" class="ml-1 text-xs opacity-60">({{ discussions.length }})</span>
        <span v-if="tab.key === 'project'" class="ml-1 text-xs opacity-60">({{ projects.length }})</span>
      </button>
    </div>

    <!-- Search -->
    <div class="relative">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <input
        v-model="searchQuery"
        placeholder="搜索..."
        class="w-full pl-9 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 text-sm focus:outline-none focus:border-zinc-500"
      />
    </div>

    <!-- Discussions Tab -->
    <div v-if="activeTab === 'discussion'">
      <div v-if="loadingDiscussions" class="text-center py-12 text-zinc-500">加载中...</div>
      <div v-else-if="filteredDiscussions.length === 0" class="text-center py-12 text-zinc-500">暂无讨论</div>
      <div v-else class="space-y-2">
        <div
          v-for="item in filteredDiscussions"
          :key="item.id"
          class="flex items-center justify-between p-4 bg-zinc-800 rounded-lg hover:bg-zinc-750 transition-colors"
        >
          <div class="flex-1 min-w-0 mr-4">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-white font-medium truncate">{{ item.topic }}</span>
              <span v-if="item.archived" class="px-2 py-0.5 bg-zinc-700 text-zinc-400 text-xs rounded">已归档</span>
              <span v-if="item.project_id" class="px-2 py-0.5 bg-blue-900/50 text-blue-400 text-xs rounded">项目讨论</span>
            </div>
            <div class="flex items-center gap-3 text-xs text-zinc-500">
              <span v-if="item.owner_name">👤 {{ item.owner_name }}</span>
              <span v-if="item.updated_at">{{ formatDate(item.updated_at) }}</span>
              <span class="font-mono text-zinc-600 truncate max-w-[200px]">{{ item.id }}</span>
            </div>
          </div>
          <button
            @click="confirmDeleteDiscussion(item)"
            class="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-red-900/50 hover:bg-red-800/70 text-red-400 hover:text-red-300 rounded-lg text-sm transition-colors"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            删除
          </button>
        </div>
      </div>
    </div>

    <!-- Projects Tab -->
    <div v-if="activeTab === 'project'">
      <div v-if="loadingProjects" class="text-center py-12 text-zinc-500">加载中...</div>
      <div v-else-if="filteredProjects.length === 0" class="text-center py-12 text-zinc-500">暂无项目</div>
      <div v-else class="space-y-2">
        <div
          v-for="item in filteredProjects"
          :key="item.id"
          class="flex items-center justify-between p-4 bg-zinc-800 rounded-lg hover:bg-zinc-750 transition-colors"
        >
          <div class="flex-1 min-w-0 mr-4">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-white font-medium truncate">{{ item.name }}</span>
              <span v-if="item.is_public" class="px-2 py-0.5 bg-emerald-900/50 text-emerald-400 text-xs rounded">公开</span>
              <span v-else class="px-2 py-0.5 bg-zinc-700 text-zinc-400 text-xs rounded">私密</span>
            </div>
            <div class="flex items-center gap-3 text-xs text-zinc-500">
              <span v-if="item.description" class="truncate max-w-[300px]">{{ item.description }}</span>
              <span v-if="item.owner_name">👤 {{ item.owner_name }}</span>
              <span class="font-mono text-zinc-600">{{ item.id }}</span>
            </div>
          </div>
          <button
            @click="confirmDeleteProject(item)"
            class="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-red-900/50 hover:bg-red-800/70 text-red-400 hover:text-red-300 rounded-lg text-sm transition-colors"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            删除
          </button>
        </div>
      </div>
    </div>

    <!-- Confirm Dialog -->
    <Transition name="fade">
      <div v-if="confirmItem" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div class="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl">
          <div class="flex items-center gap-3 mb-4">
            <div class="p-2 bg-red-900/50 rounded-lg">
              <svg class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 class="text-white font-semibold text-lg">确认删除</h3>
          </div>
          <p class="text-zinc-400 mb-2">
            即将永久删除{{ confirmType === 'discussion' ? '讨论' : '项目' }}：
          </p>
          <p class="text-white font-medium mb-1">「{{ confirmType === 'discussion' ? confirmItem.topic : confirmItem.name }}」</p>
          <p class="text-red-400 text-sm mb-6">此操作不可撤销，所有相关数据将被删除。</p>
          <div class="flex gap-3 justify-end">
            <button @click="confirmItem = null" class="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm transition-colors">
              取消
            </button>
            <button
              @click="doDelete"
              :disabled="deleting"
              class="px-4 py-2 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white rounded-lg text-sm transition-colors flex items-center gap-2"
            >
              <svg v-if="deleting" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
              确认删除
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

interface DiscussionItem {
  id: string
  topic: string
  summary: string
  owner_name: string | null
  updated_at: string
  archived: boolean
  project_id: string | null
}

interface ProjectItem {
  id: string
  name: string
  description: string
  is_public: boolean
  owner_name: string | null
}

const tabs = [
  { key: 'discussion', label: '讨论' },
  { key: 'project', label: '项目' },
]

const activeTab = ref('discussion')
const searchQuery = ref('')

const discussions = ref<DiscussionItem[]>([])
const projects = ref<ProjectItem[]>([])
const loadingDiscussions = ref(false)
const loadingProjects = ref(false)

const confirmItem = ref<any>(null)
const confirmType = ref<'discussion' | 'project'>('discussion')
const deleting = ref(false)

const filteredDiscussions = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return discussions.value
  return discussions.value.filter(d =>
    d.topic.toLowerCase().includes(q) ||
    (d.owner_name || '').toLowerCase().includes(q) ||
    d.id.includes(q)
  )
})

const filteredProjects = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return projects.value
  return projects.value.filter(p =>
    p.name.toLowerCase().includes(q) ||
    (p.owner_name || '').toLowerCase().includes(q) ||
    p.id.includes(q)
  )
})

function formatDate(dt: string): string {
  if (!dt) return ''
  const d = new Date(dt)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function loadDiscussions() {
  loadingDiscussions.value = true
  try {
    const data = await apiRequest<{ items: DiscussionItem[] }>('/data/discussions?page_size=200')
    discussions.value = data.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loadingDiscussions.value = false
  }
}

async function loadProjects() {
  loadingProjects.value = true
  try {
    const data = await apiRequest<{ items: ProjectItem[] }>('/data/projects')
    projects.value = data.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loadingProjects.value = false
  }
}

function loadAll() {
  loadDiscussions()
  loadProjects()
}

function confirmDeleteDiscussion(item: DiscussionItem) {
  confirmItem.value = item
  confirmType.value = 'discussion'
}

function confirmDeleteProject(item: ProjectItem) {
  confirmItem.value = item
  confirmType.value = 'project'
}

async function doDelete() {
  if (!confirmItem.value) return
  deleting.value = true
  try {
    const id = confirmItem.value.id
    if (confirmType.value === 'discussion') {
      await apiRequest(`/data/discussions/${id}`, { method: 'DELETE' })
      discussions.value = discussions.value.filter(d => d.id !== id)
    } else {
      await apiRequest(`/data/projects/${id}`, { method: 'DELETE' })
      projects.value = projects.value.filter(p => p.id !== id)
    }
    confirmItem.value = null
  } catch (e: any) {
    alert(e?.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
