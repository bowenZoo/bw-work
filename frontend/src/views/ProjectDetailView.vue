<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectDetail } from '@/composables/useProjectDetail'
import { useUserStore } from '@/stores/user'
import LetterAvatar from '@/components/common/LetterAvatar.vue'

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

async function doAdopt() {
  if (!showAdoptDialog.value || adoptingId.value) return
  adoptingId.value = showAdoptDialog.value.id
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const body: any = { action: adoptAction.value }
    if (adoptAction.value === 'new_doc') body.title = adoptTitle.value || showAdoptDialog.value.title
    if (adoptAction.value === 'merge') body.document_id = adoptTargetDoc.value
    const res = await fetch(\`\${base}/api/discussions/\${showAdoptDialog.value.discussion_id}/outputs/\${showAdoptDialog.value.id}/adopt\`, {
      method: 'POST', headers: { Authorization: \`Bearer \${userStore.accessToken}\`, 'Content-Type': 'application/json' },
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

onMounted(() => {
  refresh()
})

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
  const topic = prompt('讨论主题:')
  if (!topic?.trim()) return
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/discussions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userStore.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ topic: topic.trim(), project_id: projectId(), stage_id: stageId }),
    })
    if (!res.ok) throw new Error('Failed')
    const data = await res.json()
    router.push(`/discussion/${data.id}`)
  } catch {
    alert('创建讨论失败')
  }
}
</script>

<template>
  <div class="project-detail">
    <header class="pd-header">
      <button class="back-btn" @click="router.push('/')">← 返回大厅</button>
      <h1 v-if="project">{{ project.name }}</h1>
    </header>

    <div v-if="loading" class="pd-loading">加载中...</div>

    <div v-else class="stages">
      <div v-for="stage in stages" :key="stage.id" class="stage-section" :class="stage.status">
        <div class="stage-header">
          <h2 class="stage-name">{{ stage.name }}</h2>
          <span class="status-badge" :class="statusBadge(stage.status).cls">
            {{ statusBadge(stage.status).text }}
          </span>
          <button
            v-if="stage.status === 'active'"
            class="btn btn-sm btn-complete"
            @click="doCompleteStage(stage.id)"
          >标记完成</button>
        </div>

        <div v-if="stage.status === 'locked'" class="stage-locked-msg">
          完成前置阶段后解锁
        </div>

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
              @click="openAdopt(output, stage.documents)"
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

          <div v-if="stage.status === 'active'" class="stage-actions">
            <button class="btn btn-sm btn-secondary" @click="createStageDiscussion(stage.id)">+ 新讨论</button>
            <button class="btn btn-sm btn-secondary" @click="showNewDoc = stage.id">+ 新文档</button>
          </div>
        </template>
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
</style>
