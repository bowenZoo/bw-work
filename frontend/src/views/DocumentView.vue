<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const doc = ref<any>(null)
const versions = ref<any[]>([])
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const editContent = ref('')
const editTitle = ref('')
const showVersions = ref(false)
const previewVersion = ref<any>(null)

const apiBase = import.meta.env.VITE_API_BASE || ''
function authHeaders(json = false): Record<string, string> {
  const h: Record<string, string> = { Authorization: `Bearer ${userStore.accessToken}` }
  if (json) h['Content-Type'] = 'application/json'
  return h
}

async function fetchDoc() {
  loading.value = true
  try {
    const res = await fetch(`${apiBase}/api/docs/${route.params.docId}`, { headers: authHeaders() })
    if (res.ok) {
      doc.value = await res.json()
      editContent.value = doc.value.content || ''
      editTitle.value = doc.value.title || ''
    }
  } finally { loading.value = false }
}

async function fetchVersions() {
  const res = await fetch(`${apiBase}/api/docs/${route.params.docId}/versions`, { headers: authHeaders() })
  if (res.ok) versions.value = await res.json()
}

async function save() {
  if (saving.value) return
  saving.value = true
  try {
    const body: any = { content: editContent.value }
    if (editTitle.value !== doc.value.title) body.title = editTitle.value
    const res = await fetch(`${apiBase}/api/docs/${route.params.docId}`, {
      method: 'PUT', headers: authHeaders(true), body: JSON.stringify(body)
    })
    if (res.ok) { doc.value = await res.json(); editing.value = false; await fetchVersions() }
  } finally { saving.value = false }
}

async function revertTo(versionId: string) {
  const res = await fetch(`${apiBase}/api/docs/${route.params.docId}/revert/${versionId}`, {
    method: 'POST', headers: authHeaders()
  })
  if (res.ok) {
    doc.value = await res.json()
    editContent.value = doc.value.content || ''
    editTitle.value = doc.value.title || ''
    previewVersion.value = null
    await fetchVersions()
  }
}

function startEdit() { editContent.value = doc.value.content || ''; editTitle.value = doc.value.title || ''; editing.value = true }
function cancelEdit() { editing.value = false; editContent.value = doc.value.content || ''; editTitle.value = doc.value.title || '' }
function toggleVersions() { showVersions.value = !showVersions.value; if (showVersions.value && versions.value.length === 0) fetchVersions() }
function formatTime(dt: string) { if (!dt) return ''; return new Date(dt).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }
const lineCount = computed(() => (editContent.value || '').split('\n').length)

