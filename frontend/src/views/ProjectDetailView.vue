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

function statusBadge(status: string) {
  if (status === 'completed') return { text: '✅ 已完成', cls: 'completed' }
  if (status === 'active') return { text: '💬 进行中', cls: 'active' }
  return { text: '🔒 未解锁', cls: 'locked' }
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

    <header class="pd-header">
      <button class="back-btn" @click="router.push('/')">← 返回大厅</button>
      <h1 v-if="project">{{ project.name }}</h1>
      <div style="margin-left: auto;">
        <button v-if="canEdit" class="btn btn-sm btn-secondary" @click="openMemberDialog">👥 成员</button>
      </div>
    </header>

    <div v-if="isAdmin && pendingRequests.length > 0" class="pending-bar">
      <span>📬 {{ pendingRequests.length }} 个权限申请待审批</span>
      <div v-for="req in pendingRequests" :key="req.user_id" class="pending-item">
        <span>{{ req.display_name || req.username }} 申请 <strong>{{ req.requested_role === 'editor' ? '编辑' : '查看' }}</strong> 权限</span>
        <button class="btn btn-sm btn-primary" @click="approveRequest(req.user_id)">✓ 批准</button>
        <button class="btn btn-sm btn-danger" @click="rejectRequest(req.user_id)">✗ 拒绝</button>
      </div>
    </div>

    <div v-if="loading" class="pd-loading">加载中...</div>

    <div v-else class="stages">
      <div v-if="isOwner" class="stages-toolbar">
        <button v-if="canEdit" class="btn btn-sm btn-secondary" @click="openStageDialog">⚙️ 管理阶段</button>
      </div>
      <div v-for="stage in stages" :key="stage.id" class="stage-section" :class="stage.status">
        <div class="stage-header" @click="toggleStage(stage.id)" style="cursor: pointer;">
          <span class="stage-toggle" :class="{ collapsed: isStageCollapsed(stage.id) }">▶</span>
          <h2 class="stage-name">{{ stage.name }}</h2>
          <span class="status-badge" :class="statusBadge(stage.status).cls">
            {{ statusBadge(stage.status).text }}
          </span>
          <button
            v-if="stage.status === 'active'"
            class="btn btn-sm btn-complete"
            @click.stop="doCompleteStage(stage.id)"
          >标记完成</button>
        </div>

        <div class="stage-body" :class="{ 'stage-body-collapsed': isStageCollapsed(stage.id) }">
          <template v-if="stage.status === 'locked'">
            <div class="stage-locked-msg">
              完成前置阶段后解锁
            </div>
          </template>

          <template v-else>
          <div class="stage-content-grid" v-if="stage.documents.length || stage.discussions.length">
            <div
              v-for="doc in stage.documents"
              :key="'doc-'+doc.id"
              class="content-card doc-card"
              @click="goDocument(doc.id)"
            >
              <span class="content-icon">📄</span>
              <div class="content-info">
                <div class="content-title">{{ doc.title }}</div>
                <div class="content-meta">v{{ doc.current_version }} · {{ formatTime(doc.updated_at) }}</div>
              </div>
            </div>
            <div
              v-for="disc in stage.discussions"
              :key="'disc-'+disc.id"
              class="content-card disc-card"
              @click="goDiscussion(disc.id)"
            >
              <span class="content-icon">💬</span>
              <div class="content-info">
                <div class="content-title">{{ disc.topic }}</div>
                <div class="content-meta">
                  <LetterAvatar :name="disc.owner_name || ''" :size="16" />
                  <span>{{ disc.owner_name }} · {{ disc.message_count }}条</span>
                </div>
              </div>
            </div>
            <div
              v-for="output in (stage.outputs || [])"
              :key="'out-'+output.id"
              class="content-card output-card"
              @click="previewOutput = output"
            >
              <span class="content-icon">📝</span>
              <div class="content-info">
                <div class="content-title">{{ output.title }}</div>
                <div class="content-meta">
                  <span :class="'out-status-' + (output.status || 'draft')">{{ output.status === 'adopted' ? '✅ 已采纳' : '待采纳' }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="stage-empty">暂无内容</div>

          <div v-if="canEdit && (stage.status === 'active' || stage.status === 'completed')" class="stage-actions">
            <button class="btn btn-sm btn-secondary" @click="showNewDiscDialog = stage.id">+ 新讨论</button>
            <button v-if="stage.status === 'active'" class="btn btn-sm btn-secondary" @click="showNewDoc = stage.id">+ 新文档</button>
          </div>
          </template>
        </div>
      </div>
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
          <h3>📝 采纳讨论产出</h3>
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
          <h3 class="dialog-title">👥 成员管理</h3>
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
          <h3 class="dialog-title">⚙️ 管理阶段</h3>
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
    <!-- Access Denied Modal -->
    <Transition name="fade">
      <div v-if="showAccessModal" class="dialog-overlay access-overlay" @click.self="goBackToHall">
        <div class="modal access-modal">
          <div class="access-icon">🔒</div>
          <h3>{{ project?.name }}</h3>
          <p class="access-desc">{{ project?.description || '这是一个私密项目' }}</p>
          <p class="access-hint">你需要获得权限才能查看此项目内容</p>
          <div class="access-actions">
            <button class="btn btn-primary" @click="requestAccess('viewer')">📖 申请查看权限</button>
            <button class="btn btn-secondary" @click="requestAccess('editor')">✏️ 申请编辑权限</button>
          </div>
          <button class="btn-ghost" @click="goBackToHall">← 返回大厅</button>
        </div>
      </div>
    </Transition>
  </div>

</template>

<style scoped>
.project-detail {
  min-height: 100vh;
  background: #f9fafb;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.pd-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 10;
}
.pd-header h1 {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  color: #111827;
}
.back-btn {
  background: none;
  border: none;
  color: #4f46e5;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.back-btn:hover { background: #f3f4f6; }
.pd-loading {
  text-align: center;
  padding: 60px;
  color: #9ca3af;
}
.stages {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}
.stage-section {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.stage-section.locked {
  opacity: 0.6;
}
.stage-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.stage-toggle {
  font-size: 12px;
  color: #9ca3af;
  transition: transform 0.25s ease;
  transform: rotate(90deg);
  flex-shrink: 0;
}
.stage-toggle.collapsed {
  transform: rotate(0deg);
}
.stage-body {
  max-height: 1000px;
  overflow: hidden;
  transition: max-height 0.3s ease, opacity 0.25s ease;
  opacity: 1;
}
.stage-body-collapsed {
  max-height: 0;
  opacity: 0;
}
.stage-name {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
  color: #111827;
}
.status-badge {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
}
.status-badge.completed { background: #ecfdf5; color: #10b981; }
.status-badge.active { background: #eff6ff; color: #3b82f6; }
.status-badge.locked { background: #f3f4f6; color: #9ca3af; }
.stage-locked-msg {
  color: #9ca3af;
  font-size: 13px;
  font-style: italic;
}
.stage-content-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.content-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.1s;
}
.content-card:hover { background: #f9fafb; }
.content-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
.content-title {
  font-size: 14px;
  font-weight: 500;
  color: #111827;
  margin-bottom: 4px;
}
.content-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #9ca3af;
}
.stage-empty {
  color: #d1d5db;
  font-size: 13px;
  text-align: center;
  padding: 16px;
}
.stage-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

/* Shared styles */
.btn {
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background 0.15s;
}
.btn-sm { padding: 5px 12px; font-size: 13px; }
.btn-primary { background: #4f46e5; color: #fff; }
.btn-primary:hover { background: #4338ca; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb; }
.btn-secondary:hover { background: #e5e7eb; }
.btn-complete { background: #10b981; color: #fff; }
.btn-complete:hover { background: #059669; }

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.dialog {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  width: min(400px, 90vw);
  box-shadow: 0 8px 30px rgba(0,0,0,0.15);
}
.dialog h3 { margin: 0 0 16px; font-size: 18px; font-weight: 600; }
.dialog-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}
.dialog-input:focus { border-color: #4f46e5; box-shadow: 0 0 0 2px rgba(79,70,229,0.15); }
.dialog-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }

.output-card { border-color: #fbbf24; background: #fffbeb; }
.output-card:hover { background: #fef3c7; }
.out-status-draft { color: #f59e0b; font-weight: 500; }
.out-status-adopted { color: #10b981; font-weight: 500; }
.adopt-preview { font-size: 14px; color: #374151; background: #f9fafb; padding: 8px 12px; border-radius: 6px; margin: 0 0 12px; }
.adopt-options { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.adopt-option { display: flex; align-items: center; gap: 6px; font-size: 14px; cursor: pointer; }
.adopt-option input[type=radio] { accent-color: #4f46e5; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.preview-modal {
  background: #fff;
  border-radius: 16px;
  padding: 28px;
  width: min(700px, 90vw);
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 12px 40px rgba(0,0,0,0.18);
  display: flex;
  flex-direction: column;
}
.preview-modal-title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}
.preview-modal-body {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 16px;
}
.markdown-body { font-size: 14px; line-height: 1.8; color: #374151; }
.markdown-body h1 { font-size: 1.5em; font-weight: 700; margin: 0 0 12px; color: #111827; }
.markdown-body h2 { font-size: 1.3em; font-weight: 700; margin: 20px 0 10px; color: #111827; }
.markdown-body h3 { font-size: 1.15em; font-weight: 600; margin: 16px 0 8px; color: #1f2937; }
.markdown-body p { margin: 0 0 10px; }
.markdown-body ul, .markdown-body ol { margin: 0 0 10px; padding-left: 2em; }
.markdown-body li { margin-bottom: 4px; }
.markdown-body ul li { list-style-type: disc; }
.markdown-body ol li { list-style-type: decimal; }
.markdown-body code { background: #f3f4f6; color: #e11d48; font-size: 0.875em; padding: 2px 5px; border-radius: 4px; }
.markdown-body pre { background: #1f2937; color: #f9fafb; padding: 14px; border-radius: 8px; overflow-x: auto; margin: 0 0 12px; }
.markdown-body pre code { background: none; color: inherit; padding: 0; }
.markdown-body blockquote { border-left: 4px solid #d1d5db; padding-left: 14px; margin: 0 0 10px; color: #6b7280; }
.markdown-body table { width: 100%; border-collapse: collapse; margin: 0 0 12px; font-size: 14px; }
.markdown-body th { background: #f3f4f6; font-weight: 600; text-align: left; padding: 6px 10px; border: 1px solid #d1d5db; }
.markdown-body td { padding: 6px 10px; border: 1px solid #e5e7eb; }
.markdown-body strong { font-weight: 700; color: #111827; }

.dialog-enhanced {
  border-radius: 16px;
  padding: 28px;
  width: min(440px, 90vw);
  box-shadow: 0 12px 40px rgba(0,0,0,0.18);
}
.dialog-title {
  margin: 0 0 20px;
  font-size: 19px;
  font-weight: 700;
  color: #111827;
}
.dialog-field { margin-bottom: 14px; }
.dialog-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 6px;
}
.dialog-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
  resize: vertical;
  font-family: inherit;
  line-height: 1.5;
}
.dialog-textarea:focus { border-color: #4f46e5; box-shadow: 0 0 0 2px rgba(79,70,229,0.15); }

.dialog-wide {
  border-radius: 16px;
  padding: 28px;
  width: min(500px, 90vw);
  box-shadow: 0 12px 40px rgba(0,0,0,0.18);
}
.stages-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

/* Member dialog */
.member-loading { text-align: center; color: #9ca3af; padding: 20px; }
.member-list { margin-bottom: 16px; max-height: 260px; overflow-y: auto; }
.member-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #f3f4f6;
}
.member-info { display: flex; align-items: center; gap: 10px; }
.member-name { font-size: 14px; font-weight: 500; color: #111827; }
.member-role-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 500;
}
.role-owner { background: #fef3c7; color: #d97706; }
.role-editor { background: #eff6ff; color: #3b82f6; }
.role-viewer { background: #f3f4f6; color: #6b7280; }
.member-empty { text-align: center; color: #d1d5db; font-size: 13px; padding: 16px; }
.btn-remove {
  background: none;
  border: 1px solid #fca5a5;
  color: #ef4444;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 6px;
  cursor: pointer;
}
.btn-remove:hover { background: #fef2f2; }
.member-invite {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.invite-input { flex: 1; }
.invite-role { width: 100px; flex-shrink: 0; }

/* Stage edit dialog */
.stage-edit-list { margin-bottom: 16px; max-height: 320px; overflow-y: auto; }
.stage-edit-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
}
.stage-edit-input { flex: 1; }
.stage-default-tag {
  font-size: 11px;
  color: #9ca3af;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 6px;
  flex-shrink: 0;
}
.stage-add-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

@media (max-width: 768px) {
  .pd-header {
    padding: 12px 16px;
    gap: 10px;
  }
  .pd-header h1 {
    font-size: 17px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }
  .stages {
    padding: 16px 12px;
  }
  .stage-section {
    padding: 14px;
  }
  .stage-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  .stage-name {
    font-size: 15px;
  }
  .stage-content-grid {
    grid-template-columns: 1fr;
  }
  .stage-actions {
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
  }
  .stage-actions .btn {
    flex-shrink: 0;
    white-space: nowrap;
  }
  .dialog {
    width: calc(100vw - 32px);
    padding: 20px;
  }
  .dialog-enhanced {
    width: calc(100vw - 32px);
    padding: 20px;
  }
  .dialog-wide {
    width: calc(100vw - 32px);
    padding: 20px;
  }
  .dialog-title {
    font-size: 17px;
  }
  .preview-modal {
    width: calc(100vw - 24px);
    padding: 20px;
    max-height: 85vh;
  }
  .member-invite {
    flex-wrap: wrap;
  }
  .invite-input {
    flex: 1 1 100%;
  }
  .invite-role {
    width: auto;
    flex: 1;
  }
  .stage-edit-item {
    flex-wrap: wrap;
  }
}


.access-overlay { z-index: 300; }
.access-modal {
  text-align: center; padding: 32px 40px; max-width: 420px; width: 90%;
  border-radius: 16px; background: #fff;
}
.access-icon { font-size: 40px; margin-bottom: 12px; }
.access-modal h3 { font-size: 20px; margin-bottom: 6px; color: #1f2937; }
.access-desc { color: #6b7280; font-size: 13px; margin-bottom: 2px; }
.access-hint { color: #9ca3af; font-size: 12px; margin-bottom: 20px; }
.access-actions { display: flex; gap: 10px; justify-content: center; margin-bottom: 12px; }
.btn-ghost { background: none; border: none; color: #6b7280; cursor: pointer; font-size: 13px; padding: 6px 10px; }
.btn-ghost:hover { color: #374151; }

.pending-bar { background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; }
.pending-item { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 13px; }
.pending-item .btn-sm { padding: 2px 8px; font-size: 12px; }
.btn-danger { background: #ef4444; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.btn-danger:hover { background: #dc2626; }
</style>
