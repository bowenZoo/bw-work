<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectDetail } from '@/composables/useProjectDetail'
import { useUserStore } from '@/stores/user'
import LetterAvatar from '@/components/common/LetterAvatar.vue'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const projectId = () => route.params.projectId as string
const { project, stages, loading, refresh, completeStage, createDocument } = useProjectDetail(projectId)

const showNewDoc = ref<string | null>(null)
const newDocTitle = ref('')
const creating = ref(false)
const adoptingId = ref<string | null>(null)
const showAdoptDialog = ref<any>(null) // output object
const adoptAction = ref<'new_doc' | 'merge'>('new_doc')
const adoptTitle = ref('')
const adoptTargetDoc = ref('')
const collapsedStages = ref<Set<string>>(new Set())
const previewOutput = ref<any>(null)
const showNewDiscDialog = ref<string | null>(null)
const newDiscTopic = ref('')
const creatingDisc = ref(false)

// Stage → pre-configured agents mapping
const STAGE_AGENTS: Record<string, string[]> = {
  'concept':        ['creative_director', 'lead_planner', 'market_director'],
  'core-gameplay':  ['lead_planner', 'system_designer', 'number_designer'],
  'art-style':      ['lead_planner', 'visual_concept', 'system_designer'],
  'tech-prototype': ['lead_planner', 'system_designer'],
  'system-design':  ['system_designer', 'number_designer', 'lead_planner'],
  'numbers':        ['number_designer', 'system_designer', 'lead_planner'],
  'ui-ux':          ['lead_planner', 'visual_concept', 'system_designer'],
  'level-content':  ['lead_planner', 'system_designer', 'player_advocate'],
  'art-assets':     ['visual_concept', 'lead_planner'],
  'default':        ['lead_planner', 'system_designer', 'operations_analyst'],
}

const AGENT_LABELS: Record<string, string> = {
  'lead_planner':       '主策划',
  'system_designer':    '系统策划',
  'number_designer':    '数值策划',
  'operations_analyst': '市场运营',
  'player_advocate':    '玩家代言人',
  'visual_concept':     '视觉概念设计师',
  'creative_director':  '创意总监',
  'market_director':    '市场总监',
}

function stageAgents(stage: any): string[] {
  return STAGE_AGENTS[stage.template_id] || STAGE_AGENTS['default']
}

// Member management

const showAccessModal = ref(false)

function goBackToHall() {
  showAccessModal.value = false
  router.push('/')
}

// Watch for access_denied
watch(() => project.value?.access_denied, (denied) => {
  if (denied) showAccessModal.value = true
}, { immediate: true })

async function requestAccess(role: string) {
  const base = import.meta.env.VITE_API_BASE || ''
  try {
    const res = await fetch(`${base}/api/projects/${project.value?.id}/access-request`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${userStore.accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    })
    if (res.ok) {
      alert('申请已发送，等待项目管理员审批')
    } else {
      const d = await res.json()
      alert(d.detail || '申请失败')
    }
  } catch (e) {
    alert('网络错误')
  }
}

const canEdit = computed(() => {
  const role = project.value?.user_role
  return role === 'admin' || role === 'editor' || userStore.role === 'superadmin'
})

const isAdmin = computed(() => {
  const role = project.value?.user_role
  return role === 'admin' || userStore.user?.role === 'superadmin'
})

const pendingRequests = ref<any[]>([])

async function loadPendingRequests() {
  if (!isAdmin.value) return
  const base = import.meta.env.VITE_API_BASE || ''
  try {
    const res = await fetch(`${base}/api/projects/${project.value?.id}/access-requests`, {
      headers: { Authorization: `Bearer ${userStore.accessToken}` }
    })
    if (res.ok) pendingRequests.value = await res.json()
  } catch {}
}

async function approveRequest(userId: number) {
  const base = import.meta.env.VITE_API_BASE || ''
  const res = await fetch(`${base}/api/projects/${project.value?.id}/access-requests/${userId}/approve`, {
    method: 'POST', headers: { Authorization: `Bearer ${userStore.accessToken}` }
  })
  if (res.ok) {
    pendingRequests.value = pendingRequests.value.filter((r: any) => r.user_id !== userId)
  }
}

async function rejectRequest(userId: number) {
  const base = import.meta.env.VITE_API_BASE || ''
  const res = await fetch(`${base}/api/projects/${project.value?.id}/access-requests/${userId}/reject`, {
    method: 'POST', headers: { Authorization: `Bearer ${userStore.accessToken}` }
  })
  if (res.ok) {
    pendingRequests.value = pendingRequests.value.filter((r: any) => r.user_id !== userId)
  }
}

const showDeleteConfirm = ref(false)
const deleting = ref(false)

async function deleteProject() {
  if (deleting.value) return
  deleting.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects/${projectId()}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    if (!res.ok) {
      const e = await res.json()
      alert(e.detail || '删除失败')
      return
    }
    router.push('/')
  } catch {
    alert('网络错误')
  } finally {
    deleting.value = false
    showDeleteConfirm.value = false
  }
}

