<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHall } from '@/composables/useHall'
import { useUserStore } from '@/stores/user'
import UserMenu from '@/components/layout/UserMenu.vue'
import LoginModal from '@/components/auth/LoginModal.vue'

const router = useRouter()
const userStore = useUserStore()
const { items, loading, refresh, createProject } = useHall()

const showLoginModal = ref(false)
const showNewDiscussion = ref(false)
const showNewProject = ref(false)
const newDiscussionTopic = ref('')
const newProjectName = ref('')
const creating = ref(false)

const emit = defineEmits<{
  (e: 'open-panel', section: string): void
}>()

onMounted(async () => {
  if (!userStore.isAuthenticated) {
    await userStore.init()
  }
  if (userStore.isAuthenticated) {
    await refresh()
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
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/discussions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userStore.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ topic: newDiscussionTopic.value.trim() }),
    })
    if (!res.ok) throw new Error('Failed')
    const data = await res.json()
    showNewDiscussion.value = false
    newDiscussionTopic.value = ''
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
    const data = await createProject(newProjectName.value.trim())
    showNewProject.value = false
    newProjectName.value = ''
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
</script>

<template>
  <div class="hall">
    <header class="hall-header">
      <h1 class="hall-title">BW-Work</h1>
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
    <div v-else class="hall-grid">
      <div
        v-for="item in items"
        :key="`${item.type}-${item.id}`"
        class="hall-card"
        @click="onCardClick(item)"
      >
        <div class="card-header">
          <span class="card-icon">{{ item.type === 'discussion' ? '💬' : '📁' }}</span>
          <span class="card-type-badge" :class="item.type">{{ item.type === 'discussion' ? '讨论' : '项目' }}</span>
        </div>
        <h3 class="card-title">{{ item.name }}</h3>
        <p class="card-desc" v-if="item.description">{{ item.description }}</p>
        <div class="card-footer">
          <span v-if="item.type === 'discussion' && item.extra?.owner_name" class="card-meta">
            {{ item.extra.owner_name }}
          </span>
          <span v-if="item.type === 'discussion' && item.extra?.message_count != null" class="card-meta">
            {{ item.extra.message_count }} 条消息
          </span>
          <span v-if="item.type === 'project' && item.extra?.stage_progress" class="card-meta">
            进度 {{ item.extra.stage_progress }}
          </span>
          <span class="card-time">{{ formatTime(item.updated_at) }}</span>
        </div>
      </div>
    </div>

    <!-- New Discussion Dialog -->
    <Transition name="fade">
      <div v-if="showNewDiscussion" class="dialog-overlay" @click.self="showNewDiscussion = false">
        <div class="dialog">
          <h3>新建讨论</h3>
          <input
            v-model="newDiscussionTopic"
            placeholder="讨论主题..."
            class="dialog-input"
            @keyup.enter="doCreateDiscussion"
            autofocus
          />
          <div class="dialog-actions">
            <button class="btn btn-secondary" @click="showNewDiscussion = false">取消</button>
            <button class="btn btn-primary" @click="doCreateDiscussion" :disabled="creating">创建</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- New Project Dialog -->
    <Transition name="fade">
      <div v-if="showNewProject" class="dialog-overlay" @click.self="showNewProject = false">
        <div class="dialog">
          <h3>新建项目</h3>
          <input
            v-model="newProjectName"
            placeholder="项目名称..."
            class="dialog-input"
            @keyup.enter="doCreateProject"
            autofocus
          />
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
  background: #f9fafb;
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
  gap: 10px;
}
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
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
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
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  transform: translateY(-1px);
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
  background: #eff6ff;
  color: #3b82f6;
}
.card-type-badge.project {
  background: #f0fdf4;
  color: #10b981;
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
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
