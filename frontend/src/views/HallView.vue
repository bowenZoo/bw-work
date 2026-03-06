<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHall } from '@/composables/useHall'
import { useUserStore } from '@/stores/user'
import UserMenu from '@/components/layout/UserMenu.vue'
import LoginModal from '@/components/auth/LoginModal.vue'
import AgentConfigEditor from '@/components/discussion/AgentConfigEditor.vue'
import type { DiscussionStyleFull, DiscussionStyleOverrides } from '@/types'

const router = useRouter()
const userStore = useUserStore()
const { items, loading, refresh, createProject, createDiscussion, loadStyles, discussionStylesFull, defaultStyleId } = useHall()

const showLoginModal = ref(false)
const showNewDiscussion = ref(false)
const showNewProject = ref(false)

const searchQuery = ref('')
const activeTab = ref('all')

const tabs = [
  { key: 'all', label: '全部' },
  { key: 'discussion', label: '讨论' },
  { key: 'project', label: '项目' },
  { key: 'completed', label: '已完成' },
  { key: 'archived', label: '已归档' },
]

function itemStatus(item: any): string {
  return item.extra?.status || ''
}

const statusOrder: Record<string, number> = {
  active: 0, running: 0,
  waiting: 1, paused: 1,
  completed: 2,
  archived: 3,
}

const filteredItems = computed(() => {
  let list = items.value
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(item =>
      item.name.toLowerCase().includes(q) ||
      (item.description || '').toLowerCase().includes(q)
    )
  }
  if (activeTab.value === 'discussion') {
    list = list.filter(item => item.type === 'discussion')
  } else if (activeTab.value === 'project') {
    list = list.filter(item => item.type === 'project')
  } else if (activeTab.value === 'completed') {
    list = list.filter(item => itemStatus(item) === 'completed')
  } else if (activeTab.value === 'archived') {
    list = list.filter(item => itemStatus(item) === 'archived')
  }
  return [...list].sort((a, b) => {
    if (a.type === 'discussion' && b.type === 'discussion') {
      const sa = statusOrder[itemStatus(a)] ?? 99
      const sb = statusOrder[itemStatus(b)] ?? 99
      if (sa !== sb) return sa - sb
    }
    const ta = new Date(a.updated_at || 0).getTime()
    const tb = new Date(b.updated_at || 0).getTime()
    return tb - ta
  })
})

const statusMap: Record<string, { label: string; cls: string }> = {
  active:    { label: '进行中', cls: 'status-active' },
  running:   { label: '进行中', cls: 'status-active' },
  waiting:   { label: '等待中', cls: 'status-waiting' },
  paused:    { label: '等待中', cls: 'status-waiting' },
  completed: { label: '已完成', cls: 'status-completed' },
  archived:  { label: '已归档', cls: 'status-archived' },
}
const newDiscussionTopic = ref('')
const newDiscussionProjectId = ref('')
const discussionGoal = ref('')
const showAdvancedModal = ref(false)
const advancedTab = ref<'base' | 'crew'>('base')
// === Crew Tab Logic ===
const AGENT_ROLES = [
  { id: 'lead_planner', name: '主策划', emoji: '👔', locked: true },
  { id: 'system_designer', name: '系统策划', emoji: '⚙️', locked: false },
  { id: 'number_designer', name: '数值策划', emoji: '📊', locked: false },
  { id: 'player_advocate', name: '玩家代言人', emoji: '🎮', locked: false },
  { id: 'operations_analyst', name: '市场运营', emoji: '📈', locked: false },
  { id: 'visual_concept', name: '视觉概念', emoji: '🎨', locked: false },
]
const crewDefaultConfigs = ref<Record<string, any>>({})

async function loadCrewDefaults() {
  try {
    const { getAvailableAgents } = await import('@/api/discussion')
    const result = await getAvailableAgents()
    crewDefaultConfigs.value = result.agents || {}
  } catch {}
}

const crewSelectedId = ref<string | null>('lead_planner')
const showAgentPicker = ref(false)
const crewFocusText = ref('')

const enabledAgentRoles = computed(() => {
  if (selectedAgents.value.length === 0) return AGENT_ROLES
  return AGENT_ROLES.filter(r => r.locked || selectedAgents.value.includes(r.id))
})
const availableAgentRoles = computed(() => {
  if (selectedAgents.value.length === 0) return []
  return AGENT_ROLES.filter(r => !r.locked && !selectedAgents.value.includes(r.id))
})
const crewSelectedRole = computed(() => AGENT_ROLES.find(r => r.id === crewSelectedId.value))
const crewSelectedConfig = computed(() => {
  if (!crewSelectedId.value) return null
  const id = crewSelectedId.value
  const defaults = crewDefaultConfigs.value[id] || {}
  if (!agentConfigs.value[id]) {
    agentConfigs.value[id] = {}
  }
  const overrides = agentConfigs.value[id]
  return {
    get goal() { return overrides.goal ?? defaults.goal ?? '' },
    set goal(v: string) { overrides.goal = v },
    get backstory() { return overrides.backstory ?? defaults.backstory ?? '' },
    set backstory(v: string) { overrides.backstory = v },
    get focus_areas() { return overrides.focus_areas ?? defaults.focus_areas ?? [] },
    set focus_areas(v: string[]) { overrides.focus_areas = v },
  }
})