const showMemberDialog = ref(false)
const members = ref<any[]>([])
const loadingMembers = ref(false)
const inviteUsername = ref('')
const inviteRole = ref('editor')
const inviting = ref(false)

async function fetchMembers() {
  loadingMembers.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects/${projectId()}/members`, {
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    if (res.ok) members.value = await res.json()
  } finally {
    loadingMembers.value = false
  }
}

async function inviteMember() {
  if (!inviteUsername.value.trim() || inviting.value) return
  inviting.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects/${projectId()}/members`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${userStore.accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: inviteUsername.value.trim(), role: inviteRole.value }),
    })
    if (!res.ok) { const e = await res.json(); alert(e.detail || '邀请失败'); return }
    inviteUsername.value = ''
    inviteRole.value = 'editor'
    await fetchMembers()
  } finally {
    inviting.value = false
  }
}

async function removeMember(memberId: string) {
  if (!confirm('确认移除该成员？')) return
  const base = import.meta.env.VITE_API_BASE || ''
  const res = await fetch(`${base}/api/projects/${projectId()}/members/${memberId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${userStore.accessToken}` },
  })
  if (!res.ok) { alert('移除失败'); return }
  await fetchMembers()
}

function openMemberDialog() {
  showMemberDialog.value = true
  fetchMembers()
}

// Stage management
const showStageDialog = ref(false)
const editingStages = ref<any[]>([])
const newStageName = ref('')
const savingStage = ref(false)

function openStageDialog() {
  editingStages.value = stages.value.map((s: any) => ({ ...s, editName: s.name }))
  showStageDialog.value = true
}

async function saveStageRename(stage: any) {
  if (!stage.editName.trim() || stage.editName === stage.name) return
  savingStage.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects/${projectId()}/stages/${stage.id}`, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${userStore.accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: stage.editName.trim() }),
    })
    if (!res.ok) { alert('保存失败'); return }
    await refresh()
    editingStages.value = stages.value.map((s: any) => ({ ...s, editName: s.name }))
  } finally {
    savingStage.value = false
  }
}

async function addCustomStage() {
  if (!newStageName.value.trim()) return
  savingStage.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const slug = newStageName.value.trim().toLowerCase().replace(/\s+/g, '_')
    const order = editingStages.value.length
    const res = await fetch(`${base}/api/projects/${projectId()}/stages`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${userStore.accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newStageName.value.trim(), slug, order }),
    })
    if (!res.ok) { alert('添加失败'); return }
    newStageName.value = ''
    await refresh()
    editingStages.value = stages.value.map((s: any) => ({ ...s, editName: s.name }))
  } finally {
    savingStage.value = false
  }
}

async function deleteCustomStage(stageId: string) {
  if (!confirm('确认删除该自定义阶段？')) return
  savingStage.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects/${projectId()}/stages/${stageId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    if (!res.ok) { alert('删除失败'); return }
    await refresh()
    editingStages.value = stages.value.map((s: any) => ({ ...s, editName: s.name }))
  } finally {
    savingStage.value = false
  }
}

const isOwner = computed(() => project.value?.owner_id === userStore.user?.id)

async function doAdopt() {
  if (!showAdoptDialog.value || adoptingId.value) return
  adoptingId.value = showAdoptDialog.value.id
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const body: any = { action: adoptAction.value }
    if (adoptAction.value === 'new_doc') body.title = adoptTitle.value || showAdoptDialog.value.title
    if (adoptAction.value === 'merge') body.document_id = adoptTargetDoc.value
    const res = await fetch(`${base}/api/discussions/${showAdoptDialog.value.discussion_id}/outputs/${showAdoptDialog.value.id}/adopt`, {
      method: 'POST', headers: { Authorization: `Bearer ${userStore.accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!res.ok) { const e = await res.json(); alert(e.detail || '采纳失败'); return }
    showAdoptDialog.value = null
    refresh()
  } finally { adoptingId.value = null }
}

function openAdopt(output: any, stageDocs: any[]) {
  showAdoptDialog.value = { ...output, stageDocs }
  adoptAction.value = 'new_doc'
  adoptTitle.value = output.title
  adoptTargetDoc.value = stageDocs.length ? stageDocs[0].id : ''
}

onMounted(async () => {
  await refresh()
  // Check access denied after load
  if (project.value?.access_denied) {
    showAccessModal.value = true
  }
  await loadPendingRequests()
  // Default: locked stages are collapsed
  stages.value.forEach((s: any) => {
    if (s.status === 'locked') collapsedStages.value.add(s.id)
  })
})

function toggleStage(stageId: string) {
  if (collapsedStages.value.has(stageId)) {
    collapsedStages.value.delete(stageId)
  } else {
    collapsedStages.value.add(stageId)
  }
}

function isStageCollapsed(stageId: string) {
  return collapsedStages.value.has(stageId)
}

// Pipeline helpers
function stageBarColor(status: string): string {
  return status === 'active' || status === 'completed' ? '#7C3AED' : '#D4D4D8'
}

function stageItemCount(stage: any): number {
  return (stage.discussions?.length || 0) + (stage.documents?.length || 0) + (stage.outputs?.length || 0)
}

