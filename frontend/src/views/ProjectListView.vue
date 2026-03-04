<template>
  <div class="project-list-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-left">
        <h1 class="app-title">BW-Work</h1>
        <span class="app-subtitle">AI 策划工作空间</span>
      </div>
      <div v-if="userStore.isAuthenticated" class="header-right">
        <span class="user-name">{{ userStore.user?.display_name || userStore.user?.username }}</span>
        <span v-if="userStore.isAdmin" class="role-tag">管理员</span>
        <button class="btn-text" @click="userStore.logout(); $router.push('/')">退出</button>
      </div>
    </header>

    <!-- Content -->
    <main class="page-content">
      <div class="section-header">
        <h2>我的项目</h2>
        <button v-if="userStore.isAdmin" class="btn-primary" @click="showCreateDialog = true">
          + 新建项目
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading && userStore.isAuthenticated" class="loading">加载中...</div>

      <!-- Project grid -->
      <div v-else-if="projects.length > 0" class="project-grid">
        <div
          v-for="p in projects"
          :key="p.id"
          class="project-card"
          @click="$router.push(`/project/${p.id}`)"
        >
          <div class="card-icon">{{ p.name.charAt(0).toUpperCase() }}</div>
          <div class="card-body">
            <h3>{{ p.name }}</h3>
            <p class="card-desc">{{ p.description || '暂无描述' }}</p>
            <div class="card-meta">
              <span v-if="p.is_public" class="badge-public">公共</span>
              <span v-else class="badge-private">私有</span>
              <span class="badge-count">{{ p.discussion_count || 0 }} 个讨论</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty -->
      <div v-else class="empty-state">
        <p class="empty-title">暂无可访问的项目</p>
        <p class="empty-desc" v-if="!userStore.isAdmin">请联系管理员将你加入项目</p>
        <button v-if="userStore.isAdmin" class="btn-primary" @click="showCreateDialog = true">
          创建第一个项目
        </button>
      </div>
    </main>

    <!-- Create dialog -->
    <div v-if="showCreateDialog" class="modal-mask" @click.self="showCreateDialog = false">
      <div class="modal-content">
        <h2>新建项目</h2>
        <div class="form-group">
          <label>项目名称</label>
          <input v-model="newProject.name" placeholder="例：Game Design" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <textarea v-model="newProject.description" placeholder="项目简介..." rows="2" />
        </div>
        <div class="form-group">
          <label>
            <input type="checkbox" v-model="newProject.is_public" />
            公共项目（所有用户可见）
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showCreateDialog = false">取消</button>
          <button class="btn-primary" @click="createProject" :disabled="!newProject.name.trim()">创建</button>
        </div>
      </div>
    </div>

    <!-- Login Modal (should not appear if guard works, but fallback) -->
    <LoginModal v-if="!userStore.isAuthenticated" :force="true" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import LoginModal from '@/components/auth/LoginModal.vue'

const userStore = useUserStore()

const loading = ref(true)
const projects = ref<any[]>([])
const showCreateDialog = ref(false)
const newProject = ref({ name: '', description: '', is_public: false })

function getAuthHeaders(): Record<string, string> {
  const raw = localStorage.getItem('bw_user_tokens')
  if (!raw) return {}
  try { return { Authorization: `Bearer ${JSON.parse(raw).access_token}` } }
  catch { return {} }
}

async function loadProjects(): Promise<void> {
  loading.value = true
  try {
    const res = await fetch('/api/projects', { headers: getAuthHeaders() })
    if (!res.ok) throw new Error('Failed')
    const data = await res.json()
    projects.value = data.projects || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function slugify(name: string): string {
  return name.toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 40) || 'project'
}

async function createProject() {
  const slug = slugify(newProject.value.name) + '-' + Math.random().toString(36).slice(2, 6)
  try {
    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ ...newProject.value, slug })
    })
    if (!res.ok) {
      const d = await res.json()
      alert(d.detail || 'Failed')
      return
    }
    const data = await res.json()
    showCreateDialog.value = false
    router.push(`/project/${data.id}`)
  } catch (e: any) {
    alert(e.message)
  }
}

onMounted(async () => {
  if (!userStore.isAuthenticated) {
    await userStore.init()
  }
  if (userStore.isAuthenticated) {
    await loadProjects()
  } else {
    loading.value = false
  }
})

// Bug fix: reload projects when user logs in (e.g. after register)
watch(() => userStore.isAuthenticated, async (val) => {
  if (val) {
    await loadProjects()
  }
})
</script>

<style scoped>
.project-list-page {
  min-height: 100vh;
  background: #f9fafb;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
}
.header-left { display: flex; align-items: baseline; gap: 12px; }
.app-title { font-size: 20px; font-weight: 700; margin: 0; }
.app-subtitle { font-size: 13px; color: #9ca3af; }
.header-right { display: flex; align-items: center; gap: 12px; }
.user-name { font-size: 14px; color: #374151; }
.role-tag { font-size: 11px; padding: 2px 8px; background: #dbeafe; color: #1d4ed8; border-radius: 4px; }
.btn-text { background: none; border: none; color: #6b7280; cursor: pointer; font-size: 13px; }
.btn-text:hover { color: #374151; }

.page-content { max-width: 960px; margin: 0 auto; padding: 32px 24px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.section-header h2 { font-size: 18px; margin: 0; }

.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.project-card {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.2s;
}
.project-card:hover { border-color: #3b82f6; box-shadow: 0 4px 12px rgba(59,130,246,0.1); }
.card-icon {
  width: 48px; height: 48px;
  background: #3b82f6;
  color: white;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 700;
  flex-shrink: 0;
}
.card-body h3 { margin: 0 0 4px; font-size: 15px; }
.card-desc { font-size: 13px; color: #6b7280; margin: 0 0 8px; }
.card-meta { display: flex; gap: 6px; }
.badge-public { font-size: 11px; padding: 2px 8px; background: #d1fae5; color: #065f46; border-radius: 4px; }
.badge-count { font-size: 11px; color: #9ca3af; }
.badge-private { font-size: 11px; padding: 2px 8px; background: #f3f4f6; color: #6b7280; border-radius: 4px; }

.empty-state { text-align: center; padding: 60px 20px; }
.empty-title { font-size: 16px; color: #374151; margin-bottom: 8px; }
.empty-desc { font-size: 13px; color: #9ca3af; margin-bottom: 16px; }

.loading { text-align: center; padding: 40px; color: #9ca3af; }

.btn-primary { padding: 8px 20px; border: none; border-radius: 8px; background: #3b82f6; color: white; cursor: pointer; font-size: 13px; font-weight: 500; }
.btn-primary:hover { background: #2563eb; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-cancel { padding: 8px 16px; border: 1px solid #e5e7eb; border-radius: 8px; background: white; cursor: pointer; font-size: 13px; }

.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; border-radius: 12px; padding: 24px; max-width: 420px; width: 90%; box-shadow: 0 8px 24px rgba(0,0,0,0.15); }
.modal-content h2 { margin: 0 0 16px; font-size: 18px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #374151; }
.form-group input[type="text"], .form-group input:not([type]), .form-group textarea {
  width: 100%; padding: 8px 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 13px; box-sizing: border-box;
}
.form-group input[type="checkbox"] { margin-right: 6px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px; }
</style>
