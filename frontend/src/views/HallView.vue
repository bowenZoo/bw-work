<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
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
  { key: 'discussion', label: '💬 讨论' },
  { key: 'project', label: '📁 项目' },
  { key: 'completed', label: '✅ 已完成' },
  { key: 'archived', label: '📦 已归档' },
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
const newProjectName = ref('')
const newProjectDescription = ref('')
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

function onCardClick(item: any) {
  if (item.type === 'discussion') {
    router.push(`/discussion/${item.id}`)
  } else {
    router.push(`/project/${item.id}`)
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
    const data = await createProject(newProjectName.value.trim(), newProjectDescription.value.trim() || undefined)
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
        <div class="empty-icon">🔍</div>
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
            <span class="card-icon">{{ item.type === 'discussion' ? '💬' : '📁' }}</span>
            <span class="card-type-badge" :class="item.type">{{ item.type === 'discussion' ? '讨论' : '项目' }}</span>
            <span
              v-if="statusMap[itemStatus(item)]"
              class="card-status-badge"
              :class="statusMap[itemStatus(item)].cls"
            >{{ statusMap[itemStatus(item)].label }}</span>
          </div>
          <h3 class="card-title">{{ item.name }}</h3>
          <p class="card-desc" v-if="item.description">{{ item.description }}</p>
          <div class="card-footer">
            <span v-if="item.type === 'discussion' && item.extra?.owner_name" class="card-meta">
              {{ item.extra.owner_name }}
            </span>
            <span v-if="item.type === 'discussion' && item.extra?.participants_count != null" class="card-meta">
              👥 {{ item.extra.participants_count }} 人参与
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
        <div class="dialog dialog-wide">
          <h3 class="dialog-title">发起新讨论</h3>
          <div class="dialog-two-col">
            <!-- 左侧：表单 -->
            <div class="dialog-col-left">
              <div class="dialog-field">
                <label class="dialog-label">选择模板</label>
                <select v-model="selectedTemplate" class="dialog-input" @change="onTemplateChange">
                  <option v-for="t in discussionTemplates" :key="t.label" :value="t.value">{{ t.label }}</option>
                </select>
              </div>
              <div class="dialog-field">
                <label class="dialog-label">讨论话题</label>
                <textarea
                  v-model="newDiscussionTopic"
                  placeholder="输入讨论话题..."
                  class="dialog-textarea"
                  rows="3"
                  @keydown.meta.enter="doCreateDiscussion"
                  @keydown.ctrl.enter="doCreateDiscussion"
                  autofocus
                />
              </div>
              <div class="dialog-field">
                <label class="dialog-label">关联项目（可选）</label>
                <select v-model="newDiscussionProjectId" class="dialog-input">
                  <option value="">不关联项目</option>
                  <option v-for="p in projectItems" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
              </div>
              <!-- 附件 -->
              <div class="dialog-field">
                <input ref="fileInputRef" type="file" accept=".md" style="display:none" @change="handleFileSelect" />
                <div v-if="attachmentFile" class="attachment-info">
                  <span>📎 {{ attachmentFile.name }} ({{ (attachmentFile.size / 1024).toFixed(1) }} KB)</span>
                  <button class="attachment-remove" @click="removeAttachment">✕</button>
                </div>
                <button v-else class="btn-ghost" @click="triggerFileInput">📎 添加参考文档（.md）</button>
              </div>
              <!-- 密码 -->
              <div class="dialog-field">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="usePassword" />
                  <span>设置讨论密码</span>
                </label>
                <div v-if="usePassword" class="password-field">
                  <input v-model="password" :type="showPassword ? 'text' : 'password'" class="dialog-input" placeholder="输入密码" />
                  <button class="btn-icon" @click="showPassword = !showPassword" type="button">{{ showPassword ? '🙈' : '👁️' }}</button>
                </div>
              </div>
              <!-- 自动暂停 -->
              <div class="dialog-field">
                <label class="dialog-label">自动暂停间隔</label>
                <div class="auto-pause-row">
                  <input v-model.number="autoPauseInterval" type="number" min="0" max="50" class="dialog-input auto-pause-input" />
                  <span class="hint-text">{{ autoPauseInterval > 0 ? `每 ${autoPauseInterval} 轮暂停` : '不自动暂停' }}</span>
                </div>
              </div>
              <!-- 人员选择 -->
              <div class="dialog-field">
                <AgentConfigEditor v-model:agents="selectedAgents" v-model:configs="agentConfigs" />
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
            </div>
            <!-- 右侧：Prompt 预览编辑 -->
            <div class="dialog-col-right">
              <div class="prompt-preview-title">Prompt 预览</div>
              <div v-if="customOverrides" class="prompt-scroll">
                <div class="prompt-field">
                  <label class="prompt-field-label">目标</label>
                  <textarea v-model="customOverrides.goal" class="prompt-field-input" placeholder="主策划的目标..." />
                </div>
                <div class="prompt-field">
                  <label class="prompt-field-label">背景设定</label>
                  <textarea v-model="customOverrides.backstory" class="prompt-field-input" placeholder="主策划的背景设定..." />
                </div>
                <div class="prompt-field">
                  <label class="prompt-field-label">沟通风格</label>
                  <textarea v-model="customOverrides.communication_style" class="prompt-field-input" placeholder="沟通风格描述..." />
                </div>
                <div class="prompt-field">
                  <label class="prompt-field-label">关注领域</label>
                  <div class="focus-chips">
                    <span v-for="(area, idx) in customOverrides.focus_areas" :key="idx" class="focus-chip">
                      {{ area }} <button class="chip-remove" @click="removeFocusArea(idx)">✕</button>
                    </span>
                    <input v-model="newFocusArea" class="focus-add-input" placeholder="添加领域..." @keydown="handleFocusAreaKeydown" />
                  </div>
                </div>
              </div>
              <div v-else class="prompt-empty">
                <p>👈 选择讨论风格后可预览和编辑 Prompt</p>
              </div>
            </div>
          </div>
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showNewDiscussion = false">取消</button>
            <button class="btn btn-primary" @click="doCreateDiscussion" :disabled="creating">创建 (⌘+Enter)</button>
          </div>
        </div>
      </div>
    </Transition>

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
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showNewProject = false">取消</button>
            <button class="btn btn-primary" @click="doCreateProject" :disabled="creating">创建</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Login Modal -->
    <LoginModal v-if="showLoginModal" @close="showLoginModal = false" @success="onLoginSuccess" />
  </div>
</template>

<style scoped>
.hall {
  min-height: 100vh;
  background: #f8fafc;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.hall-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 10;
}
.hall-title {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}
.hall-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hall-body {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
.hall-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.hall-search {
  flex: 0 0 260px;
  padding: 8px 14px;
  border: 1px solid #d1d5db;
  border-radius: 20px;
  font-size: 14px;
  outline: none;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.hall-search:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.15);
}
.hall-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.tab-btn {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.tab-btn:hover { background: #f3f4f6; }
.tab-btn.active {
  background: #3b82f6;
  color: #fff;
}
.card-status-badge {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 6px;
  font-weight: 500;
  margin-left: auto;
}
.status-active    { background: #eff6ff; color: #2563eb; }
.status-waiting   { background: #fffbeb; color: #d97706; }
.status-completed { background: #f0fdf4; color: #16a34a; }
.status-archived  { background: #f3f4f6; color: #6b7280; }

.hall-loading, .hall-empty {
  text-align: center;
  padding: 60px 20px;
  color: #9ca3af;
  font-size: 15px;
}
.hall-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.hall-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
}
.hall-card:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  transform: translateY(-2px);
}
.card-border-blue {
  border-left: 3px solid #3b82f6;
}
.card-border-green {
  border-left: 3px solid #10b981;
}
.card-border-gray {
  border-left: 3px solid #9ca3af;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.card-icon {
  font-size: 18px;
}
.card-type-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}
.card-type-badge.discussion {
  background: #3b82f6;
  color: #fff;
}
.card-type-badge.project {
  background: #10b981;
  color: #fff;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-desc {
  font-size: 13px;
  color: #6b7280;
  margin: 0 0 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.card-meta {
  font-size: 12px;
  color: #9ca3af;
}
.card-time {
  font-size: 12px;
  color: #9ca3af;
  margin-left: auto;
}
.card-last-active {
  font-size: 11px;
  color: #b0b8c4;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f3f4f6;
}
.card-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}
.progress-bar {
  flex: 1;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #10b981;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.progress-label {
  font-size: 11px;
  color: #6b7280;
  white-space: nowrap;
}
.hall-filter-empty {
  text-align: center;
  padding: 60px 20px;
}
.empty-icon {
  font-size: 40px;
  margin-bottom: 12px;
}
.empty-text {
  font-size: 16px;
  color: #6b7280;
  margin: 0 0 6px;
  font-weight: 500;
}
.empty-hint {
  font-size: 13px;
  color: #9ca3af;
  margin: 0;
}

/* Buttons */
.btn {
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background 0.15s;
}
.btn-primary {
  background: #4f46e5;
  color: #fff;
}
.btn-primary:hover { background: #4338ca; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #e5e7eb;
}
.btn-secondary:hover { background: #e5e7eb; }

/* Dialogs */
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
.dialog h3 {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 600;
}
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
.dialog-field {
  margin-bottom: 14px;
}
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
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 768px) {
  .hall-header {
    padding: 12px 16px;
  }
  .hall-title {
    font-size: 17px;
  }
  .hall-actions {
    gap: 6px;
  }
  .hall-actions .btn {
    padding: 6px 10px;
    font-size: 13px;
  }
  .hall-body {
    padding: 16px 12px;
  }
  .hall-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  .hall-search {
    flex: none;
    width: 100%;
  }
  .hall-tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    padding-bottom: 2px;
  }
  .hall-tabs::-webkit-scrollbar {
    display: none;
  }
  .tab-btn {
    flex-shrink: 0;
    white-space: nowrap;
  }
  .hall-grid {
    grid-template-columns: 1fr;
  }
  .card-title {
    font-size: 15px;
  }
  .dialog-enhanced {
    width: calc(100vw - 32px);
    padding: 20px;
  }
  .dialog-title {
    font-size: 17px;
  }
}

/* === 新建讨论弹窗扩展样式 === */
.dialog-wide { max-width: 900px; width: calc(100vw - 48px); max-height: 90vh; overflow-y: auto; }
.dialog-two-col { display: flex; gap: 20px; }
.dialog-col-left { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.dialog-col-right { flex: 1; min-width: 0; background: #f8fafc; border-radius: 10px; padding: 12px; max-height: 70vh; overflow-y: auto; }
.prompt-preview-title { font-size: 13px; font-weight: 600; color: #6b7280; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
.prompt-scroll { display: flex; flex-direction: column; gap: 8px; }
.prompt-field { display: flex; flex-direction: column; gap: 4px; }
.prompt-field-label { font-size: 12px; font-weight: 600; color: #374151; }
.prompt-field-input { width: 100%; padding: 6px 8px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 12px; resize: vertical; min-height: 44px; font-family: inherit; background: #fff; line-height: 1.5; }
.prompt-field-input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
.prompt-empty { display: flex; align-items: center; justify-content: center; height: 120px; color: #9ca3af; font-size: 13px; }
.focus-chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.focus-chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; background: #eff6ff; color: #2563eb; border-radius: 12px; font-size: 12px; }
.chip-remove { background: none; border: none; color: #93c5fd; cursor: pointer; font-size: 12px; padding: 0 2px; }
.chip-remove:hover { color: #dc2626; }
.focus-add-input { border: 1px dashed #d1d5db; border-radius: 8px; padding: 3px 8px; font-size: 12px; width: 120px; outline: none; }
.focus-add-input:focus { border-color: #3b82f6; }

.style-pills { display: flex; flex-wrap: wrap; gap: 6px; }
.style-pill { padding: 5px 12px; border-radius: 16px; border: 1px solid #d1d5db; background: #fff; font-size: 12px; cursor: pointer; transition: all 0.15s; color: #4b5563; }
.style-pill:hover { border-color: #3b82f6; color: #3b82f6; }
.style-pill-active { background: #3b82f6; color: #fff; border-color: #3b82f6; }

.checkbox-label { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; cursor: pointer; }
.password-field { display: flex; gap: 8px; margin-top: 6px; }
.btn-icon { background: none; border: none; cursor: pointer; font-size: 16px; padding: 4px; }
.btn-ghost { background: none; border: 1px dashed #d1d5db; border-radius: 8px; padding: 8px 12px; font-size: 13px; color: #6b7280; cursor: pointer; width: 100%; text-align: left; }
.btn-ghost:hover { border-color: #3b82f6; color: #3b82f6; }
.attachment-info { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #eff6ff; border-radius: 8px; font-size: 13px; color: #2563eb; }
.attachment-remove { background: none; border: none; color: #93c5fd; cursor: pointer; font-size: 14px; margin-left: auto; }
.attachment-remove:hover { color: #dc2626; }
.auto-pause-row { display: flex; align-items: center; gap: 8px; }
.auto-pause-input { width: 70px !important; }
.hint-text { font-size: 12px; color: #9ca3af; }

@media (max-width: 768px) {
  .dialog-wide { max-width: calc(100vw - 32px); }
  .dialog-two-col { flex-direction: column; }
  .dialog-col-right { margin-top: 12px; }
}
</style>