function discStatusColor(status: string): string {
  if (status === 'running') return '#22C55E'
  if (status === 'waiting_decision') return '#7C3AED'
  if (status === 'completed') return '#9CA3AF'
  return '#9CA3AF'
}

function discStatusText(status: string): string {
  if (status === 'running') return 'AI 运行中'
  if (status === 'waiting_decision') return '等待决策'
  if (status === 'completed') return '已完成'
  if (status === 'paused') return '已暂停'
  if (status === 'pending' || status === 'queued') return '等待中'
  if (status === 'failed') return '异常'
  return status || '未知'
}

const projectStatusText = computed(() => {
  if (!stages.value.length) return '未开始'
  if (stages.value.some((s: any) => s.status === 'active')) return '进行中'
  if (stages.value.every((s: any) => s.status === 'completed')) return '已完成'
  return '未开始'
})

const projectStatusActive = computed(() =>
  stages.value.some((s: any) => s.status === 'active')
)

const hasAdoptedOutputs = computed(() =>
  stages.value.some((s: any) => (s.outputs || []).some((o: any) => o.status === 'adopted'))
)

function statusBadge(status: string) {
  if (status === 'completed') return { text: '已完成', cls: 'completed' }
  if (status === 'active') return { text: '进行中', cls: 'active' }
  return { text: '未解锁', cls: 'locked' }
}

async function doCompleteStage(stageId: string) {
  if (!confirm('确认标记此阶段为已完成？')) return
  try {
    await completeStage(stageId)
  } catch (e) {
    alert('标记完成失败')
  }
}

async function doCreateDocument(stageId: string) {
  if (!newDocTitle.value.trim() || creating.value) return
  creating.value = true
  try {
    const doc = await createDocument(stageId, newDocTitle.value.trim())
    showNewDoc.value = null
    newDocTitle.value = ''
    router.push(`/project/${projectId()}/doc/${doc.id}`)
  } catch (e) {
    alert('创建文档失败')
  } finally {
    creating.value = false
  }
}

function goDiscussion(id: string) {
  router.push(`/discussion/${id}`)
}

function goDocument(docId: string) {
  router.push(`/project/${projectId()}/doc/${docId}`)
}