function addAgent(id: string) {
  if (selectedAgents.value.length === 0) {
    selectedAgents.value = AGENT_ROLES.filter(r => r.locked).map(r => r.id)
  }
  if (!selectedAgents.value.includes(id)) selectedAgents.value.push(id)
  showAgentPicker.value = false
  crewSelectedId.value = id
}
function removeAgent(id: string) {
  const currentList = enabledAgentRoles.value
  const deletedIndex = currentList.findIndex(r => r.id === id)

  if (selectedAgents.value.length === 0) {
    selectedAgents.value = AGENT_ROLES.map(r => r.id).filter(a => a !== id)
  } else {
    selectedAgents.value = selectedAgents.value.filter(a => a !== id)
  }

  if (crewSelectedId.value === id) {
    const newList = enabledAgentRoles.value
    if (newList.length > 0) {
      const newIndex = Math.min(deletedIndex, newList.length - 1)
      crewSelectedId.value = newList[Math.max(0, newIndex - 1)]?.id || newList[0]?.id
    } else {
      crewSelectedId.value = null
    }
  }
}
function hasAgentOverrides(id: string) {
  const o = agentConfigs.value[id]
  if (!o) return false
  const d = crewDefaultConfigs.value[id] || {}
  return (o.goal !== undefined && o.goal !== d.goal) ||
         (o.backstory !== undefined && o.backstory !== d.backstory) ||
         (o.focus_areas !== undefined)
}
function resetAgentConfig(id: string) {
  delete agentConfigs.value[id]
}
function syncFocusAreas() {
  if (!crewSelectedId.value || !crewSelectedConfig.value) return
  crewSelectedConfig.value.focus_areas = crewFocusText.value.split(',').map(s => s.trim()).filter(Boolean)
}

watch(crewSelectedId, (id) => {
  if (!id) { crewFocusText.value = ''; return }
  const areas = agentConfigs.value[id]?.focus_areas ?? crewDefaultConfigs.value[id]?.focus_areas ?? []
  crewFocusText.value = areas.join(', ')
})

const newProjectName = ref('')
const newProjectDescription = ref('')
const newProjectIsPublic = ref(true)
const creating = ref(false)
const selectedTemplate = ref('')

// 新建讨论高级选项
const usePassword = ref(false)
const password = ref('')
const showPassword = ref(false)
const autoPauseInterval = ref(5)
const selectedAgents = ref<string[]>([])
const agentConfigs = ref<Record<string, any>>({})
const selectedStyle = ref('')
const customOverrides = ref<DiscussionStyleOverrides | null>(null)
const attachmentFile = ref<File | null>(null)
const newFocusArea = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

const discussionTemplates = [
  { label: '自由讨论（空模板）', value: '' },
  { label: '核心玩法讨论', value: '请从玩家体验、创新性、可行性三个角度讨论以下核心玩法设计：' },
  { label: '数值平衡评审', value: '请评审以下数值设计的平衡性，关注成长曲线、资源产出消耗比、付费点设计：' },
  { label: '美术风格探讨', value: '请从目标用户、技术可行性、市场差异化角度讨论以下美术风格方案：' },
  { label: '技术方案评估', value: '请从性能、开发成本、可维护性角度评估以下技术方案：' },
]

function onTemplateChange() {
  newDiscussionTopic.value = selectedTemplate.value
}

function onStyleSelect(styleId: string) {
  selectedStyle.value = styleId
  const style = discussionStylesFull.value.find(s => s.id === styleId)
  if (style?.overrides) {
    customOverrides.value = JSON.parse(JSON.stringify(style.overrides))
  } else {
    customOverrides.value = null
  }
}

function triggerFileInput() { fileInputRef.value?.click() }
function handleFileSelect(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) attachmentFile.value = f
}
function removeAttachment() { attachmentFile.value = null }

function addFocusArea() {
  if (newFocusArea.value.trim() && customOverrides.value) {
    customOverrides.value.focus_areas.push(newFocusArea.value.trim())
    newFocusArea.value = ''
  }
}
function removeFocusArea(idx: number) {
  customOverrides.value?.focus_areas.splice(idx, 1)
}
function handleFocusAreaKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') { e.preventDefault(); addFocusArea() }
}

function resetDiscussionForm() {
  newDiscussionTopic.value = ''
  newDiscussionProjectId.value = ''
  discussionGoal.value = ''
  selectedTemplate.value = ''
  usePassword.value = false
  password.value = ''
  autoPauseInterval.value = 5
  selectedAgents.value = []
  agentConfigs.value = {}
  selectedStyle.value = ''
  customOverrides.value = null
  attachmentFile.value = null
}

const projectItems = computed(() =>
  items.value.filter(item => item.type === 'project')
)

const emit = defineEmits<{
  (e: 'open-panel', section: string): void
}>()

onMounted(async () => {
  if (!userStore.isAuthenticated) {
    await userStore.init()
  }
  if (userStore.isAuthenticated) {
    await refresh()
    await loadStyles()
    if (discussionStylesFull.value.length > 0) {
      onStyleSelect(discussionStylesFull.value[0].id)
    }
  } else {
    showLoginModal.value = true
  }
})

watch(() => userStore.isAuthenticated, (val) => {
  if (!val) {
    items.value = []
    showLoginModal.value = true
  } else {
    refresh()
  }
})

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

// Access request modal state
const showAccessModal = ref(false)
const accessModalProject = ref<any>(null)
const accessRequesting = ref(false)
const accessRequestDone = ref(false)
const accessPendingRole = ref('')

