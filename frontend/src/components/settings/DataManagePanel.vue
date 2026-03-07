<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminApi } from './useAdminApi'

const { adminRequest } = useAdminApi()

// ── Types ──────────────────────────────────────────────────────────────────
interface DiscussionItem {
  id: string
  topic: string
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
  created_at: string
  discussion_count: number
}

type SortField = 'name' | 'created_at' | 'discussion_count'
type SortDir = 'asc' | 'desc'

// ── State ──────────────────────────────────────────────────────────────────
const activeTab = ref<'project' | 'discussion'>('project')
const searchQuery = ref('')
const discussions = ref<DiscussionItem[]>([])
const projects = ref<ProjectItem[]>([])
const loadingDisc = ref(false)
const loadingProj = ref(false)
const confirmItem = ref<any>(null)
const confirmType = ref<'discussion' | 'project'>('project')
const deleting = ref(false)
const errorMsg = ref('')

// Sort state
const projSort = ref<SortField>('created_at')
const projSortDir = ref<SortDir>('desc')
const discSort = ref<'updated_at' | 'topic'>('updated_at')
const discSortDir = ref<SortDir>('desc')

// ── Computed ───────────────────────────────────────────────────────────────
const filteredProj = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  let list = q
    ? projects.value.filter(p =>
        p.name.toLowerCase().includes(q) ||
        (p.owner_name || '').toLowerCase().includes(q) ||
        p.id.includes(q)
      )
    : [...projects.value]

  list.sort((a, b) => {
    let va: any = a[projSort.value]
    let vb: any = b[projSort.value]
    if (projSort.value === 'discussion_count') {
      va = va ?? 0; vb = vb ?? 0
    } else {
      va = va ?? ''; vb = vb ?? ''
    }
    if (va < vb) return projSortDir.value === 'asc' ? -1 : 1
    if (va > vb) return projSortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return list
})

const filteredDisc = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  let list = q
    ? discussions.value.filter(d =>
        d.topic.toLowerCase().includes(q) ||
        (d.owner_name || '').toLowerCase().includes(q)
      )
    : [...discussions.value]

  list.sort((a, b) => {
    const va = (a as any)[discSort.value] ?? ''
    const vb = (b as any)[discSort.value] ?? ''
    if (va < vb) return discSortDir.value === 'asc' ? -1 : 1
    if (va > vb) return discSortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return list
})

// ── Methods ────────────────────────────────────────────────────────────────
async function loadDiscussions() {
  loadingDisc.value = true
  errorMsg.value = ''
  try {
    const data = await adminRequest<{ items: DiscussionItem[] }>('/data/discussions?page_size=200')
    discussions.value = data.items || []
  } catch (e: any) {
    errorMsg.value = e?.message || '加载讨论失败'
  } finally {
    loadingDisc.value = false
  }
}

async function loadProjects() {
  loadingProj.value = true
  errorMsg.value = ''
  try {
    const data = await adminRequest<{ items: ProjectItem[] }>('/data/projects')
    projects.value = data.items || []
  } catch (e: any) {
    errorMsg.value = e?.message || '加载项目失败'
  } finally {
    loadingProj.value = false
  }
}

function refresh() {
  loadDiscussions()
  loadProjects()
}

function toggleProjSort(field: SortField) {
  if (projSort.value === field) {
    projSortDir.value = projSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    projSort.value = field
    projSortDir.value = field === 'discussion_count' ? 'desc' : 'desc'
  }
}

function toggleDiscSort(field: 'updated_at' | 'topic') {
  if (discSort.value === field) {
    discSortDir.value = discSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    discSort.value = field
    discSortDir.value = 'desc'
  }
}

function confirmDelete(item: any, type: 'discussion' | 'project') {
  confirmItem.value = item
  confirmType.value = type
}

async function doDelete() {
  if (!confirmItem.value) return
  deleting.value = true
  errorMsg.value = ''
  try {
    const id = confirmItem.value.id
    if (confirmType.value === 'discussion') {
      await adminRequest(`/data/discussions/${id}`, { method: 'DELETE' })
      discussions.value = discussions.value.filter(d => d.id !== id)
    } else {
      await adminRequest(`/data/projects/${id}`, { method: 'DELETE' })
      projects.value = projects.value.filter(p => p.id !== id)
    }
    confirmItem.value = null
    window.dispatchEvent(new CustomEvent('bw:hall-refresh'))
  } catch (e: any) {
    errorMsg.value = e?.message || '删除失败'
  } finally {
    deleting.value = false
  }
}