function formatTime(dt: string) {
  if (!dt) return ''
  const d = new Date(dt)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function createStageDiscussion(stageId: string) {
  if (!newDiscTopic.value.trim() || creatingDisc.value) return
  creatingDisc.value = true
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    // find the stage to get template_id
    const stage = stages.value.find((s: any) => s.id === stageId)
    const agents = stageAgents(stage || {})
    const res = await fetch(`${base}/api/discussions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userStore.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        topic: newDiscTopic.value.trim(),
        project_id: projectId(),
        target_type: 'stage',
        target_id: stageId,
        agents,
        rounds: 50,
        auto_pause_interval: 1,
      }),
    })
    if (!res.ok) throw new Error('Failed')
    const data = await res.json()
    showNewDiscDialog.value = null
    newDiscTopic.value = ''
    router.push(`/discussion/${data.id}`)
  } catch {
    alert('创建讨论失败')
  } finally {
    creatingDisc.value = false
  }
}
</script>

<template>
  <div class="project-detail">

    <!-- Breadcrumb -->
    <div class="breadcrumb">
      <span class="bc-link" @click="router.push('/')">大厅</span>
      <span class="bc-sep">/</span>
      <span class="bc-current">{{ project?.name || '加载中...' }}</span>
    </div>

    <!-- Header -->
    <div class="pd-header">
      <div class="header-left">
        <div class="header-title">{{ project?.name || '加载中...' }}</div>
        <div v-if="project?.description" class="header-desc">{{ project.description }}</div>
      </div>
      <div class="header-right">
        <div class="status-pill" :class="projectStatusActive ? 'status-pill-active' : 'status-pill-idle'">
          <div class="status-dot" :class="projectStatusActive ? 'status-dot-active' : 'status-dot-idle'"></div>
          {{ projectStatusText }}
        </div>
        <button v-if="canEdit" class="gear-btn" @click="openMemberDialog" title="成员管理">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        </button>
        <button v-if="isOwner" class="gear-btn" @click="openStageDialog" title="管理阶段">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </button>
        <button v-if="userStore.role === 'superadmin'" class="gear-btn gear-btn-danger" @click="showDeleteConfirm = true" title="删除项目">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
        </button>
      </div>
    </div>

    <!-- Pending requests bar -->
    <div v-if="isAdmin && pendingRequests.length > 0" class="pending-bar">
      <span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline;vertical-align:middle"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.63 3.4 2 2 0 0 1 3.6 1.21h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.79a16 16 0 0 0 6.29 6.29l.95-.95a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
        {{ pendingRequests.length }} 个权限申请待审批
      </span>
      <div v-for="req in pendingRequests" :key="req.user_id" class="pending-item">
        <span>{{ req.display_name || req.username }} 申请 <strong>{{ req.requested_role === 'editor' ? '编辑' : '查看' }}</strong> 权限</span>
        <button class="btn btn-sm btn-primary" @click="approveRequest(req.user_id)">✓ 批准</button>
        <button class="btn btn-sm btn-danger" @click="rejectRequest(req.user_id)">✗ 拒绝</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="pd-loading">加载中...</div>

    <!-- Pipeline -->
    <div v-else class="pipeline">
      <div v-for="stage in stages" :key="stage.id" class="pipeline-col">
        <div class="col-header">
          <div class="col-bar" :style="{ background: stageBarColor(stage.status) }"></div>
          <div class="col-title-row">
            <span class="col-name">{{ stage.name }}</span>
            <span class="col-count">{{ stageItemCount(stage) }}</span>
          </div>
        </div>
        <div class="col-body">
          <!-- Discussion cards -->
          <div
            v-for="disc in stage.discussions"
            :key="'disc-' + disc.id"
            class="item-card"
            @click="goDiscussion(disc.id)"
          >
            <div class="card-header-row">
              <span class="card-icon">💬</span>
              <span class="card-title">{{ disc.topic }}</span>
            </div>
            <div class="card-meta">{{ disc.owner_name }} · {{ disc.message_count }} 条</div>
            <div class="card-footer">
              <div class="status-dot-sm" :style="{ background: discStatusColor(disc.status) }"></div>
              <span class="card-status-txt">{{ discStatusText(disc.status) }}</span>
            </div>
          </div>

          <!-- Document cards -->
          <div
            v-for="doc in stage.documents"
            :key="'doc-' + doc.id"
            class="item-card"
            @click="goDocument(doc.id)"
          >
            <div class="card-header-row">
              <span class="card-icon">📄</span>
              <span class="card-title">{{ doc.title }}</span>
            </div>
            <div class="card-meta">v{{ doc.current_version }} · {{ formatTime(doc.updated_at) }}</div>
          </div>

          <!-- Output cards -->
          <div
            v-for="output in (stage.outputs || [])"
            :key="'out-' + output.id"
            class="item-card item-card-output"
            @click="previewOutput = output"
          >
            <div class="card-header-row">
              <span class="card-icon">📝</span>
              <span class="card-title">{{ output.title }}</span>
              <span v-if="output.status === 'adopted'" class="adopted-badge">已采纳</span>
            </div>
            <div class="card-meta">{{ output.status === 'adopted' ? '讨论产出' : '待采纳' }}</div>
          </div>

          <!-- Empty state -->
          <div
            v-if="!stage.discussions.length && !stage.documents.length && !(stage.outputs || []).length"
            class="col-empty"
          >
            <span class="col-empty-txt">{{ stage.status === 'locked' ? '未解锁' : '暂无内容' }}</span>
          </div>

          <!-- New buttons -->
          <template v-if="canEdit && stage.status !== 'locked'">
            <button class="new-btn" @click="showNewDiscDialog = stage.id">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              新讨论
            </button>
            <button class="new-btn" @click="showNewDoc = stage.id">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              新文档
            </button>
            <button
              v-if="stage.status === 'active'"
              class="new-btn new-btn-complete"
              @click="doCompleteStage(stage.id)"
            >
              ✓ 标记完成
            </button>
          </template>
        </div>
      </div>
    </div>

    <!-- Bottom Bar -->
    <div class="bottom-bar">
      <span class="bottom-label">讨论成果</span>
      <template v-for="stage in stages" :key="stage.id">
        <div
          v-for="output in (stage.outputs || []).filter((o: any) => o.status === 'adopted')"
          :key="output.id"
          class="result-card"
          @click="previewOutput = output"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          <span class="result-text">{{ output.title }}</span>
          <span class="result-pill">已采纳</span>
        </div>
      </template>
      <span v-if="!hasAdoptedOutputs" class="no-results">暂无采纳成果</span>
    </div>

    <!-- New Document Dialog -->
    <Transition name="fade">
      <div v-if="showNewDoc" class="dialog-overlay" @click.self="showNewDoc = null">
        <div class="dialog">
          <h3>新建文档</h3>
          <input
            v-model="newDocTitle"
            placeholder="文档标题..."
            class="dialog-input"
            @keyup.enter="doCreateDocument(showNewDoc!)"
            autofocus
          />
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showNewDoc = null">取消</button>
            <button class="btn btn-primary" @click="doCreateDocument(showNewDoc!)" :disabled="creating">创建</button>
          </div>
        </div>
      </div>
    </Transition>
    <!-- Adopt Dialog -->
    <Transition name="fade">
      <div v-if="showAdoptDialog" class="dialog-overlay" @click.self="showAdoptDialog = null">
        <div class="dialog">
          <h3>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            采纳讨论产出
          </h3>
          <p class="adopt-preview">{{ showAdoptDialog.title }}</p>
          <div class="adopt-options">
            <label class="adopt-option">
              <input type="radio" v-model="adoptAction" value="new_doc" /> 创建新文档
            </label>
            <label class="adopt-option">
              <input type="radio" v-model="adoptAction" value="merge" :disabled="!showAdoptDialog.stageDocs?.length" /> 合并到已有文档
            </label>
          </div>
          <input v-if="adoptAction === 'new_doc'" v-model="adoptTitle" placeholder="文档标题..." class="dialog-input" />
          <select v-if="adoptAction === 'merge' && showAdoptDialog.stageDocs?.length" v-model="adoptTargetDoc" class="dialog-input">
            <option v-for="d in showAdoptDialog.stageDocs" :key="d.id" :value="d.id">{{ d.title }} (v{{ d.current_version }})</option>
          </select>
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showAdoptDialog = null">取消</button>
            <button class="btn btn-primary" @click="doAdopt" :disabled="!!adoptingId">{{ adoptingId ? '处理中...' : '确认采纳' }}</button>
          </div>
        </div>
      </div>
    </Transition>
    <!-- Output Preview Modal -->
    <Transition name="fade">
      <div v-if="previewOutput" class="dialog-overlay" @click.self="previewOutput = null">
        <div class="preview-modal">
          <h3 class="preview-modal-title">{{ previewOutput.title }}</h3>
          <div class="preview-modal-body markdown-body" v-html="marked.parse(previewOutput.content || '')"></div>
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="previewOutput = null">关闭</button>
            <button
              v-if="previewOutput.status !== 'adopted'"
              class="btn btn-primary"
              @click="() => { const o = previewOutput; previewOutput = null; openAdopt(o, stages.find((s: any) => (s.outputs || []).some((x: any) => x.id === o.id))?.documents || []) }"
            >采纳</button>
          </div>
        </div>
      </div>
    </Transition>
    <!-- New Discussion Dialog -->
    <Transition name="fade">
      <div v-if="showNewDiscDialog" class="dialog-overlay" @click.self="showNewDiscDialog = null">
        <div class="dialog dialog-enhanced">
          <h3 class="dialog-title">新建讨论</h3>
          <div class="dialog-participants">
            <span class="participants-label">参与者：</span>
            <span class="participants-tags">
              <span
                v-for="agent in stageAgents(stages.find((s: any) => s.id === showNewDiscDialog) || {})"
                :key="agent"
                class="participant-tag"
              >{{ AGENT_LABELS[agent] || agent }}</span>
            </span>
          </div>
          <div class="dialog-field">
            <label class="dialog-label">讨论主题</label>
            <textarea
              v-model="newDiscTopic"
              placeholder="输入讨论话题..."
              class="dialog-textarea"
              rows="3"
              @keydown.meta.enter="createStageDiscussion(showNewDiscDialog!)"
              @keydown.ctrl.enter="createStageDiscussion(showNewDiscDialog!)"
              autofocus
            />
          </div>
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showNewDiscDialog = null; newDiscTopic = ''">取消</button>
            <button class="btn btn-primary" @click="createStageDiscussion(showNewDiscDialog!)" :disabled="creatingDisc">{{ creatingDisc ? '创建中...' : '创建' }}</button>
          </div>
        </div>
      </div>
    </Transition>
    <!-- Member Management Dialog -->
    <Transition name="fade">
      <div v-if="showMemberDialog" class="dialog-overlay" @click.self="showMemberDialog = false">
        <div class="dialog dialog-wide">
          <h3 class="dialog-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            成员管理
          </h3>
          <div v-if="loadingMembers" class="member-loading">加载中...</div>
          <div v-else class="member-list">
            <div v-for="m in members" :key="m.id" class="member-item">
              <div class="member-info">
                <span class="member-name">{{ m.username || m.user_id }}</span>
                <span class="member-role-badge" :class="'role-' + m.role">{{ {admin:'管理员',editor:'编辑',viewer:'查看',member:'成员',owner:'创建者'}[m.role] || m.role }}</span>
              </div>
              <button v-if="m.role !== 'owner'" class="btn-remove" @click="removeMember(m.id)">移除</button>
            </div>
            <div v-if="members.length === 0" class="member-empty">暂无成员</div>
          </div>
          <div class="member-invite">
            <input v-model="inviteUsername" placeholder="输入用户名..." class="dialog-input invite-input" />
            <select v-model="inviteRole" class="dialog-input invite-role">
              <option value="editor">编辑</option>
              <option value="viewer">查看</option>
            </select>
            <button class="btn btn-primary btn-sm" @click="inviteMember" :disabled="inviting">邀请</button>
          </div>
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showMemberDialog = false">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
    <!-- Stage Management Dialog -->
    <Transition name="fade">
      <div v-if="showStageDialog" class="dialog-overlay" @click.self="showStageDialog = false">
        <div class="dialog dialog-wide">
          <h3 class="dialog-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            管理阶段
          </h3>
          <div class="stage-edit-list">
            <div v-for="s in editingStages" :key="s.id" class="stage-edit-item">
              <input v-model="s.editName" class="dialog-input stage-edit-input" />
              <button
                v-if="s.editName !== s.name"
                class="btn btn-sm btn-primary"
                @click="saveStageRename(s)"
                :disabled="savingStage"
              >保存</button>
              <button
                v-if="s.is_custom"
                class="btn-remove"
                @click="deleteCustomStage(s.id)"
                :disabled="savingStage"
              >删除</button>
              <span v-if="!s.is_custom" class="stage-default-tag">默认</span>
            </div>
          </div>
          <div class="stage-add-row">
            <input v-model="newStageName" placeholder="自定义阶段名称..." class="dialog-input stage-edit-input" @keyup.enter="addCustomStage" />
            <button class="btn btn-sm btn-primary" @click="addCustomStage" :disabled="savingStage || !newStageName.trim()">+ 添加</button>
          </div>
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showStageDialog = false">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
    <!-- Delete Confirm Dialog -->
    <Transition name="fade">
      <div v-if="showDeleteConfirm" class="dialog-overlay" @click.self="showDeleteConfirm = false">
        <div class="dialog">
          <h3>⚠️ 确认删除项目</h3>
          <p style="color: #ef4444; font-weight: 500;">你确定要删除项目「{{ project?.name }}」吗？</p>
          <p style="color: #6b7280; font-size: 13px;">此操作不可撤销，项目的所有阶段、文档、讨论记录将被永久删除。</p>
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showDeleteConfirm = false">取消</button>
            <button class="btn btn-danger" @click="deleteProject" :disabled="deleting">{{ deleting ? '删除中...' : '确认删除' }}</button>
          </div>
        </div>
      </div>
    </Transition>
    <!-- Access Denied Modal -->
    <Transition name="fade">
      <div v-if="showAccessModal" class="dialog-overlay access-overlay" @click.self="goBackToHall">
        <div class="modal access-modal">
          <div class="access-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          </div>
          <h3>{{ project?.name }}</h3>
          <p class="access-desc">{{ project?.description || '这是一个私密项目' }}</p>
          <p class="access-hint">你需要获得权限才能查看此项目内容</p>
          <div class="access-actions">
            <button class="btn btn-primary" @click="requestAccess('viewer')">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
              申请查看权限
            </button>
            <button class="btn btn-secondary" @click="requestAccess('editor')">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              申请编辑权限
            </button>
          </div>
          <button class="btn-ghost" @click="goBackToHall">← 返回大厅</button>
        </div>
      </div>
    </Transition>
  </div>

</template>

<style scoped>
/* ---- Base ---- */
.project-detail {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #FFFBF5;
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ---- Breadcrumb ---- */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 24px;
  height: 36px;
  flex-shrink: 0;
}
.bc-link {
  font-size: 14px;
  font-weight: 500;
  color: #7C3AED;
  cursor: pointer;
}
.bc-link:hover { text-decoration: underline; }
.bc-sep { font-size: 14px; color: #A1A1AA; }
.bc-current { font-size: 14px; font-weight: 500; color: #18181B; }

/* ---- Header ---- */
.pd-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 72px;
  background: #FFFFFF;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  flex-shrink: 0;
}
.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.header-title {
  font-size: 20px;
  font-weight: 700;
  color: #18181B;
  line-height: 1.2;
}
.header-desc {
  font-size: 13px;
  color: #71717A;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.status-pill-active { background: #DCFCE7; color: #16A34A; }
.status-pill-idle { background: #F4F4F5; color: #71717A; }
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot-active { background: #22C55E; }
.status-dot-idle { background: #D4D4D8; }
.gear-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid #E4E4E7;
  background: transparent;
  color: #71717A;
  cursor: pointer;
  transition: background 0.12s;
}
.gear-btn:hover { background: #F4F4F5; color: #18181B; }
.gear-btn-danger { color: #EF4444; border-color: #fca5a5; }
.gear-btn-danger:hover { background: #fef2f2; }

/* ---- Pending bar ---- */
.pending-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #FEF3C7;
  border: 1px solid #D97706;
  border-radius: 0;
  padding: 10px 24px;
  flex-shrink: 0;
}
.pending-bar > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 500;
  color: #92400E;
}
.pending-item { display: flex; align-items: center; gap: 8px; margin-top: 4px; font-size: 13px; }

/* ---- Loading ---- */
.pd-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9CA3AF;
  font-size: 14px;
}

/* ---- Pipeline ---- */
.pipeline {
  display: flex;
  gap: 12px;
  flex: 1;
  overflow: hidden;
  padding: 16px 24px;
  min-height: 0;
}
.pipeline-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-width: 160px;
  overflow: hidden;
}
.col-header { display: flex; flex-direction: column; flex-shrink: 0; }
.col-bar { height: 4px; border-radius: 2px; width: 100%; }
.col-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  padding: 6px 0;
}
.col-name { font-size: 13px; font-weight: 600; color: #18181B; }
.col-count {
  font-size: 12px;
  font-weight: 500;
  color: #71717A;
  background: #F4F4F5;
  padding: 1px 8px;
  border-radius: 100px;
}
.col-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}
.col-body::-webkit-scrollbar { width: 4px; }
.col-body::-webkit-scrollbar-thumb { background: #E4E4E7; border-radius: 4px; }

/* ---- Cards ---- */
.item-card {
  background: #FFFFFF;
  border-radius: 10px;
  padding: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition: box-shadow 0.15s;
  flex-shrink: 0;
}
.item-card:hover { box-shadow: 0 3px 12px rgba(0,0,0,0.1); }
.item-card-output { border: 1px solid #fbbf24; background: #fffbeb; }
.item-card-output:hover { background: #fef3c7; }
.card-header-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.card-icon { font-size: 13px; flex-shrink: 0; }
.card-title {
  font-size: 12px;
  font-weight: 600;
  color: #18181B;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-meta { font-size: 11px; color: #71717A; }
.card-footer { display: flex; align-items: center; gap: 5px; }
.status-dot-sm { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.card-status-txt { font-size: 11px; color: #71717A; }
.adopted-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 100px;
  background: #DCFCE7;
  color: #16A34A;
  font-weight: 600;
  flex-shrink: 0;
}

/* ---- Empty & New buttons ---- */
.col-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
}
.col-empty-txt { font-size: 12px; color: #D4D4D8; }
.new-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid #E4E4E7;
  background: transparent;
  font-size: 11px;
  color: #71717A;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.12s;
  flex-shrink: 0;
}
.new-btn:hover { background: #F4F4F5; }
.new-btn-complete { border-color: #86efac; color: #16A34A; }
.new-btn-complete:hover { background: #f0fdf4; }

/* ---- Bottom Bar ---- */
.bottom-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 52px;
  padding: 0 24px;
  background: #FFFFFF;
  border-top: 1px solid #F0EDE8;
  flex-shrink: 0;
  overflow-x: auto;
  flex-wrap: nowrap;
}
.bottom-bar::-webkit-scrollbar { height: 4px; }
.bottom-bar::-webkit-scrollbar-thumb { background: #E4E4E7; border-radius: 4px; }
.bottom-label { font-size: 13px; font-weight: 600; color: #18181B; flex-shrink: 0; }
.result-card {
  display: flex;
  align-items: center;
  gap: 7px;
  background: #F4F4F5;
  border-radius: 8px;
  padding: 5px 10px;
  cursor: pointer;
  transition: background 0.12s;
  flex-shrink: 0;
}
.result-card:hover { background: #EDE9FE; }
.result-text { font-size: 12px; font-weight: 500; color: #18181B; }
.result-pill {
  background: #DCFCE7;
  color: #16A34A;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 999px;
}
.no-results { font-size: 12px; color: #D4D4D8; }

/* ---- Shared buttons ---- */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background 0.15s;
}
.btn-sm { padding: 5px 12px; font-size: 13px; }
.btn-primary { background: #7C3AED; color: #fff; }
.btn-primary:hover { background: #6D28D9; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #F3F4F6; color: #374151; border: 1px solid #E5E7EB; }
.btn-secondary:hover { background: #E5E7EB; }
.btn-danger { background: #EF4444; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.btn-danger:hover { background: #dc2626; }

/* ---- Dialogs ---- */
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
  border-radius: 12px;
  padding: 24px;
  width: min(400px, 90vw);
  box-shadow: 0 8px 32px -4px #00000020;
}
.dialog h3 { margin: 0 0 16px; font-size: 18px; font-weight: 600; }
.dialog-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}
.dialog-input:focus { border-color: #7C3AED; box-shadow: 0 0 0 2px rgba(124,58,237,0.15); }
.dialog-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.output-card { border-color: #fbbf24; background: #fffbeb; }
.output-card:hover { background: #FEF3C7; }
.out-status-draft { color: #f59e0b; font-weight: 500; }
.out-status-adopted { display: inline-flex; align-items: center; gap: 3px; color: #16A34A; font-weight: 500; }
.adopt-preview { font-size: 14px; color: #374151; background: #FFFBF5; padding: 8px 12px; border-radius: 6px; margin: 0 0 12px; }
.adopt-options { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.adopt-option { display: flex; align-items: center; gap: 6px; font-size: 14px; cursor: pointer; }
.adopt-option input[type=radio] { accent-color: #7C3AED; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.preview-modal {
  background: #FFFFFF;
  border-radius: 16px;
  padding: 28px;
  width: min(700px, 90vw);
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px -4px #00000020;
  display: flex;
  flex-direction: column;
}
.preview-modal-title { font-size: 18px; font-weight: 700; color: #18181B; margin: 0 0 16px; padding-bottom: 12px; border-bottom: 1px solid #E5E7EB; }
.preview-modal-body { flex: 1; overflow-y: auto; margin-bottom: 16px; }
.markdown-body { font-size: 14px; line-height: 1.8; color: #374151; }
.markdown-body h1 { font-size: 1.5em; font-weight: 700; margin: 0 0 12px; color: #18181B; }
.markdown-body h2 { font-size: 1.3em; font-weight: 700; margin: 20px 0 10px; color: #18181B; }
.markdown-body h3 { font-size: 1.15em; font-weight: 600; margin: 16px 0 8px; color: #1F2937; }
.markdown-body p { margin: 0 0 10px; }
.markdown-body ul, .markdown-body ol { margin: 0 0 10px; padding-left: 2em; }
.markdown-body li { margin-bottom: 4px; }
.markdown-body ul li { list-style-type: disc; }
.markdown-body ol li { list-style-type: decimal; }
.markdown-body code { background: #F3F4F6; color: #e11d48; font-size: 0.875em; padding: 2px 5px; border-radius: 4px; }
.markdown-body pre { background: #1F2937; color: #f9fafb; padding: 14px; border-radius: 8px; overflow-x: auto; margin: 0 0 12px; }
.markdown-body pre code { background: none; color: inherit; padding: 0; }
.markdown-body blockquote { border-left: 4px solid #D1D5DB; padding-left: 14px; margin: 0 0 10px; color: #6B7280; }
.markdown-body table { width: 100%; border-collapse: collapse; margin: 0 0 12px; font-size: 14px; }
.markdown-body th { background: #F3F4F6; font-weight: 600; text-align: left; padding: 6px 10px; border: 1px solid #D1D5DB; }
.markdown-body td { padding: 6px 10px; border: 1px solid #E5E7EB; }
.markdown-body strong { font-weight: 700; color: #18181B; }
.dialog-participants { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 16px; padding: 10px 12px; background: #F8F7FF; border-radius: 8px; border: 1px solid #E8E4FF; }
.participants-label { font-size: 12px; font-weight: 600; color: #7C3AED; white-space: nowrap; padding-top: 3px; }
.participants-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.participant-tag { font-size: 12px; padding: 2px 10px; background: #EDE9FE; color: #5B21B6; border-radius: 20px; font-weight: 500; }
.dialog-enhanced { border-radius: 16px; padding: 28px; width: min(440px, 90vw); box-shadow: 0 8px 32px -4px #00000020; }
.dialog-title { margin: 0 0 20px; font-size: 19px; font-weight: 700; color: #18181B; }
.dialog-field { margin-bottom: 14px; }
.dialog-label { display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px; }
.dialog-desc { font-size: 13px; color: #6b7280; margin: -4px 0 14px; line-height: 1.5; }
.dialog-textarea { width: 100%; padding: 10px 12px; border: 1px solid #D1D5DB; border-radius: 8px; font-size: 14px; outline: none; box-sizing: border-box; resize: vertical; font-family: inherit; line-height: 1.5; }
.dialog-textarea:focus { border-color: #7C3AED; box-shadow: 0 0 0 2px rgba(124,58,237,0.15); }
.dialog-wide { border-radius: 16px; padding: 28px; width: min(500px, 90vw); box-shadow: 0 8px 32px -4px #00000020; }
.member-loading { text-align: center; color: #9CA3AF; padding: 20px; }
.member-list { margin-bottom: 16px; max-height: 260px; overflow-y: auto; }
.member-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #F3F4F6; }
.member-info { display: flex; align-items: center; gap: 10px; }
.member-name { font-size: 14px; font-weight: 500; color: #18181B; }
.member-role-badge { font-size: 11px; padding: 2px 8px; border-radius: 6px; font-weight: 500; }
.role-owner { background: #FEF3C7; color: #D97706; }
.role-editor { background: #EDE9FE; color: #7C3AED; }
.role-viewer { background: #F3F4F6; color: #6B7280; }
.member-empty { text-align: center; color: #D1D5DB; font-size: 13px; padding: 16px; }
.btn-remove { background: none; border: 1px solid #fca5a5; color: #EF4444; font-size: 12px; padding: 3px 10px; border-radius: 6px; cursor: pointer; }
.btn-remove:hover { background: #fef2f2; }
.member-invite { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.invite-input { flex: 1; }
.invite-role { width: 100px; flex-shrink: 0; }
.stage-edit-list { margin-bottom: 16px; max-height: 320px; overflow-y: auto; }
.stage-edit-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #F3F4F6; }
.stage-edit-input { flex: 1; }
.stage-default-tag { font-size: 11px; color: #9CA3AF; background: #F3F4F6; padding: 2px 8px; border-radius: 6px; flex-shrink: 0; }
.stage-add-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.pending-item .btn-sm { padding: 2px 8px; font-size: 12px; }
.access-overlay { z-index: 300; }
.access-modal { text-align: center; padding: 32px 40px; max-width: 420px; width: 90%; border-radius: 16px; background: #FFFFFF; box-shadow: 0 8px 32px -4px #00000020; }
.access-icon { display: flex; justify-content: center; color: #6B7280; margin-bottom: 12px; }
.access-modal h3 { font-size: 20px; margin-bottom: 6px; color: #1F2937; }
.access-desc { color: #6B7280; font-size: 13px; margin-bottom: 2px; }
.access-hint { color: #9CA3AF; font-size: 12px; margin-bottom: 20px; }
.access-actions { display: flex; gap: 10px; justify-content: center; margin-bottom: 12px; }
.btn-ghost { background: none; border: none; color: #6B7280; cursor: pointer; font-size: 13px; padding: 6px 10px; }
.btn-ghost:hover { color: #374151; }

@media (max-width: 768px) {
  .pipeline { padding: 12px 12px; gap: 8px; }
  .pipeline-col { min-width: 140px; }
  .pd-header { padding: 0 16px; }
  .breadcrumb { padding: 0 16px; }
  .bottom-bar { padding: 0 16px; }
  .dialog, .dialog-enhanced, .dialog-wide { width: calc(100vw - 32px); padding: 20px; }
  .preview-modal { width: calc(100vw - 24px); padding: 20px; max-height: 85vh; }
  .member-invite { flex-wrap: wrap; }
  .invite-input { flex: 1 1 100%; }
  .invite-role { width: auto; flex: 1; }
}
</style>
