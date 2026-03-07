<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useAdminApi } from '@/components/settings/useAdminApi'

const router = useRouter()
const userStore = useUserStore()
const { adminRequest } = useAdminApi()

// Guard: only admin
if (!userStore.isAdmin) {
  router.replace('/')
}

// ── Tab navigation ─────────────────────────────────────────────────────────
type Tab = 'dashboard' | 'llm' | 'image' | 'langfuse' | 'discussion' | 'data' | 'logs'
const activeTab = ref<Tab>('dashboard')

const TABS: { key: Tab; label: string }[] = [
  { key: 'dashboard',  label: '概览' },
  { key: 'llm',        label: 'LLM 配置' },
  { key: 'image',      label: '图像服务' },
  { key: 'langfuse',   label: 'Langfuse' },
  { key: 'discussion', label: '讨论设置' },
  { key: 'data',       label: '数据管理' },
  { key: 'logs',       label: '操作日志' },
]

// ═══════════════════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════
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
  ip_address?: string | null
  user_agent?: string | null
  before_value?: string | null
  after_value?: string | null
  details?: string | null
}

const dashStatus = ref<ConfigStatus>({
  llm_configured: false,
  langfuse_configured: false,
  langfuse_enabled: false,
  image_configured: false,
  default_image_provider: null,
})
const recentLogs = ref<AuditLog[]>([])

async function loadDashboard() {
  try {
    const data = await adminRequest<ConfigStatus>('/config/status')
    dashStatus.value = data
  } catch {}
  try {
    const data = await adminRequest<{ items: AuditLog[] }>('/logs?page_size=5')
    recentLogs.value = data.items || []
  } catch {}
}

// ═══════════════════════════════════════════════════════════════════════════
// LLM CONFIG
// ═══════════════════════════════════════════════════════════════════════════
interface LlmProfile {
  id: string
  name: string
  base_url: string
  model: string
  has_api_key: boolean
  is_active: boolean
}
interface TestResult {
  success: boolean
  message: string
  latency_ms?: number
}

const llmProfiles = ref<LlmProfile[]>([])
const llmEditing = ref(false)
const llmIsNew = ref(false)
const llmSaving = ref(false)
const llmShowKey = ref(false)
const llmTestingId = ref<string | null>(null)
const llmActivatingId = ref<string | null>(null)
const llmTestResults = reactive<Record<string, TestResult>>({})
const llmMsg = ref<{ success: boolean; text: string } | null>(null)
const llmEditingId = ref<string | null>(null)
const llmForm = ref({ id: '', name: '', api_key: '', base_url: '', model: 'gpt-4' })