function exportMarkdown() {
  if (!doc.value) return
  const content = `# ${doc.value.title}\n\n${doc.value.content || ''}`
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${doc.value.title || 'document'}.md`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => { await fetchDoc(); await fetchVersions() })
</script>

<template>
  <div class="doc-view">
    <header class="doc-header">
      <button class="back-btn" @click="router.back()">← 返回</button>
      <div class="doc-info" v-if="doc">
        <input v-if="editing" v-model="editTitle" class="title-input" placeholder="文档标题" />
        <h1 v-else>{{ doc.title }}</h1>
        <span class="version-badge">v{{ doc.current_version }}</span>
      </div>
      <div class="header-actions" v-if="doc">
        <button v-if="!editing" class="btn btn-export" @click="exportMarkdown">导出 Markdown</button>
        <button v-if="!editing" class="btn btn-secondary" @click="toggleVersions">📋 历史 ({{ versions.length }})</button>
        <button v-if="!editing" class="btn btn-primary" @click="startEdit">✏️ 编辑</button>
        <button v-if="editing" class="btn btn-secondary" @click="cancelEdit">取消</button>
        <button v-if="editing" class="btn btn-primary" @click="save" :disabled="saving">{{ saving ? '保存中...' : '💾 保存' }}</button>
      </div>
    </header>

    <div v-if="loading" class="doc-loading">加载中...</div>

    <div v-else-if="doc" class="doc-body">
      <aside v-if="showVersions" class="version-panel">
        <h3>版本历史</h3>
        <div v-for="v in versions" :key="v.id" class="version-item"
             :class="{ active: previewVersion?.id === v.id, current: v.version === doc.current_version }"
             @click="previewVersion = previewVersion?.id === v.id ? null : v">
          <div class="v-header">
            <span class="v-num">v{{ v.version }}</span>
            <span class="v-time">{{ formatTime(v.created_at) }}</span>
          </div>
          <div class="v-source">{{ v.source_type === 'manual' ? '手动编辑' : v.source_type === 'adoption' ? '讨论采纳' : v.source_type }}</div>
          <button v-if="v.version !== doc.current_version" class="v-revert" @click.stop="revertTo(v.id)">回退到此版本</button>
        </div>
      </aside>

      <main class="doc-content" :class="{ 'with-panel': showVersions }">
        <div v-if="previewVersion" class="preview-banner">
          👁️ 预览 v{{ previewVersion.version }} —
          <button @click="previewVersion = null">关闭预览</button>
          <button @click="revertTo(previewVersion.id)">回退到此版本</button>
        </div>
        <textarea v-if="editing" v-model="editContent" class="content-editor" placeholder="在这里编写文档内容..." />
        <div v-else-if="previewVersion" class="content-display">
          <div v-if="previewVersion.content" class="markdown-body" v-html="marked.parse(previewVersion.content)" />
          <div v-else class="empty-doc">此版本无内容</div>
        </div>
        <div v-else class="content-display">
          <div v-if="doc.content" class="markdown-body" v-html="marked.parse(doc.content)" />
          <div v-else class="empty-doc">文档还没有内容，点击「编辑」开始编写</div>
        </div>
        <div v-if="editing" class="editor-footer"><span class="line-count">{{ lineCount }} 行</span></div>
      </main>
    </div>

    <div v-else class="doc-loading">文档未找到</div>
  </div>
</template>

<style scoped>
.doc-view { min-height: 100vh; background: #FFFBF5; font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; display: flex; flex-direction: column; }
.doc-header { display: flex; align-items: center; gap: 16px; padding: 12px 24px; background: #FFFFFF; box-shadow: 0 1px 4px #0000000A; position: sticky; top: 0; z-index: 10; }
.back-btn { background: none; border: none; color: #374151; font-size: 14px; cursor: pointer; white-space: nowrap; }
.back-btn:hover { text-decoration: underline; }
.doc-info { flex: 1; display: flex; align-items: center; gap: 8px; }
.doc-info h1 { font-size: 18px; font-weight: 700; margin: 0; color: #1F2937; }
.title-input { flex: 1; font-size: 18px; font-weight: 700; border: 1px solid #D1D5DB; border-radius: 6px; padding: 4px 8px; color: #1F2937; }
.title-input:focus { outline: none; border-color: #7C3AED; }
.version-badge { background: #EDE9FE; color: #7C3AED; font-size: 12px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.header-actions { display: flex; gap: 8px; white-space: nowrap; }
.btn { padding: 6px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; font-weight: 500; transition: all 0.15s; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #7C3AED; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #6D28D9; }
.btn-secondary { background: #F3F4F6; color: #374151; border: 1px solid #D1D5DB; }
.btn-secondary:hover { background: #E5E7EB; }
.btn-export { background: #FFFFFF; color: #6B7280; border: 1px solid #D1D5DB; font-size: 12px; padding: 4px 10px; }
.btn-export:hover { color: #7C3AED; border-color: #7C3AED; background: #EDE9FE; }
.doc-loading { text-align: center; padding: 60px; color: #9CA3AF; font-size: 15px; }
.doc-body { flex: 1; display: flex; overflow: hidden; }
.version-panel { width: 260px; background: #FFFFFF; border-right: 1px solid #E5E7EB; padding: 16px; overflow-y: auto; flex-shrink: 0; }
.version-panel h3 { font-size: 14px; font-weight: 600; margin: 0 0 12px; color: #374151; }
.version-item { padding: 10px; border-radius: 8px; margin-bottom: 6px; cursor: pointer; border: 1px solid #E5E7EB; transition: all 0.15s; }
.version-item:hover { background: #FFFBF5; }
.version-item.active { border-color: #7C3AED; background: #EDE9FE; }
.version-item.current { border-left: 3px solid #22C55E; }
.v-header { display: flex; justify-content: space-between; align-items: center; }
.v-num { font-weight: 700; font-size: 13px; color: #18181B; }
.v-time { font-size: 11px; color: #9CA3AF; }
.v-source { font-size: 11px; color: #6B7280; margin-top: 4px; }
.v-revert { margin-top: 6px; font-size: 11px; color: #7C3AED; background: none; border: none; cursor: pointer; padding: 0; }
.v-revert:hover { text-decoration: underline; }
.doc-content { flex: 1; padding: 24px; max-width: 900px; margin: 0 auto; width: 100%; }
.doc-content.with-panel { margin: 0; }
.preview-banner { background: #FEF3C7; border: 1px solid #D97706; border-radius: 8px; padding: 8px 16px; margin-bottom: 16px; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.preview-banner button { background: none; border: none; color: #7C3AED; cursor: pointer; font-size: 12px; text-decoration: underline; }
.content-display { background: #FFFFFF; border-radius: 12px; padding: 32px; box-shadow: 0 1px 3px #0000000A; min-height: 400px; }
.content-display pre { white-space: pre-wrap; word-wrap: break-word; font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.8; color: #374151; margin: 0; }
.markdown-body { font-size: 14px; line-height: 1.8; color: #374151; }
.markdown-body h1 { font-size: 1.875em; font-weight: 700; margin: 0 0 16px; color: #1F2937; border-bottom: 2px solid #E5E7EB; padding-bottom: 8px; }
.markdown-body h2 { font-size: 1.5em; font-weight: 700; margin: 24px 0 12px; color: #1F2937; border-bottom: 1px solid #E5E7EB; padding-bottom: 6px; }
.markdown-body h3 { font-size: 1.25em; font-weight: 600; margin: 20px 0 10px; color: #1F2937; }
.markdown-body h4 { font-size: 1.1em; font-weight: 600; margin: 16px 0 8px; color: #374151; }
.markdown-body p { margin: 0 0 12px; }
.markdown-body ul, .markdown-body ol { margin: 0 0 12px; padding-left: 2em; }
.markdown-body li { margin-bottom: 4px; }
.markdown-body ul li { list-style-type: disc; }
.markdown-body ol li { list-style-type: decimal; }
.markdown-body code { background: #F3F4F6; color: #e11d48; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.875em; padding: 2px 5px; border-radius: 4px; }
.markdown-body pre { background: #1F2937; color: #f9fafb; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 0 0 16px; }
.markdown-body pre code { background: none; color: inherit; padding: 0; font-size: 0.875em; }
.markdown-body blockquote { border-left: 4px solid #D1D5DB; padding-left: 16px; margin: 0 0 12px; color: #6B7280; }
.markdown-body table { width: 100%; border-collapse: collapse; margin: 0 0 16px; font-size: 14px; }
.markdown-body th { background: #F3F4F6; font-weight: 600; text-align: left; padding: 8px 12px; border: 1px solid #D1D5DB; color: #374151; }
.markdown-body td { padding: 8px 12px; border: 1px solid #E5E7EB; vertical-align: top; }
.markdown-body tr:nth-child(even) td { background: #FFFBF5; }
.markdown-body a { color: #7C3AED; text-decoration: underline; }
.markdown-body hr { border: none; border-top: 1px solid #E5E7EB; margin: 24px 0; }
.markdown-body strong { font-weight: 700; color: #1F2937; }
.markdown-body em { font-style: italic; }
.content-editor { width: 100%; min-height: 500px; background: #FFFFFF; border: 2px solid #7C3AED; border-radius: 12px; padding: 24px; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 14px; line-height: 1.8; color: #374151; resize: vertical; box-sizing: border-box; }
.content-editor:focus { outline: none; border-color: #6D28D9; }
.editor-footer { display: flex; justify-content: flex-end; padding: 8px 0; }
.line-count { font-size: 12px; color: #9CA3AF; }
.empty-doc { text-align: center; padding: 60px 20px; color: #9CA3AF; font-size: 15px; }

@media (max-width: 768px) {
  .doc-header {
    padding: 10px 12px;
    gap: 8px;
    flex-wrap: wrap;
  }
  .doc-info {
    flex: 1 1 100%;
    order: 2;
  }
  .doc-info h1 {
    font-size: 16px;
  }
  .title-input {
    font-size: 16px;
  }
  .back-btn {
    order: 1;
  }
  .header-actions {
    order: 3;
    flex-wrap: wrap;
    gap: 6px;
    width: 100%;
  }
  .header-actions .btn {
    flex: 1;
    min-width: 0;
    text-align: center;
    padding: 6px 8px;
    font-size: 12px;
  }
  .doc-body {
    flex-direction: column;
  }
  .version-panel {
    width: 100%;
    max-height: 50vh;
    border-right: none;
    border-bottom: 1px solid #E5E7EB;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 20;
    border-radius: 16px 16px 0 0;
    box-shadow: 0 -4px 20px rgba(0,0,0,0.15);
  }
  .doc-content {
    padding: 16px 12px;
  }
  .content-display {
    padding: 20px 16px;
  }
  .content-editor {
    padding: 16px;
    min-height: 300px;
  }
}
</style>