function formatDate(dt: string) {
  if (!dt) return '—'
  const d = new Date(dt)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

function formatDateTime(dt: string) {
  if (!dt) return '—'
  const d = new Date(dt)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(refresh)
</script>

<template>
  <div class="dm-panel">
    <!-- Error -->
    <div v-if="errorMsg" class="dm-error">{{ errorMsg }}</div>

    <!-- Tab bar + refresh -->
    <div class="dm-topbar">
      <div class="dm-tabs">
        <button class="dm-tab" :class="{ 'dm-tab--active': activeTab === 'project' }" @click="activeTab = 'project'">
          项目
          <span class="dm-tab-count">{{ projects.length }}</span>
        </button>
        <button class="dm-tab" :class="{ 'dm-tab--active': activeTab === 'discussion' }" @click="activeTab = 'discussion'">
          大厅讨论
          <span class="dm-tab-count">{{ discussions.length }}</span>
        </button>
      </div>
      <button class="dm-refresh" @click="refresh" title="刷新">
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
        </svg>
        刷新
      </button>
    </div>

    <!-- Search -->
    <div class="dm-search">
      <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input v-model="searchQuery" class="dm-search-input" placeholder="搜索名称、创建者..." />
    </div>

    <!-- ── Projects ──────────────────────────────────────────────────────── -->
    <div v-if="activeTab === 'project'">
      <!-- Sort bar -->
      <div class="dm-sort-bar">
        <span class="dm-sort-label">排序：</span>
        <button
          v-for="s in ([['name','名称'],['created_at','创建时间'],['discussion_count','讨论数']] as [SortField, string][])"
          :key="s[0]"
          class="dm-sort-btn"
          :class="{ 'dm-sort-btn--active': projSort === s[0] }"
          @click="toggleProjSort(s[0])"
        >
          {{ s[1] }}
          <span v-if="projSort === s[0]" class="dm-sort-arrow">{{ projSortDir === 'asc' ? '↑' : '↓' }}</span>
        </button>
      </div>

      <div v-if="loadingProj" class="dm-empty">加载中...</div>
      <div v-else-if="filteredProj.length === 0" class="dm-empty">暂无项目</div>
      <div v-else class="dm-list">
        <div v-for="item in filteredProj" :key="item.id" class="dm-row">
          <div class="dm-info">
            <div class="dm-name">
              {{ item.name }}
              <span class="dm-tag" :class="item.is_public ? 'dm-tag--green' : 'dm-tag--muted'">
                {{ item.is_public ? '公开' : '私密' }}
              </span>
            </div>
            <div class="dm-proj-meta">
              <span class="dm-meta-item">
                <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                {{ item.owner_name || '未知' }}
              </span>
              <span class="dm-meta-item">
                <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                {{ item.discussion_count }} 次讨论
              </span>
              <span class="dm-meta-item">
                <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                {{ formatDate(item.created_at) }}
              </span>
              <span v-if="item.description" class="dm-meta-desc">{{ item.description }}</span>
            </div>
          </div>
          <button class="dm-del-btn" @click="confirmDelete(item, 'project')">删除</button>
        </div>
      </div>
    </div>

    <!-- ── Discussions ───────────────────────────────────────────────────── -->
    <div v-if="activeTab === 'discussion'">
      <!-- Sort bar -->
      <div class="dm-sort-bar">
        <span class="dm-sort-label">排序：</span>
        <button
          v-for="s in ([['updated_at','更新时间'],['topic','名称']] as ['updated_at' | 'topic', string][])"
          :key="s[0]"
          class="dm-sort-btn"
          :class="{ 'dm-sort-btn--active': discSort === s[0] }"
          @click="toggleDiscSort(s[0])"
        >
          {{ s[1] }}
          <span v-if="discSort === s[0]" class="dm-sort-arrow">{{ discSortDir === 'asc' ? '↑' : '↓' }}</span>
        </button>
      </div>

      <div v-if="loadingDisc" class="dm-empty">加载中...</div>
      <div v-else-if="filteredDisc.length === 0" class="dm-empty">暂无大厅讨论</div>
      <div v-else class="dm-list">
        <div v-for="item in filteredDisc" :key="item.id" class="dm-row">
          <div class="dm-info">
            <div class="dm-name">
              {{ item.topic }}
              <span v-if="item.archived" class="dm-tag dm-tag--muted">已归档</span>
            </div>
            <div class="dm-proj-meta">
              <span v-if="item.owner_name" class="dm-meta-item">
                <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                {{ item.owner_name }}
              </span>
              <span class="dm-meta-item">
                <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                {{ formatDateTime(item.updated_at) }}
              </span>
              <span class="dm-id">{{ item.id.slice(0, 8) }}</span>
            </div>
          </div>
          <button class="dm-del-btn" @click="confirmDelete(item, 'discussion')">删除</button>
        </div>
      </div>
    </div>

    <!-- Confirm Modal -->
    <Transition name="fade">
      <div v-if="confirmItem" class="dm-modal-overlay" @click.self="confirmItem = null">
        <div class="dm-modal">
          <div class="dm-modal-title">确认删除</div>
          <p class="dm-modal-body">即将永久删除{{ confirmType === 'discussion' ? '讨论' : '项目' }}：</p>
          <p class="dm-modal-name">「{{ confirmType === 'discussion' ? confirmItem.topic : confirmItem.name }}」</p>
          <p class="dm-modal-warn">此操作不可撤销，所有相关数据将被删除。</p>
          <div v-if="errorMsg" class="dm-modal-err">{{ errorMsg }}</div>
          <div class="dm-modal-actions">
            <button class="dm-btn dm-btn--secondary" @click="confirmItem = null">取消</button>
            <button class="dm-btn dm-btn--danger" :disabled="deleting" @click="doDelete">
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dm-panel { display: flex; flex-direction: column; gap: 12px; }

.dm-error {
  padding: 8px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #dc2626;
  font-size: 13px;
}

.dm-topbar { display: flex; align-items: center; justify-content: space-between; }
.dm-tabs { display: flex; gap: 4px; }
.dm-tab {
  display: flex; align-items: center; gap: 5px;
  padding: 6px 14px;
  border: 1px solid #e5e7eb; border-radius: 8px;
  background: #fff; font-size: 13px; color: #6b7280;
  cursor: pointer; transition: all 0.15s;
}
.dm-tab:hover { background: #f9fafb; color: #111; }
.dm-tab--active { background: #111827; color: #fff; border-color: #111827; }
.dm-tab-count { font-size: 11px; opacity: 0.7; }

.dm-refresh {
  display: flex; align-items: center; gap: 5px;
  padding: 6px 12px;
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
  font-size: 12px; color: #6b7280; cursor: pointer; transition: all 0.15s;
}
.dm-refresh:hover { background: #f3f4f6; color: #111; }

.dm-search {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 12px;
  border: 1px solid #e5e7eb; border-radius: 8px;
  background: #fff; color: #9ca3af;
}
.dm-search-input {
  flex: 1; border: none; outline: none;
  font-size: 13px; color: #111827; background: transparent;
}
.dm-search-input::placeholder { color: #9ca3af; }

/* Sort bar */
.dm-sort-bar {
  display: flex; align-items: center; gap: 6px;
  padding-bottom: 4px;
  font-size: 12px;
}
.dm-sort-label { color: #9ca3af; }
.dm-sort-btn {
  display: flex; align-items: center; gap: 2px;
  padding: 3px 9px;
  border: 1px solid #e5e7eb; border-radius: 6px;
  background: #f9fafb; font-size: 12px; color: #6b7280;
  cursor: pointer; transition: all 0.12s;
}
.dm-sort-btn:hover { background: #f3f4f6; color: #374151; }
.dm-sort-btn--active { background: #eff6ff; border-color: #93c5fd; color: #1d4ed8; }
.dm-sort-arrow { font-size: 11px; }

.dm-empty { text-align: center; padding: 32px; color: #9ca3af; font-size: 13px; }
.dm-list { display: flex; flex-direction: column; gap: 6px; }

.dm-row {
  display: flex; align-items: flex-start;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
  gap: 10px; transition: box-shadow 0.15s;
}
.dm-row:hover { box-shadow: 0 1px 4px rgba(0,0,0,0.06); background: #fff; }

.dm-info { flex: 1; min-width: 0; }
.dm-name {
  font-size: 13.5px; font-weight: 500; color: #111827;
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-bottom: 5px;
}

/* Project meta row */
.dm-proj-meta {
  display: flex; flex-wrap: wrap; gap: 10px;
  font-size: 11.5px; color: #6b7280;
}
.dm-meta-item {
  display: flex; align-items: center; gap: 3px;
}
.dm-meta-desc {
  color: #9ca3af;
  max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dm-id { font-family: monospace; color: #d1d5db; font-size: 11px; }

.dm-tag {
  font-size: 10px; font-weight: 600;
  padding: 1px 7px; border-radius: 999px;
}
.dm-tag--muted { background: #f3f4f6; color: #6b7280; }
.dm-tag--green { background: #d1fae5; color: #065f46; }
.dm-tag--blue { background: #dbeafe; color: #1e40af; }

.dm-del-btn {
  flex-shrink: 0;
  padding: 4px 10px;
  background: #fef2f2; color: #dc2626;
  border: 1px solid #fecaca; border-radius: 6px;
  font-size: 12px; cursor: pointer; transition: all 0.12s;
  margin-top: 1px;
}
.dm-del-btn:hover { background: #fee2e2; }

/* Modal */
.dm-modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 200;
}
.dm-modal {
  background: #fff; border-radius: 12px; padding: 24px;
  max-width: 400px; width: calc(100% - 32px);
  box-shadow: 0 20px 60px rgba(0,0,0,0.15);
}
.dm-modal-title { font-size: 17px; font-weight: 700; margin-bottom: 12px; }
.dm-modal-body { color: #6b7280; font-size: 13.5px; margin: 0 0 4px; }
.dm-modal-name { font-size: 14px; font-weight: 600; color: #111827; margin: 0 0 8px; }
.dm-modal-warn { color: #dc2626; font-size: 12.5px; margin: 0 0 16px; }
.dm-modal-err { color: #dc2626; font-size: 12px; margin-bottom: 12px; }
.dm-modal-actions { display: flex; gap: 8px; justify-content: flex-end; }

.dm-btn {
  padding: 7px 16px; border-radius: 7px;
  font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.12s;
}
.dm-btn--secondary { background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb; }
.dm-btn--secondary:hover { background: #e5e7eb; }
.dm-btn--danger { background: #dc2626; color: #fff; border: none; }
.dm-btn--danger:hover { background: #b91c1c; }
.dm-btn--danger:disabled { opacity: 0.5; cursor: not-allowed; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