async function loadLlmProfiles() {
  try { llmProfiles.value = await adminRequest<LlmProfile[]>('/config/llm/profiles') } catch {}
}
function llmStartCreate() {
  llmEditing.value = true; llmIsNew.value = true; llmEditingId.value = null
  llmForm.value = { id: '', name: '', api_key: '', base_url: '', model: 'gpt-4' }
  llmShowKey.value = false
}
function llmStartEdit(p: LlmProfile) {
  llmEditing.value = true; llmIsNew.value = false; llmEditingId.value = p.id
  llmForm.value = { id: p.id, name: p.name, api_key: '', base_url: p.base_url, model: p.model }
  llmShowKey.value = false
}
function llmCancelEdit() { llmEditing.value = false; llmEditingId.value = null }
async function llmSave() {
  llmSaving.value = true; llmMsg.value = null
  try {
    const payload: Record<string, unknown> = { name: llmForm.value.name, base_url: llmForm.value.base_url, model: llmForm.value.model }
    if (llmForm.value.api_key) payload.api_key = llmForm.value.api_key
    if (llmIsNew.value) {
      payload.id = llmForm.value.id
      await adminRequest('/config/llm/profiles', { method: 'POST', body: JSON.stringify(payload) })
      llmMsg.value = { success: true, text: '方案创建成功' }
    } else {
      await adminRequest(`/config/llm/profiles/${llmEditingId.value}`, { method: 'PUT', body: JSON.stringify(payload) })
      llmMsg.value = { success: true, text: '方案保存成功' }
    }
    llmEditing.value = false; llmEditingId.value = null
    await loadLlmProfiles()
  } catch (e) {
    llmMsg.value = { success: false, text: e instanceof Error ? e.message : '保存失败' }
  } finally { llmSaving.value = false }
}
async function llmTest(id: string) {
  llmTestingId.value = id; delete llmTestResults[id]
  try {
    const r = await adminRequest<TestResult>(`/config/test/llm/${id}`, { method: 'POST' })
    llmTestResults[id] = r
  } catch (e) {
    llmTestResults[id] = { success: false, message: e instanceof Error ? e.message : '测试失败' }
  } finally { llmTestingId.value = null }
}
async function llmActivate(id: string) {
  llmActivatingId.value = id; llmMsg.value = null
  try {
    await adminRequest(`/config/llm/profiles/${id}/activate`, { method: 'POST' })
    llmMsg.value = { success: true, text: '已切换激活方案' }
    await loadLlmProfiles()
  } catch (e) {
    llmMsg.value = { success: false, text: e instanceof Error ? e.message : '激活失败' }
  } finally { llmActivatingId.value = null }
}
async function llmDelete(id: string, name: string) {
  if (!confirm(`确定删除方案「${name}」？`)) return
  llmMsg.value = null
  try {
    await adminRequest(`/config/llm/profiles/${id}`, { method: 'DELETE' })
    llmMsg.value = { success: true, text: `已删除「${name}」` }
    await loadLlmProfiles()
  } catch (e) {
    llmMsg.value = { success: false, text: e instanceof Error ? e.message : '删除失败' }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// IMAGE CONFIG
// ═══════════════════════════════════════════════════════════════════════════
const imageOpenaiConfig = ref<any>({})
const imageOpenaiForm = ref({ enabled: false, base_url: '', api_key: '', model: '', prompt_prefix: '' })
const imageShowKey = ref(false)
const imageSaving = ref(false)
const imageMsg = ref<{ success: boolean; text: string } | null>(null)

async function loadImageConfig() {
  try {
    const data = await adminRequest<any>('/config/image/openai-compatible')
    imageOpenaiConfig.value = data
    imageOpenaiForm.value = {
      enabled: data.enabled ?? false,
      base_url: data.base_url || '',
      api_key: '',
      model: data.model || '',
      prompt_prefix: data.prompt_prefix || '',
    }
  } catch {}
}
async function saveImageConfig() {
  imageSaving.value = true; imageMsg.value = null
  try {
    const payload: Record<string, unknown> = {
      enabled: imageOpenaiForm.value.enabled,
      base_url: imageOpenaiForm.value.base_url,
      model: imageOpenaiForm.value.model,
      prompt_prefix: imageOpenaiForm.value.prompt_prefix,
    }
    if (imageOpenaiForm.value.api_key) payload.api_key = imageOpenaiForm.value.api_key
    await adminRequest('/config/image/openai-compatible', { method: 'PUT', body: JSON.stringify(payload) })
    imageMsg.value = { success: true, text: '图像配置已保存' }
    await loadImageConfig()
  } catch (e) {
    imageMsg.value = { success: false, text: e instanceof Error ? e.message : '保存失败' }
  } finally { imageSaving.value = false }
}

// ═══════════════════════════════════════════════════════════════════════════
// LANGFUSE CONFIG
// ═══════════════════════════════════════════════════════════════════════════
const langfuseConfig = ref<any>({})
const langfuseForm = ref({ enabled: false, public_key: '', secret_key: '', host: '' })
const langfuseSaving = ref(false)
const langfuseMsg = ref<{ success: boolean; text: string } | null>(null)
const langfuseShowSecret = ref(false)

async function loadLangfuseConfig() {
  try {
    const data = await adminRequest<any>('/config/langfuse')
    langfuseConfig.value = data
    langfuseForm.value = {
      enabled: data.enabled ?? false,
      public_key: data.public_key || '',
      secret_key: '',
      host: data.host || '',
    }
  } catch {}
}
async function saveLangfuseConfig() {
  langfuseSaving.value = true; langfuseMsg.value = null
  try {
    const payload: Record<string, unknown> = {
      enabled: langfuseForm.value.enabled,
      public_key: langfuseForm.value.public_key,
      host: langfuseForm.value.host,
    }
    if (langfuseForm.value.secret_key) payload.secret_key = langfuseForm.value.secret_key
    await adminRequest('/config/langfuse', { method: 'PUT', body: JSON.stringify(payload) })
    langfuseMsg.value = { success: true, text: 'Langfuse 配置已保存' }
    await loadLangfuseConfig()
  } catch (e) {
    langfuseMsg.value = { success: false, text: e instanceof Error ? e.message : '保存失败' }
  } finally { langfuseSaving.value = false }
}

// ═══════════════════════════════════════════════════════════════════════════
// DISCUSSION SETTINGS
// ═══════════════════════════════════════════════════════════════════════════
const STAGE_TEMPLATES = [
  { id: 'concept', label: '概念孵化' },
  { id: 'core-gameplay', label: '核心玩法' },
  { id: 'art-style', label: '美术风格' },
  { id: 'tech-prototype', label: '技术原型' },
  { id: 'system-design', label: '系统设计' },
  { id: 'numbers', label: '数值设计' },
  { id: 'ui-ux', label: 'UI/UX' },
  { id: 'level-content', label: '关卡与内容' },
  { id: 'art-assets', label: '美术资产' },
  { id: 'default', label: '默认（其他阶段）' },
]
const AGENT_OPTIONS = [
  { value: 'lead_planner', label: '主策划' },
  { value: 'creative_director', label: '创意总监' },
  { value: 'system_designer', label: '系统策划' },
  { value: 'number_designer', label: '数值策划' },
  { value: 'visual_concept', label: '视觉概念设计师' },
  { value: 'market_director', label: '市场总监' },
  { value: 'operations_analyst', label: '运营策划' },
  { value: 'player_advocate', label: '玩家代言人' },
]
const discCurrentMax = ref(2)
const discForm = ref({ max_concurrent: 2 })
const discSaving = ref(false)
const discMsg = ref<{ success: boolean; message: string } | null>(null)
const discHasChanges = computed(() => discForm.value.max_concurrent !== discCurrentMax.value)
const discModerators = ref<Record<string, string>>({})
const discModSaved = ref<Record<string, boolean>>({})

async function loadDiscussionConfig() {
  try {
    const configs = await adminRequest<Array<{ category: string; key: string; value: string }>>('/config?category=discussion')
    const item = configs.find((c: any) => c.key === 'max_concurrent')
    if (item) {
      const val = parseInt(item.value, 10)
      if (!isNaN(val) && val > 0) { discCurrentMax.value = val; discForm.value.max_concurrent = val }
    }
  } catch {}
  try {
    const data = await adminRequest<{ moderators: Record<string, string> }>('/config/stage-moderators')
    discModerators.value = data.moderators || {}
  } catch {}
}
async function saveDiscConfig() {
  discSaving.value = true; discMsg.value = null
  try {
    await adminRequest('/config/discussion/max_concurrent', { method: 'PUT', body: JSON.stringify({ value: String(discForm.value.max_concurrent), encrypted: false }) })
    discCurrentMax.value = discForm.value.max_concurrent
    discMsg.value = { success: true, message: `并发数已更新为 ${discForm.value.max_concurrent}` }
  } catch (e) {
    discMsg.value = { success: false, message: e instanceof Error ? e.message : '保存失败' }
  } finally { discSaving.value = false }
}
async function saveDiscModerator(templateId: string) {
  try {
    await adminRequest(`/config/stage-moderators/${templateId}`, { method: 'PUT', body: JSON.stringify({ role: discModerators.value[templateId] }) })
    discModSaved.value[templateId] = true
    setTimeout(() => { discModSaved.value[templateId] = false }, 2000)
  } catch {
    discMsg.value = { success: false, message: `保存 ${templateId} 负责人失败` }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// DATA MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════
interface DiscussionItem { id: string; topic: string; owner_name: string | null; updated_at: string; archived: boolean; project_id: string | null }
interface ProjectItem { id: string; name: string; description: string; is_public: boolean; owner_name: string | null }

const dataTab = ref<'discussion' | 'project'>('discussion')
const dataSearch = ref('')
const dataDiscussions = ref<DiscussionItem[]>([])
const dataProjects = ref<ProjectItem[]>([])
const dataLoadingDisc = ref(false)
const dataLoadingProj = ref(false)
const dataConfirmItem = ref<any>(null)
const dataConfirmType = ref<'discussion' | 'project'>('discussion')
const dataDeleting = ref(false)

const dataFilteredDisc = computed(() => {
  const q = dataSearch.value.trim().toLowerCase()
  if (!q) return dataDiscussions.value
  return dataDiscussions.value.filter(d => d.topic.toLowerCase().includes(q) || (d.owner_name || '').toLowerCase().includes(q) || d.id.includes(q))
})
const dataFilteredProj = computed(() => {
  const q = dataSearch.value.trim().toLowerCase()
  if (!q) return dataProjects.value
  return dataProjects.value.filter(p => p.name.toLowerCase().includes(q) || (p.owner_name || '').toLowerCase().includes(q) || p.id.includes(q))
})

async function loadDiscussions() {
  dataLoadingDisc.value = true
  try {
    const data = await adminRequest<{ items: DiscussionItem[] }>('/data/discussions?page_size=200')
    dataDiscussions.value = data.items || []
  } catch {} finally { dataLoadingDisc.value = false }
}
async function loadProjects() {
  dataLoadingProj.value = true
  try {
    const data = await adminRequest<{ items: ProjectItem[] }>('/data/projects')
    dataProjects.value = data.items || []
  } catch {} finally { dataLoadingProj.value = false }
}
async function doDataDelete() {
  if (!dataConfirmItem.value) return
  dataDeleting.value = true
  try {
    const id = dataConfirmItem.value.id
    if (dataConfirmType.value === 'discussion') {
      await adminRequest(`/data/discussions/${id}`, { method: 'DELETE' })
      dataDiscussions.value = dataDiscussions.value.filter(d => d.id !== id)
    } else {
      await adminRequest(`/data/projects/${id}`, { method: 'DELETE' })
      dataProjects.value = dataProjects.value.filter(p => p.id !== id)
    }
    dataConfirmItem.value = null
  } catch (e: any) {
    alert(e?.message || '删除失败')
  } finally { dataDeleting.value = false }
}

// ═══════════════════════════════════════════════════════════════════════════
// AUDIT LOGS
// ═══════════════════════════════════════════════════════════════════════════
const logsList = ref<AuditLog[]>([])
const logsLoading = ref(false)
const logsPage = ref(1)
const logsPageSize = ref(20)
const logsTotalItems = ref(0)
const logsTotalPages = ref(0)
const logsSelected = ref<AuditLog | null>(null)
const logsFilters = reactive({ action: '', username: '', start_date: '', end_date: '' })
let logsDebounce: ReturnType<typeof setTimeout> | null = null

async function loadLogs() {
  logsLoading.value = true
  try {
    const params = new URLSearchParams()
    params.append('page', logsPage.value.toString())
    params.append('page_size', logsPageSize.value.toString())
    if (logsFilters.action) params.append('action', logsFilters.action)
    if (logsFilters.username) params.append('username', logsFilters.username)
    if (logsFilters.start_date) params.append('start_time', new Date(logsFilters.start_date).toISOString())
    if (logsFilters.end_date) {
      const end = new Date(logsFilters.end_date); end.setHours(23, 59, 59, 999)
      params.append('end_time', end.toISOString())
    }
    const r = await adminRequest<{ items: AuditLog[]; total: number; total_pages: number }>(`/logs?${params}`)
    logsList.value = r.items; logsTotalItems.value = r.total; logsTotalPages.value = r.total_pages
  } catch {} finally { logsLoading.value = false }
}
function logsDebouncedLoad() {
  if (logsDebounce) clearTimeout(logsDebounce)
  logsDebounce = setTimeout(loadLogs, 300)
}
function logsGoPage(p: number) {
  if (p >= 1 && p <= logsTotalPages.value) { logsPage.value = p; loadLogs() }
}
function logsClearFilters() {
  logsFilters.action = ''; logsFilters.username = ''; logsFilters.start_date = ''; logsFilters.end_date = ''
  logsPage.value = 1; loadLogs()
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════
function formatDate(dt: string) {
  if (!dt) return ''
  return new Date(dt).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
function formatAction(action: string) {
  const MAP: Record<string, string> = {
    login: '登录', login_failed: '登录失败', logout: '退出',
    config_update: '配置更新', config_delete: '配置删除', bootstrap_setup: '初始设置',
  }
  return MAP[action] || action
}
function logBadgeClass(action: string) {
  if (action === 'login') return 'bg-emerald-900/50 text-emerald-400'
  if (action === 'login_failed') return 'bg-red-900/50 text-red-400'
  if (action === 'logout') return 'bg-yellow-900/50 text-yellow-400'
  if (action === 'config_update') return 'bg-blue-900/50 text-blue-400'
  if (action === 'config_delete') return 'bg-orange-900/50 text-orange-400'
  return 'bg-zinc-700 text-zinc-400'
}

// ── Tab switch loader ──────────────────────────────────────────────────────
function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'dashboard') loadDashboard()
  else if (tab === 'llm') loadLlmProfiles()
  else if (tab === 'image') loadImageConfig()
  else if (tab === 'langfuse') loadLangfuseConfig()
  else if (tab === 'discussion') loadDiscussionConfig()
  else if (tab === 'data') { loadDiscussions(); loadProjects() }
  else if (tab === 'logs') loadLogs()
}

onMounted(() => loadDashboard())
</script>

<template>
  <div class="settings-wrap">
    <!-- Header -->
    <div class="settings-header">
      <button class="back-btn" @click="router.back()">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
        返回
      </button>
      <h1 class="settings-title">系统管理</h1>
      <span class="settings-user">{{ userStore.user?.display_name || userStore.user?.username }}</span>
    </div>

    <div class="settings-body">
      <!-- Sidebar tabs -->
      <nav class="settings-nav">
        <button
          v-for="tab in TABS"
          :key="tab.key"
          class="nav-item"
          :class="{ 'nav-item--active': activeTab === tab.key }"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </nav>

      <!-- Content area -->
      <div class="settings-content">

        <!-- ─── DASHBOARD ─────────────────────────────────────────────── -->
        <div v-if="activeTab === 'dashboard'" class="tab-pane">
          <h2 class="pane-title">系统概览</h2>

          <div class="status-grid">
            <div class="status-card">
              <div class="status-label">LLM 服务</div>
              <span class="status-badge" :class="dashStatus.llm_configured ? 'badge-ok' : 'badge-warn'">
                {{ dashStatus.llm_configured ? '已配置' : '未配置' }}
              </span>
            </div>
            <div class="status-card">
              <div class="status-label">Langfuse 监控</div>
              <span class="status-badge" :class="dashStatus.langfuse_enabled ? 'badge-ok' : 'badge-muted'">
                {{ dashStatus.langfuse_enabled ? '已启用' : dashStatus.langfuse_configured ? '已禁用' : '未配置' }}
              </span>
            </div>
            <div class="status-card">
              <div class="status-label">图像服务</div>
              <span class="status-badge" :class="dashStatus.image_configured ? 'badge-ok' : 'badge-warn'">
                {{ dashStatus.image_configured ? '已配置' : '未配置' }}
              </span>
            </div>
          </div>

          <div class="section-box">
            <div class="section-head">最近操作</div>
            <div v-if="recentLogs.length === 0" class="empty-text">暂无记录</div>
            <div v-else class="log-list">
              <div v-for="log in recentLogs" :key="log.id" class="log-row">
                <span class="log-badge" :class="logBadgeClass(log.action)">{{ formatAction(log.action) }}</span>
                <span class="log-user">{{ log.username }}</span>
                <span v-if="log.target" class="log-target">{{ log.target }}</span>
                <span class="log-time">{{ formatDate(log.timestamp) }}</span>
              </div>
            </div>
          </div>

          <div class="section-box">
            <div class="section-head">快捷入口</div>
            <div class="quick-links">
              <button v-for="tab in TABS.slice(1)" :key="tab.key" class="quick-link" @click="switchTab(tab.key)">
                {{ tab.label }}
              </button>
            </div>
          </div>
        </div>

        <!-- ─── LLM CONFIG ────────────────────────────────────────────── -->
        <div v-if="activeTab === 'llm'" class="tab-pane">
          <div class="pane-header">
            <h2 class="pane-title">LLM 配置</h2>
            <button class="btn-primary" @click="llmStartCreate">+ 新增方案</button>
          </div>

          <div v-if="llmMsg" class="msg-box" :class="llmMsg.success ? 'msg-ok' : 'msg-err'">{{ llmMsg.text }}</div>

          <div v-if="llmProfiles.length === 0 && !llmEditing" class="empty-text">暂无配置方案</div>

          <div v-for="p in llmProfiles" :key="p.id" class="section-box">
            <div class="profile-row">
              <div class="profile-info">
                <span class="profile-dot" :class="p.is_active ? 'dot-active' : 'dot-inactive'" />
                <div>
                  <div class="profile-name">
                    {{ p.name }}
                    <span v-if="p.is_active" class="tag tag-green">激活</span>
                    <span v-if="!p.has_api_key" class="tag tag-warn">未配置密钥</span>
                  </div>
                  <div class="profile-sub">{{ p.model }}<span v-if="p.base_url" class="ml-2">{{ p.base_url }}</span></div>
                </div>
              </div>
              <div class="profile-actions">
                <button class="btn-sm" @click="llmStartEdit(p)">编辑</button>
                <button class="btn-sm" :disabled="llmTestingId === p.id" @click="llmTest(p.id)">
                  {{ llmTestingId === p.id ? '测试中...' : '测试' }}
                </button>
                <button v-if="!p.is_active" class="btn-sm btn-green" :disabled="llmActivatingId === p.id" @click="llmActivate(p.id)">激活</button>
                <button v-if="!p.is_active" class="btn-sm btn-red" @click="llmDelete(p.id, p.name)">删除</button>
              </div>
            </div>
            <div v-if="llmTestResults[p.id]" class="test-result" :class="llmTestResults[p.id].success ? 'test-ok' : 'test-err'">
              {{ llmTestResults[p.id].message }}
              <span v-if="llmTestResults[p.id].latency_ms"> ({{ llmTestResults[p.id].latency_ms!.toFixed(0) }}ms)</span>
            </div>
          </div>

          <!-- Edit form -->
          <div v-if="llmEditing" class="section-box section-box--bordered">
            <div class="form-title">{{ llmIsNew ? '新增方案' : `编辑：${llmForm.name}` }}</div>
            <div v-if="llmIsNew" class="form-row">
              <label class="form-label">方案 ID（可选）</label>
              <input v-model="llmForm.id" class="form-input" placeholder="如 deepseek" />
            </div>
            <div class="form-row">
              <label class="form-label">名称</label>
              <input v-model="llmForm.name" class="form-input" placeholder="如 DeepSeek" />
            </div>
            <div class="form-row">
              <label class="form-label">API Key</label>
              <div class="input-group">
                <input v-model="llmForm.api_key" :type="llmShowKey ? 'text' : 'password'" class="form-input" :placeholder="llmIsNew ? 'sk-...' : '留空保持不变'" />
                <button type="button" class="input-toggle" @click="llmShowKey = !llmShowKey">{{ llmShowKey ? '隐藏' : '显示' }}</button>
              </div>
            </div>
            <div class="form-row">
              <label class="form-label">Base URL</label>
              <input v-model="llmForm.base_url" class="form-input" placeholder="https://api.openai.com/v1" />
            </div>
            <div class="form-row">
              <label class="form-label">模型</label>
              <input v-model="llmForm.model" list="llm-models" class="form-input" placeholder="输入或选择模型" />
              <datalist id="llm-models">
                <option value="gpt-4o"/><option value="gpt-4o-mini"/>
                <option value="deepseek-chat"/><option value="moonshot-v1-32k"/>
                <option value="qwen-max"/><option value="kimi-k2.5"/>
              </datalist>
            </div>
            <div class="form-actions">
              <button class="btn-secondary" @click="llmCancelEdit">取消</button>
              <button class="btn-primary" :disabled="llmSaving || !llmForm.name" @click="llmSave">
                {{ llmSaving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>

        <!-- ─── IMAGE CONFIG ──────────────────────────────────────────── -->
        <div v-if="activeTab === 'image'" class="tab-pane">
          <h2 class="pane-title">图像服务配置</h2>
          <div v-if="imageMsg" class="msg-box" :class="imageMsg.success ? 'msg-ok' : 'msg-err'">{{ imageMsg.text }}</div>

          <div class="section-box">
            <div class="section-head">OpenAI 兼容接口</div>
            <div class="toggle-row">
              <span class="form-label">启用图像生成</span>
              <button
                class="toggle-btn"
                :class="imageOpenaiForm.enabled ? 'toggle-on' : 'toggle-off'"
                @click="imageOpenaiForm.enabled = !imageOpenaiForm.enabled"
              ><span class="toggle-thumb" :class="imageOpenaiForm.enabled ? 'thumb-on' : 'thumb-off'" /></button>
            </div>
            <div class="form-row">
              <label class="form-label">Base URL</label>
              <input v-model="imageOpenaiForm.base_url" class="form-input" placeholder="https://api.example.com/v1" />
            </div>
            <div class="form-row">
              <label class="form-label">API 密钥</label>
              <div class="input-group">
                <input v-model="imageOpenaiForm.api_key" :type="imageShowKey ? 'text' : 'password'" class="form-input" placeholder="留空保持不变" />
                <button type="button" class="input-toggle" @click="imageShowKey = !imageShowKey">{{ imageShowKey ? '隐藏' : '显示' }}</button>
              </div>
            </div>
            <div class="form-row">
              <label class="form-label">模型</label>
              <input v-model="imageOpenaiForm.model" class="form-input" placeholder="如 dall-e-3 / stable-diffusion-xl" />
            </div>
            <div class="form-row">
              <label class="form-label">提示词前缀</label>
              <input v-model="imageOpenaiForm.prompt_prefix" class="form-input" placeholder="可选，附加到每次图像生成请求前" />
            </div>
            <div class="form-actions">
              <button class="btn-primary" :disabled="imageSaving" @click="saveImageConfig">
                {{ imageSaving ? '保存中...' : '保存配置' }}
              </button>
            </div>
          </div>
        </div>

        <!-- ─── LANGFUSE CONFIG ───────────────────────────────────────── -->
        <div v-if="activeTab === 'langfuse'" class="tab-pane">
          <h2 class="pane-title">Langfuse 监控配置</h2>
          <div v-if="langfuseMsg" class="msg-box" :class="langfuseMsg.success ? 'msg-ok' : 'msg-err'">{{ langfuseMsg.text }}</div>

          <div class="section-box">
            <div class="toggle-row">
              <div>
                <div class="form-label">启用 Langfuse 监控</div>
                <div class="form-hint">启用后 LLM 调用将被追踪记录</div>
              </div>
              <button class="toggle-btn" :class="langfuseForm.enabled ? 'toggle-on' : 'toggle-off'" @click="langfuseForm.enabled = !langfuseForm.enabled">
                <span class="toggle-thumb" :class="langfuseForm.enabled ? 'thumb-on' : 'thumb-off'" />
              </button>
            </div>
            <div class="form-row">
              <label class="form-label">公钥 (Public Key)</label>
              <input v-model="langfuseForm.public_key" class="form-input" :placeholder="langfuseConfig.public_key || 'pk-lf-...'" />
            </div>
            <div class="form-row">
              <label class="form-label">密钥 (Secret Key)</label>
              <div class="input-group">
                <input v-model="langfuseForm.secret_key" :type="langfuseShowSecret ? 'text' : 'password'" class="form-input" placeholder="留空保持不变" />
                <button type="button" class="input-toggle" @click="langfuseShowSecret = !langfuseShowSecret">{{ langfuseShowSecret ? '隐藏' : '显示' }}</button>
              </div>
            </div>
            <div class="form-row">
              <label class="form-label">Host (可选)</label>
              <input v-model="langfuseForm.host" class="form-input" placeholder="https://cloud.langfuse.com" />
            </div>
            <div class="form-actions">
              <button class="btn-primary" :disabled="langfuseSaving" @click="saveLangfuseConfig">
                {{ langfuseSaving ? '保存中...' : '保存配置' }}
              </button>
            </div>
          </div>
        </div>

        <!-- ─── DISCUSSION SETTINGS ───────────────────────────────────── -->
        <div v-if="activeTab === 'discussion'" class="tab-pane">
          <h2 class="pane-title">讨论设置</h2>
          <div v-if="discMsg" class="msg-box" :class="discMsg.success ? 'msg-ok' : 'msg-err'">{{ discMsg.message }}</div>

          <div class="section-box">
            <div class="section-head">并发控制</div>
            <div class="form-row">
              <label class="form-label">最大并发讨论数</label>
              <input v-model.number="discForm.max_concurrent" type="number" min="1" max="10" class="form-input form-input--short" />
              <span class="form-hint">同时运行的讨论上限（默认 2）</span>
            </div>
            <div class="form-actions">
              <button class="btn-primary" :disabled="discSaving || !discHasChanges" @click="saveDiscConfig">
                {{ discSaving ? '保存中...' : '保存更改' }}
              </button>
            </div>
          </div>

          <div class="section-box">
            <div class="section-head">阶段负责人</div>
            <p class="form-hint mb-3">每个阶段的负责人将主持讨论</p>
            <div v-for="stage in STAGE_TEMPLATES" :key="stage.id" class="moderator-row">
              <div class="moderator-label">
                <div class="font-medium text-sm">{{ stage.label }}</div>
                <div class="text-xs text-zinc-500">{{ stage.id }}</div>
              </div>
              <div class="flex items-center gap-2">
                <span v-if="discModSaved[stage.id]" class="text-xs text-emerald-400">✓ 已保存</span>
                <select v-model="discModerators[stage.id]" @change="saveDiscModerator(stage.id)" class="form-select">
                  <option v-for="agent in AGENT_OPTIONS" :key="agent.value" :value="agent.value">{{ agent.label }}</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- ─── DATA MANAGEMENT ──────────────────────────────────────── -->
        <div v-if="activeTab === 'data'" class="tab-pane">
          <div class="pane-header">
            <h2 class="pane-title">数据管理</h2>
            <button class="btn-secondary" @click="loadDiscussions(); loadProjects()">刷新</button>
          </div>

          <div class="tab-bar">
            <button class="tab-btn" :class="{ 'tab-btn--active': dataTab === 'discussion' }" @click="dataTab = 'discussion'">
              讨论 <span class="tab-count">({{ dataDiscussions.length }})</span>
            </button>
            <button class="tab-btn" :class="{ 'tab-btn--active': dataTab === 'project' }" @click="dataTab = 'project'">
              项目 <span class="tab-count">({{ dataProjects.length }})</span>
            </button>
          </div>

          <div class="search-row">
            <input v-model="dataSearch" class="form-input" placeholder="搜索..." />
          </div>

          <!-- Discussions -->
          <div v-if="dataTab === 'discussion'">
            <div v-if="dataLoadingDisc" class="empty-text">加载中...</div>
            <div v-else-if="dataFilteredDisc.length === 0" class="empty-text">暂无讨论</div>
            <div v-else class="data-list">
              <div v-for="item in dataFilteredDisc" :key="item.id" class="data-row">
                <div class="data-info">
                  <div class="data-name">
                    {{ item.topic }}
                    <span v-if="item.archived" class="tag tag-muted">已归档</span>
                  </div>
                  <div class="data-meta">
                    <span v-if="item.owner_name">{{ item.owner_name }}</span>
                    <span>{{ formatDate(item.updated_at) }}</span>
                    <span class="font-mono text-xs text-zinc-600">{{ item.id.slice(0, 8) }}</span>
                  </div>
                </div>
                <button class="btn-sm btn-red" @click="dataConfirmItem = item; dataConfirmType = 'discussion'">删除</button>
              </div>
            </div>
          </div>

          <!-- Projects -->
          <div v-if="dataTab === 'project'">
            <div v-if="dataLoadingProj" class="empty-text">加载中...</div>
            <div v-else-if="dataFilteredProj.length === 0" class="empty-text">暂无项目</div>
            <div v-else class="data-list">
              <div v-for="item in dataFilteredProj" :key="item.id" class="data-row">
                <div class="data-info">
                  <div class="data-name">
                    {{ item.name }}
                    <span class="tag" :class="item.is_public ? 'tag-green' : 'tag-muted'">{{ item.is_public ? '公开' : '私密' }}</span>
                  </div>
                  <div class="data-meta">
                    <span v-if="item.owner_name">{{ item.owner_name }}</span>
                    <span v-if="item.description" class="truncate max-w-xs">{{ item.description }}</span>
                  </div>
                </div>
                <button class="btn-sm btn-red" @click="dataConfirmItem = item; dataConfirmType = 'project'">删除</button>
              </div>
            </div>
          </div>
        </div>

        <!-- ─── AUDIT LOGS ─────────────────────────────────────────────── -->
        <div v-if="activeTab === 'logs'" class="tab-pane">
          <h2 class="pane-title">操作日志</h2>

          <div class="section-box">
            <div class="filters-row">
              <select v-model="logsFilters.action" @change="logsPage = 1; loadLogs()" class="form-select">
                <option value="">全部操作</option>
                <option value="login">登录</option>
                <option value="login_failed">登录失败</option>
                <option value="logout">退出</option>
                <option value="config_update">配置更新</option>
                <option value="config_delete">配置删除</option>
              </select>
              <input v-model="logsFilters.username" @input="logsDebouncedLoad" class="form-input" placeholder="按用户名筛选" />
              <input v-model="logsFilters.start_date" @change="logsPage = 1; loadLogs()" type="date" class="form-input" />
              <input v-model="logsFilters.end_date" @change="logsPage = 1; loadLogs()" type="date" class="form-input" />
              <button class="btn-secondary btn-sm" @click="logsClearFilters">清除</button>
            </div>
          </div>

          <div v-if="logsLoading" class="empty-text">加载中...</div>
          <div v-else-if="logsList.length === 0" class="empty-text">暂无日志</div>
          <div v-else class="section-box logs-table-wrap">
            <table class="logs-table">
              <thead>
                <tr>
                  <th>时间</th><th>操作</th><th>用户</th><th>目标</th><th>IP</th><th>详情</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in logsList" :key="log.id">
                  <td>{{ formatDate(log.timestamp) }}</td>
                  <td><span class="log-badge" :class="logBadgeClass(log.action)">{{ formatAction(log.action) }}</span></td>
                  <td>{{ log.username }}</td>
                  <td>{{ log.target || '-' }}</td>
                  <td class="font-mono text-xs">{{ log.ip_address || '-' }}</td>
                  <td>
                    <button v-if="log.before_value || log.after_value || log.details" class="link-btn" @click="logsSelected = log">查看</button>
                    <span v-else class="text-zinc-600">-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          <div v-if="logsTotalPages > 1" class="pagination-row">
            <span class="text-sm text-zinc-400">共 {{ logsTotalItems }} 条</span>
            <button class="btn-sm btn-secondary" :disabled="logsPage === 1" @click="logsGoPage(logsPage - 1)">上一页</button>
            <span class="text-sm">{{ logsPage }} / {{ logsTotalPages }}</span>
            <button class="btn-sm btn-secondary" :disabled="logsPage === logsTotalPages" @click="logsGoPage(logsPage + 1)">下一页</button>
          </div>
        </div>

      </div><!-- /settings-content -->
    </div><!-- /settings-body -->

    <!-- Data delete confirm modal -->
    <Transition name="fade">
      <div v-if="dataConfirmItem" class="modal-overlay" @click.self="dataConfirmItem = null">
        <div class="modal-box">
          <div class="modal-title">确认删除</div>
          <p class="modal-body">
            即将永久删除{{ dataConfirmType === 'discussion' ? '讨论' : '项目' }}：<br>
            <strong>「{{ dataConfirmType === 'discussion' ? dataConfirmItem.topic : dataConfirmItem.name }}」</strong>
          </p>
          <p class="modal-warn">此操作不可撤销，所有相关数据将被删除。</p>
          <div class="modal-actions">
            <button class="btn-secondary" @click="dataConfirmItem = null">取消</button>
            <button class="btn-danger" :disabled="dataDeleting" @click="doDataDelete">
              {{ dataDeleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Log detail modal -->
    <Transition name="fade">
      <div v-if="logsSelected" class="modal-overlay" @click.self="logsSelected = null">
        <div class="modal-box">
          <div class="modal-title">日志详情
            <button class="modal-close" @click="logsSelected = null">✕</button>
          </div>
          <div class="log-detail">
            <div v-if="logsSelected.before_value" class="detail-block detail-before">
              <div class="detail-label">修改前</div>{{ logsSelected.before_value }}
            </div>
            <div v-if="logsSelected.after_value" class="detail-block detail-after">
              <div class="detail-label">修改后</div>{{ logsSelected.after_value }}
            </div>
            <div v-if="logsSelected.details" class="detail-block">
              <div class="detail-label">详情</div>{{ logsSelected.details }}
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.settings-wrap {
  min-height: 100vh;
  background: #0f0f11;
  color: #e4e4e7;
  font-family: inherit;
}

.settings-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid #27272a;
  background: #18181b;
}
.back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #a1a1aa;
  cursor: pointer;
  background: none;
  border: none;
  padding: 4px 8px;
  border-radius: 6px;
  transition: color 0.15s;
}
.back-btn:hover { color: #fff; }
.settings-title { font-size: 18px; font-weight: 700; }
.settings-user { margin-left: auto; font-size: 13px; color: #71717a; }

.settings-body {
  display: flex;
  min-height: calc(100vh - 57px);
}

.settings-nav {
  width: 160px;
  flex-shrink: 0;
  background: #18181b;
  border-right: 1px solid #27272a;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-item {
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  font-size: 13px;
  border-radius: 6px;
  background: none;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
  transition: all 0.15s;
}
.nav-item:hover { background: #27272a; color: #fff; }
.nav-item--active { background: #3f3f46; color: #fff; font-weight: 600; }

.settings-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  max-width: 860px;
}

.tab-pane { display: flex; flex-direction: column; gap: 16px; }

.pane-title { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
.pane-header { display: flex; align-items: center; justify-content: space-between; }

.section-box {
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 10px;
  padding: 16px;
}
.section-box--bordered { border-color: #52525b; }
.section-head { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #e4e4e7; }

.status-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.status-card {
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.status-label { font-size: 13px; color: #a1a1aa; }
.status-badge {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  font-weight: 500;
}
.badge-ok { background: rgba(16,185,129,0.15); color: #34d399; }
.badge-warn { background: rgba(234,179,8,0.15); color: #fbbf24; }
.badge-muted { background: #27272a; color: #71717a; }

.log-list { display: flex; flex-direction: column; gap: 6px; }
.log-row { display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
.log-user { color: #e4e4e7; }
.log-target { color: #71717a; }
.log-time { margin-left: auto; color: #52525b; }

.quick-links { display: flex; flex-wrap: wrap; gap: 8px; }
.quick-link {
  padding: 6px 14px;
  background: #27272a;
  border-radius: 6px;
  border: none;
  color: #a1a1aa;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.quick-link:hover { background: #3f3f46; color: #fff; }

/* Form elements */
.form-row { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.form-label { font-size: 13px; color: #a1a1aa; font-weight: 500; }
.form-hint { font-size: 12px; color: #71717a; }
.form-input {
  padding: 7px 12px;
  background: #27272a;
  border: 1px solid #3f3f46;
  border-radius: 6px;
  color: #e4e4e7;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
}
.form-input:focus { border-color: #71717a; }
.form-input--short { width: 100px; }
.form-select {
  padding: 7px 10px;
  background: #27272a;
  border: 1px solid #3f3f46;
  border-radius: 6px;
  color: #e4e4e7;
  font-size: 13px;
  outline: none;
}
.form-title { font-size: 15px; font-weight: 600; margin-bottom: 14px; }
.form-actions { display: flex; gap: 8px; justify-content: flex-end; padding-top: 12px; border-top: 1px solid #27272a; margin-top: 4px; }

.input-group { display: flex; gap: 6px; }
.input-group .form-input { flex: 1; }
.input-toggle {
  padding: 7px 12px;
  background: #27272a;
  border: 1px solid #3f3f46;
  border-radius: 6px;
  color: #a1a1aa;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

/* Buttons */
.btn-primary {
  padding: 7px 16px;
  background: #fff;
  color: #000;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-primary:hover { opacity: 0.9; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-secondary {
  padding: 7px 14px;
  background: #3f3f46;
  color: #e4e4e7;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-secondary:hover { background: #52525b; }
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-sm { padding: 4px 10px; font-size: 12px; border-radius: 5px; border: none; cursor: pointer; transition: all 0.12s; background: #3f3f46; color: #e4e4e7; }
.btn-sm:hover { background: #52525b; }
.btn-sm:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-green { background: rgba(16,185,129,0.15); color: #34d399; }
.btn-green:hover { background: rgba(16,185,129,0.25); }
.btn-red { background: rgba(239,68,68,0.15); color: #f87171; }
.btn-red:hover { background: rgba(239,68,68,0.25); }
.btn-danger { padding: 7px 16px; background: #dc2626; color: #fff; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; }
.btn-danger:hover { background: #b91c1c; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

/* Messages */
.msg-box { padding: 10px 14px; border-radius: 8px; font-size: 13px; }
.msg-ok { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); color: #34d399; }
.msg-err { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #f87171; }

/* Profile rows */
.profile-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.profile-info { display: flex; align-items: center; gap: 10px; }
.profile-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.dot-active { background: #34d399; }
.dot-inactive { background: #3f3f46; }
.profile-name { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.profile-sub { font-size: 12px; color: #71717a; margin-top: 2px; }
.profile-actions { display: flex; gap: 6px; flex-shrink: 0; }

.test-result { margin-top: 8px; padding: 8px 12px; border-radius: 6px; font-size: 12.5px; }
.test-ok { background: rgba(16,185,129,0.1); color: #34d399; }
.test-err { background: rgba(239,68,68,0.1); color: #f87171; }

/* Tags */
.tag { font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
.tag-green { background: rgba(16,185,129,0.15); color: #34d399; }
.tag-warn { background: rgba(234,179,8,0.15); color: #fbbf24; }
.tag-muted { background: #27272a; color: #71717a; }

/* Toggle */
.toggle-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.toggle-btn {
  position: relative;
  width: 44px; height: 24px;
  border-radius: 999px;
  border: none; cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
}
.toggle-on { background: #10b981; }
.toggle-off { background: #3f3f46; }
.toggle-thumb {
  position: absolute;
  top: 2px;
  width: 20px; height: 20px;
  border-radius: 50%;
  background: #fff;
  transition: left 0.2s;
}
.thumb-on { left: 22px; }
.thumb-off { left: 2px; }

/* Moderator */
.moderator-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #27272a;
}
.moderator-row:last-child { border-bottom: none; }
.moderator-label { flex: 1; }

/* Data management */
.tab-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.tab-btn { padding: 6px 14px; background: #27272a; color: #a1a1aa; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; }
.tab-btn--active { background: #fff; color: #000; font-weight: 600; }
.tab-count { opacity: 0.6; font-size: 11px; }
.search-row { margin-bottom: 12px; }
.data-list { display: flex; flex-direction: column; gap: 6px; }
.data-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 8px;
  gap: 12px;
}
.data-info { flex: 1; min-width: 0; }
.data-name { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.data-meta { font-size: 12px; color: #71717a; display: flex; gap: 10px; margin-top: 2px; }

/* Logs */
.logs-table-wrap { padding: 0; overflow-x: auto; }
.logs-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.logs-table th { padding: 10px 12px; text-align: left; color: #71717a; font-weight: 500; border-bottom: 1px solid #27272a; background: #18181b; }
.logs-table td { padding: 10px 12px; border-bottom: 1px solid #1f1f23; }
.logs-table tr:last-child td { border-bottom: none; }
.log-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.link-btn { background: none; border: none; color: #818cf8; cursor: pointer; font-size: 12px; }
.link-btn:hover { color: #a5b4fc; }
.filters-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.filters-row .form-input { flex: 1; min-width: 120px; }
.pagination-row { display: flex; align-items: center; gap: 10px; margin-top: 12px; }

/* Log detail */
.log-detail { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
.detail-block { padding: 10px; background: #0f0f11; border-radius: 6px; font-family: monospace; font-size: 12px; word-break: break-all; }
.detail-label { font-size: 11px; color: #71717a; margin-bottom: 4px; font-family: inherit; }
.detail-before { color: #f87171; }
.detail-after { color: #34d399; }

/* Modal */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.7);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.modal-box {
  background: #18181b;
  border: 1px solid #3f3f46;
  border-radius: 12px;
  padding: 24px;
  max-width: 440px;
  width: calc(100% - 32px);
}
.modal-title { font-size: 16px; font-weight: 700; display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.modal-close { background: none; border: none; color: #71717a; cursor: pointer; font-size: 16px; padding: 2px; }
.modal-body { color: #a1a1aa; font-size: 14px; margin-bottom: 8px; }
.modal-warn { color: #f87171; font-size: 13px; margin-bottom: 16px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }

/* Empty */
.empty-text { text-align: center; padding: 40px; color: #52525b; font-size: 14px; }

/* Fade transition */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.mb-3 { margin-bottom: 12px; }
.ml-2 { margin-left: 8px; }
</style>