function onCardClick(item: any) {
  if (item.type === 'discussion') {
    router.push(`/discussion/${item.id}`)
    return
  }
  if (!item.is_public && !item.user_role) {
    accessModalProject.value = item
    accessRequestDone.value = false
    accessPendingRole.value = ''
    showAccessModal.value = true
    return
  }
  if (!item.is_public && item.user_role && String(item.user_role).startsWith('pending_')) {
    accessModalProject.value = item
    accessRequestDone.value = true
    accessPendingRole.value = item.user_role.replace('pending_', '')
    showAccessModal.value = true
    return
  }
  router.push(`/project/${item.id}`)
}

async function requestAccess(role: string) {
  if (accessRequesting.value || !accessModalProject.value) return
  accessRequesting.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects/${accessModalProject.value.id}/access-request`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userStore.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ role }),
    })
    if (res.ok) {
      accessRequestDone.value = true
      accessPendingRole.value = role
      const itm = items.value.find(i => i.id === accessModalProject.value.id && i.type === 'project')
      if (itm) (itm as any).user_role = `pending_${role}`
    } else {
      const data = await res.json().catch(() => ({}))
      alert(data.detail || '申请失败')
    }
  } catch {
    alert('网络错误')
  } finally {
    accessRequesting.value = false
  }
}

async function doCreateDiscussion() {
  if (!newDiscussionTopic.value.trim() || creating.value) return
  creating.value = true
  try {
    let attachment = null
    if (attachmentFile.value) {
      const text = await attachmentFile.value.text()
      attachment = { filename: attachmentFile.value.name, content: text }
    }
    const data = await createDiscussion({
      topic: newDiscussionTopic.value.trim(),
      projectId: newDiscussionProjectId.value || undefined,
      briefing: discussionGoal.value.trim() || undefined,
      autoPauseInterval: autoPauseInterval.value,
      attachment,
      agents: selectedAgents.value.length > 0 ? selectedAgents.value : undefined,
      agentConfigs: Object.keys(agentConfigs.value).length > 0 ? agentConfigs.value : undefined,
      discussionStyle: selectedStyle.value || undefined,
      password: usePassword.value ? password.value : undefined,
      customOverrides: customOverrides.value,
    })
    showNewDiscussion.value = false
    resetDiscussionForm()
    router.push(`/discussion/${data.id}`)
  } catch (e) {
    alert('创建讨论失败')
  } finally {
    creating.value = false
  }
}

async function doCreateProject() {
  if (!newProjectName.value.trim() || creating.value) return
  creating.value = true
  try {
    const data = await createProject(newProjectName.value.trim(), newProjectDescription.value.trim() || undefined, newProjectIsPublic.value)
    showNewProject.value = false
    newProjectName.value = ''
    newProjectDescription.value = ''
    router.push(`/project/${data.id}`)
  } catch (e) {
    alert('创建项目失败')
  } finally {
    creating.value = false
  }
}

function onLoginSuccess() {
  showLoginModal.value = false
  refresh()
}

// Expose hall data for webmcp tools
const hallExpose = {
  get filteredItems() { return filteredItems.value },
  get items() { return items.value },
  get activeTab() { return activeTab.value },
  get searchQuery() { return searchQuery.value },
  showNewDiscussion,
  showNewProject,
  newDiscussionTopic,
  newDiscussionProjectId,
  discussionGoal,
  newProjectName,
  newProjectDescription,
  doCreateDiscussion,
  doCreateProject,
}
;(window as any).__bwHall = hallExpose
onUnmounted(() => { delete (window as any).__bwHall })
</script>

<template>
  <div class="hall">
    <header class="hall-header">
      <h1 class="hall-title">🎮 BW-Work</h1>
      <div class="hall-actions" v-if="userStore.isAuthenticated">
        <button class="btn btn-secondary" @click="showNewDiscussion = true">+ 新讨论</button>
        <button class="btn btn-secondary" @click="showNewProject = true">+ 新项目</button>
        <UserMenu @open-panel="(s: string) => emit('open-panel', s)" />
      </div>
      <div v-else class="hall-actions">
        <button class="btn btn-primary" @click="showLoginModal = true">登录</button>
      </div>
    </header>

    <div v-if="loading" class="hall-loading">加载中...</div>
    <div v-else-if="items.length === 0 && userStore.isAuthenticated" class="hall-empty">
      还没有任何讨论或项目，点击上方按钮创建吧！
    </div>
    <div v-else class="hall-body">
      <!-- Search + Tabs -->
      <div class="hall-toolbar">
        <input
          v-model="searchQuery"
          class="hall-search"
          placeholder="搜索标题或描述..."
        />
        <div class="hall-tabs">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="tab-btn"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >{{ tab.label }}</button>
        </div>
      </div>

      <div v-if="filteredItems.length === 0" class="hall-filter-empty">
        <div class="empty-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </div>
        <p class="empty-text">没有找到匹配的内容</p>
        <p class="empty-hint">试试其他关键词或切换分类</p>
      </div>
      <div v-else class="hall-grid">
        <div
          v-for="item in filteredItems"
          :key="`${item.type}-${item.id}`"
          class="hall-card"
          :class="[item.type === 'discussion' ? (itemStatus(item) === 'completed' ? 'card-border-gray' : 'card-border-blue') : (itemStatus(item) === 'completed' ? 'card-border-gray' : 'card-border-green')]"
          @click="onCardClick(item)"
        >
          <div class="card-header">
            <span class="card-icon">
              <svg v-if="item.type === 'discussion'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </span>
            <span class="card-type-badge" :class="item.type">{{ item.type === 'discussion' ? '讨论' : '项目' }}</span>
            <span
              v-if="statusMap[itemStatus(item)]"
              class="card-status-badge"
              :class="statusMap[itemStatus(item)].cls"
            >{{ statusMap[itemStatus(item)].label }}</span>
          </div>
          <h3 class="card-title">
            <span v-if="item.type==='project'" class="vis-icon">
              <svg v-if="item.is_public" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
              <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </span>{{ item.name }}
          </h3>
          <p class="card-desc" v-if="item.description">{{ item.description }}</p>
          <div class="card-footer">
            <span v-if="item.type === 'discussion' && item.extra?.owner_name" class="card-meta">
              {{ item.extra.owner_name }}
            </span>
            <span v-if="item.type === 'discussion' && item.extra?.participants_count != null" class="card-meta">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
              {{ item.extra.participants_count }} 人参与
            </span>
            <span v-if="item.type === 'discussion' && item.extra?.message_count != null" class="card-meta">
              {{ item.extra.message_count }} 条消息
            </span>
            <div v-if="item.type === 'project' && item.extra?.total_stages" class="card-progress">
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: `${((item.extra.completed_stages || 0) / item.extra.total_stages) * 100}%` }"
                />
              </div>
              <span class="progress-label">{{ item.extra.completed_stages || 0 }}/{{ item.extra.total_stages }} 阶段</span>
            </div>
            <span v-else-if="item.type === 'project' && item.extra?.stage_progress" class="card-progress">
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: `${(parseInt(item.extra.stage_progress) / parseInt(item.extra.stage_progress.split('/')[1] || '1')) * 100}%` }"
                />
              </div>
              <span class="progress-label">进度 {{ item.extra.stage_progress }}</span>
            </span>
            <span class="card-time">{{ formatTime(item.updated_at) }}</span>
          </div>
          <div v-if="item.type === 'discussion' && item.extra?.last_active_at" class="card-last-active">
            最后活跃 {{ formatTime(item.extra.last_active_at) }}
          </div>
        </div>
      </div>
    </div>

    <!-- New Discussion Dialog -->
    <Transition name="fade">
      <div v-if="showNewDiscussion" class="dialog-overlay" @click.self="showNewDiscussion = false">
        <div class="dialog dialog-compact">
          <h3 class="dialog-title">发起新讨论</h3>

          <div class="dialog-field">
            <label class="dialog-label">讨论话题 <span class="required">*</span></label>
            <textarea
              v-model="newDiscussionTopic"
              placeholder="输入讨论话题..."
              class="dialog-textarea"
              rows="2"
              @keydown.meta.enter="doCreateDiscussion"
              @keydown.ctrl.enter="doCreateDiscussion"
              autofocus
            />
          </div>

          <div class="dialog-field">
            <label class="dialog-label">讨论目标 / 期望产出</label>
            <textarea
              v-model="discussionGoal"
              placeholder="例如：输出一份核心玩法GDD文档，包含战斗系统、成长曲线、付费设计..."
              class="dialog-textarea"
              rows="2"
            />
          </div>

          <div class="dialog-row-3">
            <div class="dialog-field">
              <label class="dialog-label">关联项目</label>
              <select v-model="newDiscussionProjectId" class="dialog-input">
                <option value="">不关联</option>
                <option v-for="p in projectItems" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="dialog-field">
              <label class="dialog-label">讨论模板</label>
              <select v-model="selectedTemplate" class="dialog-input" @change="onTemplateChange">
                <option v-for="t in discussionTemplates" :key="t.label" :value="t.value">{{ t.label }}</option>
              </select>
            </div>
            <div class="dialog-field">
              <label class="dialog-label">暂停间隔</label>
              <div class="auto-pause-row">
                <input v-model.number="autoPauseInterval" type="number" min="0" max="50" class="dialog-input auto-pause-input" />
                <span class="hint-text">轮</span>
              </div>
            </div>
          </div>

          <!-- 讨论风格 -->
          <div v-if="discussionStylesFull.length > 0" class="dialog-field">
            <label class="dialog-label">讨论风格</label>
            <div class="style-pills">
              <button
                v-for="style in discussionStylesFull"
                :key="style.id"
                class="style-pill"
                :class="{ 'style-pill-active': selectedStyle === style.id }"
                @click="onStyleSelect(style.id)"
                :title="style.description"
              >{{ style.name }}</button>
            </div>
          </div>

          <!-- 密码 + 附件 + 高级 横排 -->
          <div class="dialog-inline-row">
            <label class="checkbox-label">
              <input type="checkbox" v-model="usePassword" />
              <span>讨论密码</span>
            </label>
            <input ref="fileInputRef" type="file" accept=".md" style="display:none" @change="handleFileSelect" />
            <div v-if="attachmentFile" class="attachment-chip">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
              {{ attachmentFile.name }} <button class="chip-remove" @click="removeAttachment">✕</button>
            </div>
            <button v-else class="btn-ghost-sm" @click="triggerFileInput">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
              参考文档
            </button>
            <button class="btn-ghost-sm" @click="showAdvancedModal = true; loadCrewDefaults()">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
              高级选项
            </button>
          </div>

          <!-- 密码输入（勾选后展开） -->
          <div v-if="usePassword" class="dialog-field">
            <div class="password-field">
              <input v-model="password" :type="showPassword ? 'text' : 'password'" class="dialog-input" placeholder="输入密码" />
              <button class="btn-icon" @click="showPassword = !showPassword" type="button">
                <svg v-if="showPassword" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </div>

          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showNewDiscussion = false">取消</button>
            <button class="btn btn-primary" @click="doCreateDiscussion" :disabled="creating">创建 (⌘+Enter)</button>
          </div>
        </div>
      </div>

</Transition>
    <Teleport to="body">
      <!-- 高级选项独立弹窗 -->
      <div v-if="showAdvancedModal" class="dialog-overlay" @click.self="showAdvancedModal = false" style="z-index:200">
        <div class="dialog dialog-compact">
          <h3 class="dialog-title">高级选项</h3>

          <!-- Tab 切换 -->
          <div class="adv-tabs">
            <button class="adv-tab" :class="{ 'adv-tab-active': advancedTab === 'base' }" @click="advancedTab = 'base'">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>
              基础
            </button>
            <button class="adv-tab" :class="{ 'adv-tab-active': advancedTab === 'crew' }" @click="advancedTab = 'crew'">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
              人员
            </button>
          </div>

          <!-- 基础 Tab -->
          <div v-if="advancedTab === 'base'" class="adv-tab-body">
            <div v-if="customOverrides" class="prompt-fields-compact">
              <div class="prompt-field">
                <label class="prompt-field-label">讨论目标</label>
                <textarea v-model="customOverrides.goal" class="prompt-field-input" placeholder="主策划的目标..." rows="2" />
              </div>
              <div class="prompt-field">
                <label class="prompt-field-label">背景设定</label>
                <textarea v-model="customOverrides.backstory" class="prompt-field-input" placeholder="主策划的背景设定..." rows="2" />
              </div>
              <div class="prompt-field">
                <label class="prompt-field-label">沟通风格</label>
                <textarea v-model="customOverrides.communication_style" class="prompt-field-input" placeholder="沟通风格描述..." rows="1" />
              </div>
              <div class="prompt-field">
                <label class="prompt-field-label">关注领域</label>
                <div class="focus-chips">
                  <span v-for="(area, idx) in customOverrides.focus_areas" :key="idx" class="focus-chip">
                    {{ area }} <button class="chip-remove" @click="removeFocusArea(idx)">✕</button>
                  </span>
                  <input v-model="newFocusArea" class="focus-add-input" placeholder="添加..." @keydown="handleFocusAreaKeydown" />
                </div>
              </div>
            </div>
            <div v-else class="hint-text" style="text-align:center;padding:16px">请先在主弹窗选择讨论风格</div>
          </div>

          <!-- 人员 Tab -->
          <div v-if="advancedTab === 'crew'" class="adv-tab-body">
            <div class="crew-panel">
              <!-- 参与人员列表 -->
              <div class="crew-list">
                <button
                  v-for="role in enabledAgentRoles"
                  :key="role.id"
                  class="crew-item"
                  :class="{ 'crew-item-active': crewSelectedId === role.id }"
                  @click="crewSelectedId = role.id"
                >
                  <span class="crew-emoji">{{ role.emoji }}</span>
                  <span class="crew-name">{{ role.name }}</span>
                  <span v-if="role.locked" class="crew-lock">必选</span>
                  <button v-else class="crew-remove" @click.stop="removeAgent(role.id)" title="移除">−</button>
                </button>
                <!-- 添加按钮 -->
                <div v-if="availableAgentRoles.length > 0" class="crew-add-wrap">
                  <button class="crew-add-btn" @click="showAgentPicker = !showAgentPicker">＋</button>
                  <div v-if="showAgentPicker" class="crew-picker">
                    <button
                      v-for="role in availableAgentRoles"
                      :key="role.id"
                      class="crew-picker-item"
                      @click="addAgent(role.id)"
                    >{{ role.emoji }} {{ role.name }}</button>
                  </div>
                </div>
              </div>

              <!-- 选中人员的提示词 -->
              <div v-if="crewSelectedId && crewSelectedConfig" class="crew-detail">
                <div class="crew-detail-header">
                  <span>{{ crewSelectedRole?.emoji }} {{ crewSelectedRole?.name }} 提示词</span>
                  <button v-if="hasAgentOverrides(crewSelectedId)" class="crew-reset" @click="resetAgentConfig(crewSelectedId)">↺ 恢复默认</button>
                </div>
                <div class="crew-fields">
                  <div class="crew-field">
                    <label>目标</label>
                    <textarea v-model="crewSelectedConfig.goal" rows="2" class="crew-input" />
                  </div>
                  <div class="crew-field">
                    <label>背景</label>
                    <textarea v-model="crewSelectedConfig.backstory" rows="2" class="crew-input" />
                  </div>
                  <div class="crew-field">
                    <label>关注领域</label>
                    <input v-model="crewFocusText" class="crew-input" placeholder="逗号分隔" @blur="syncFocusAreas" />
                  </div>
                </div>
              </div>
              <div v-else class="hint-text" style="text-align:center;padding:12px">点击人员查看提示词</div>
            </div>
          </div>

          <div class="dialog-actions">
            <button class="btn btn-primary" @click="showAdvancedModal = false">完成</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- New Project Dialog -->
    <Transition name="fade">
      <div v-if="showNewProject" class="dialog-overlay" @click.self="showNewProject = false">
        <div class="dialog dialog-enhanced">
          <h3 class="dialog-title">新建项目</h3>
          <div class="dialog-field">
            <label class="dialog-label">项目名称</label>
            <input
              v-model="newProjectName"
              placeholder="项目名称..."
              class="dialog-input"
              @keyup.enter="doCreateProject"
              autofocus
            />
          </div>
          <div class="dialog-field">
            <label class="dialog-label">项目描述（可选）</label>
            <textarea
              v-model="newProjectDescription"
              placeholder="简要描述项目内容..."
              class="dialog-textarea"
              rows="3"
            />
          </div>
          <div class="dialog-field">
            <label class="dialog-label">可见性</label>
            <div class="visibility-pills">
              <button class="vis-pill" :class="{ 'vis-pill-active': newProjectIsPublic }" @click="newProjectIsPublic = true">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                公开
              </button>
              <button class="vis-pill" :class="{ 'vis-pill-active': !newProjectIsPublic }" @click="newProjectIsPublic = false">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                私密
              </button>
            </div>
            <span class="hint-text">{{ newProjectIsPublic ? '所有用户可查看，编辑需申请权限' : '仅成员可见，需申请查看或编辑权限' }}</span>
          </div>
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showNewProject = false">取消</button>
            <button class="btn btn-primary" @click="doCreateProject" :disabled="creating">创建</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Access Request Modal -->
    <Transition name="fade">
      <div v-if="showAccessModal" class="dialog-overlay" @click.self="showAccessModal = false">
        <div class="dialog dialog-enhanced">
          <h3 class="dialog-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            这是私密项目
          </h3>
          <div v-if="!accessRequestDone" class="access-modal-body">
            <p class="access-project-name">{{ accessModalProject?.name }}</p>
            <p class="access-hint">你没有访问权限，可以申请加入</p>
            <div class="access-actions">
              <button class="btn btn-primary" @click="requestAccess('viewer')" :disabled="accessRequesting">申请查看权限</button>
              <button class="btn btn-primary" @click="requestAccess('editor')" :disabled="accessRequesting">申请编辑权限</button>
              <button class="btn btn-secondary" @click="showAccessModal = false">取消</button>
            </div>
          </div>
          <div v-else class="access-modal-body">
            <p class="access-done-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </p>
            <p class="access-done-text">已提交申请，等待管理员审批</p>
            <p class="access-done-hint">申请角色：{{ accessPendingRole === 'viewer' ? '查看者' : '编辑者' }}</p>
            <div class="access-actions">
              <button class="btn btn-secondary" @click="showAccessModal = false">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Login Modal -->
    <LoginModal v-if="showLoginModal" @close="showLoginModal = false" @success="onLoginSuccess" />
  </div>
</template>

<style scoped>
/* === Base === */
.hall {
  min-height: 100vh;
  background: #FFFBF5;
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* === Top Bar === */
.hall-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #FFFFFF;
  box-shadow: 0 1px 4px #0000000A;
  height: 56px;
  position: sticky;
  top: 0;
  z-index: 10;
  gap: 16px;
}
.hall-title {
  font-family: Outfit, sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: #7C3AED;
  letter-spacing: -0.5px;
  margin: 0;
}
.hall-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* === Main Body === */
.hall-body { padding: 0; }

/* === Filter Toolbar === */
.hall-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 52px;
  padding: 0 24px;
  background: #FFFFFF;
  flex-wrap: nowrap;
}
.hall-search {
  flex: 0 0 360px;
  padding: 0 14px;
  border: none;
  border-radius: 100px;
  font-size: 14px;
  height: 36px;
  outline: none;
  background: #F5F3F0;
  color: #18181B;
  font-family: inherit;
  transition: box-shadow 0.15s;
}
.hall-search::placeholder { color: #9C9B99; }
.hall-search:focus { box-shadow: 0 0 0 2px #7C3AED40; }

/* === Filter Tabs === */
.hall-tabs { display: flex; gap: 12px; flex-wrap: wrap; }
.tab-btn {
  padding: 6px 16px;
  height: 32px;
  border-radius: 100px;
  font-family: Outfit, sans-serif;
  font-size: 13px;
  font-weight: 500;
  border: none;
  background: #F0EDE8;
  color: #6D6C6A;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  display: flex;
  align-items: center;
}
.tab-btn:hover { background: #E8E4DE; }
.tab-btn.active { background: #7C3AED; color: #FFFFFF; font-weight: 600; }

/* === Status Badges === */
.card-status-badge {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 100px;
  font-weight: 500;
  margin-left: auto;
}
.status-active    { background: #EDE9FE; color: #7C3AED; }
.status-waiting   { background: #FEF3C7; color: #92400E; }
.status-completed { background: #D1FAE5; color: #16A34A; }
.status-archived  { background: #F4F4F5; color: #71717A; }

/* === Loading / Empty === */
.hall-loading, .hall-empty {
  text-align: center;
  padding: 60px 20px;
  color: #9CA3AF;
  font-size: 15px;
}

/* === Grid === */
.hall-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  padding: 24px;
}

/* === Cards === */
.hall-card {
  background: #FFFFFF;
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 2px 12px #0000000D;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
}
.hall-card:hover {
  box-shadow: 0 8px 24px #00000018;
  transform: translateY(-2px);
}
.card-border-blue  { border-left: 3px solid #7C3AED; }
.card-border-green { border-left: 3px solid #22C55E; }
.card-border-gray  { border-left: 3px solid #D1D5DB; }

.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.card-icon { display: inline-flex; align-items: center; color: #7C3AED; }
.card-type-badge {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 100px;
  font-weight: 500;
}
.card-type-badge.discussion { background: #7C3AED; color: #FFFFFF; }
.card-type-badge.project    { background: #22C55E; color: #FFFFFF; }

.card-title {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 16px;
  font-weight: 700;
  color: #18181B;
  margin: 0 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vis-icon { display: inline-flex; align-items: center; color: #6B7280; flex-shrink: 0; }
.card-desc {
  font-size: 13px;
  color: #6B7280;
  margin: 0 0 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-footer { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.card-meta  { display: inline-flex; align-items: center; gap: 3px; font-size: 12px; color: #9CA3AF; }
.card-time  { font-size: 12px; color: #9CA3AF; margin-left: auto; }
.card-last-active {
  font-size: 11px;
  color: #A1A1AA;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #F0EDE8;
}

/* === Progress === */
.card-progress { display: flex; align-items: center; gap: 8px; flex: 1; }
.progress-bar { flex: 1; height: 6px; background: #F0EDE8; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: #7C3AED; border-radius: 3px; transition: width 0.3s ease; }
.progress-label { font-size: 11px; color: #6B7280; white-space: nowrap; }

/* === Filter Empty === */
.hall-filter-empty { text-align: center; padding: 60px 20px; }
.empty-icon  { display: flex; justify-content: center; align-items: center; margin-bottom: 12px; color: #9CA3AF; }
.empty-text  { font-size: 16px; color: #6B7280; margin: 0 0 6px; font-weight: 500; }
.empty-hint  { font-size: 13px; color: #9CA3AF; margin: 0; }

/* === Buttons === */
.btn {
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  font-family: inherit;
  transition: background 0.15s;
}
.btn-primary { background: #7C3AED; color: #FFFFFF; }
.btn-primary:hover   { background: #6D28D9; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  background: transparent;
  color: #374151;
  border: 1px solid #D1D5DB;
}
.btn-secondary:hover { background: #F5F3F0; }

/* === Dialog Overlay === */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: #00000066;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.dialog {
  background: #FFFFFF;
  border-radius: 16px;
  padding: 24px;
  width: min(400px, 90vw);
  box-shadow: 0 8px 32px -4px #00000020;
}
.dialog h3 {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 600;
  color: #18181B;
  font-family: Geist, Inter, sans-serif;
}
.dialog-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
  font-family: inherit;
  background: #FFFFFF;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.dialog-input:focus { border-color: #7C3AED; box-shadow: 0 0 0 3px #7C3AED20; }
.dialog-enhanced {
  border-radius: 16px;
  padding: 28px;
  width: min(440px, 90vw);
  box-shadow: 0 8px 32px -4px #00000020;
}
.dialog-title {
  margin: 0 0 20px;
  font-size: 18px;
  font-weight: 600;
  color: #18181B;
  font-family: Geist, Inter, sans-serif;
}
.dialog-field { margin-bottom: 14px; }
.dialog-label { display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px; }
.dialog-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
  background: #FFFFFF;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.dialog-textarea:focus { border-color: #7C3AED; box-shadow: 0 0 0 3px #7C3AED20; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }

/* === Transitions === */
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* === Responsive === */
@media (max-width: 768px) {
  .hall-header { padding: 0 16px; }
  .hall-title  { font-size: 17px; }
  .hall-actions { gap: 8px; }
  .hall-actions .btn { padding: 5px 10px; font-size: 13px; }
  .hall-toolbar { height: auto; flex-wrap: wrap; padding: 10px 16px; gap: 10px; }
  .hall-search { flex: none; width: 100%; }
  .hall-tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    padding-bottom: 2px;
  }
  .hall-tabs::-webkit-scrollbar { display: none; }
  .tab-btn { flex-shrink: 0; }
  .hall-grid { grid-template-columns: 1fr; padding: 16px; }
  .card-title { font-size: 15px; }
  .dialog-enhanced { width: calc(100vw - 32px); padding: 20px; }
  .dialog-title { font-size: 17px; }
}

/* === 新建讨论弹窗样式 === */
.dialog-compact { max-width: 560px; width: calc(100vw - 48px); }
.dialog-row-3 { display: grid; grid-template-columns: 1fr 1fr 120px; gap: 12px; }
.required { color: #EF4444; }
.dialog-inline-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.btn-ghost-sm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 12px;
  color: #6B7280;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.15s, color 0.15s;
}
.btn-ghost-sm:hover { border-color: #7C3AED; color: #7C3AED; }
.attachment-chip { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; background: #EDE9FE; border-radius: 8px; font-size: 12px; color: #7C3AED; }

/* === Crew Panel === */
.crew-panel { display: flex; flex-direction: column; gap: 10px; }
.crew-list { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.crew-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 100px;
  font-size: 13px;
  border: 1.5px solid #D1D5DB;
  background: #FFFFFF;
  cursor: pointer;
  transition: border-color 0.15s;
}
.crew-item:hover { border-color: #C4B5FD; }
.crew-item-active { border-color: #7C3AED; background: #EDE9FE; }
.crew-emoji { font-size: 14px; }
.crew-name { font-weight: 500; color: #374151; }
.crew-lock { font-size: 10px; padding: 0 4px; background: #F0EDE8; color: #6B7280; border-radius: 3px; }
.crew-remove { background: none; border: none; color: #D1D5DB; font-size: 16px; cursor: pointer; padding: 0 2px; line-height: 1; }
.crew-remove:hover { color: #EF4444; }
.crew-add-wrap { position: relative; }
.crew-add-btn {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1.5px dashed #D1D5DB;
  background: #FFFFFF;
  font-size: 16px;
  color: #9CA3AF;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s, color 0.15s;
}
.crew-add-btn:hover { border-color: #7C3AED; color: #7C3AED; }
.crew-picker {
  position: absolute;
  top: 36px;
  left: 0;
  background: #FFFFFF;
  border: 1px solid #F0EDE8;
  border-radius: 12px;
  box-shadow: 0 8px 24px #00000018;
  z-index: 10;
  min-width: 140px;
}
.crew-picker-item { display: block; width: 100%; text-align: left; padding: 9px 16px; font-size: 13px; border: none; background: none; cursor: pointer; color: #2D2D2D; }
.crew-picker-item:hover { background: #FFFBF5; }
.crew-detail { border: 1px solid #F0EDE8; border-radius: 10px; padding: 10px; background: #FAFAFA; }
.crew-detail-header { display: flex; justify-content: space-between; align-items: center; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 8px; }
.crew-reset { font-size: 12px; color: #9CA3AF; background: none; border: none; cursor: pointer; }
.crew-reset:hover { color: #7C3AED; }
.crew-fields { display: flex; flex-direction: column; gap: 8px; }
.crew-field label { font-size: 11px; font-weight: 500; color: #6B7280; display: block; margin-bottom: 2px; }
.crew-input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid #D1D5DB;
  border-radius: 6px;
  font-size: 12px;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.15s;
  background: #FFFFFF;
}
.crew-input:focus { outline: none; border-color: #7C3AED; }

/* 高级选项 Tab */
.adv-tabs { display: flex; gap: 0; border-bottom: 2px solid #F0EDE8; margin-bottom: 12px; }
.adv-tab {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 8px 0;
  background: none;
  border: none;
  font-size: 13px;
  font-weight: 500;
  color: #9CA3AF;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s;
}
.adv-tab:hover { color: #6B7280; }
.adv-tab-active { color: #7C3AED; border-bottom-color: #7C3AED; }
.adv-tab-body { min-height: 200px; }
.prompt-preview-section { background: #FAFAFA; border-radius: 10px; padding: 12px; }
.prompt-preview-title { font-size: 12px; font-weight: 600; color: #6B7280; margin-bottom: 8px; }
.prompt-fields-compact { display: flex; flex-direction: column; gap: 8px; }
.prompt-field { display: flex; flex-direction: column; gap: 4px; }
.prompt-field-label { font-size: 12px; font-weight: 600; color: #374151; }
.prompt-field-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  font-size: 12px;
  resize: vertical;
  min-height: 44px;
  font-family: inherit;
  background: #FFFFFF;
  line-height: 1.5;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.prompt-field-input:focus { outline: none; border-color: #7C3AED; box-shadow: 0 0 0 2px #7C3AED20; }

.focus-chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.focus-chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; background: #EDE9FE; color: #7C3AED; border-radius: 100px; font-size: 12px; }
.chip-remove { background: none; border: none; color: #C4B5FD; cursor: pointer; font-size: 12px; padding: 0 2px; }
.chip-remove:hover { color: #EF4444; }
.focus-add-input { border: 1px dashed #D1D5DB; border-radius: 8px; padding: 3px 8px; font-size: 12px; width: 120px; outline: none; background: #FFFFFF; }
.focus-add-input:focus { border-color: #7C3AED; }

.style-pills { display: flex; flex-wrap: wrap; gap: 6px; }
.style-pill { padding: 5px 12px; border-radius: 100px; border: 1px solid #D1D5DB; background: #FFFFFF; font-size: 12px; cursor: pointer; transition: border-color 0.15s, color 0.15s; color: #374151; }
.style-pill:hover { border-color: #7C3AED; color: #7C3AED; }
.style-pill-active { background: #7C3AED; color: #FFFFFF; border-color: #7C3AED; }

.checkbox-label { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; cursor: pointer; }
.password-field { display: flex; gap: 8px; margin-top: 6px; }
.btn-icon { background: none; border: none; cursor: pointer; font-size: 16px; padding: 4px; }
.btn-ghost {
  background: none;
  border: 1px dashed #D1D5DB;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: #6B7280;
  cursor: pointer;
  width: 100%;
  text-align: left;
  transition: border-color 0.15s, color 0.15s;
}
.btn-ghost:hover { border-color: #7C3AED; color: #7C3AED; }
.attachment-info { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #EDE9FE; border-radius: 8px; font-size: 13px; color: #7C3AED; }
.attachment-remove { background: none; border: none; color: #C4B5FD; cursor: pointer; font-size: 14px; margin-left: auto; }
.attachment-remove:hover { color: #EF4444; }
.auto-pause-row { display: flex; align-items: center; gap: 8px; }
.auto-pause-input { width: 70px !important; }

.visibility-pills { display: flex; gap: 8px; }
.vis-pill { display: inline-flex; align-items: center; gap: 5px; padding: 6px 16px; border-radius: 100px; border: 1.5px solid #D1D5DB; background: #FFFFFF; font-size: 13px; cursor: pointer; transition: border-color 0.15s, background 0.15s; }
.vis-pill:hover { border-color: #C4B5FD; }
.vis-pill-active { border-color: #7C3AED; background: #EDE9FE; color: #7C3AED; font-weight: 500; }
.hint-text { font-size: 12px; color: #9CA3AF; }

/* Access Request Modal */
.access-modal-body { text-align: center; padding: 8px 0; }
.access-project-name { font-size: 18px; font-weight: 600; color: #18181B; margin: 0 0 8px; }
.access-hint { font-size: 14px; color: #6B7280; margin: 0 0 20px; }
.access-actions { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
.access-done-icon { display: flex; justify-content: center; margin: 0 0 8px; }
.access-done-text { font-size: 16px; font-weight: 500; color: #18181B; margin: 0 0 4px; }
.access-done-hint { font-size: 13px; color: #9CA3AF; margin: 0 0 16px; }

@media (max-width: 768px) {
  .dialog-wide { max-width: calc(100vw - 32px); }
  .dialog-two-col { flex-direction: column; }
  .dialog-col-right { margin-top: 12px; }
}
</style>
