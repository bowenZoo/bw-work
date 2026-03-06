import { createRouter, createWebHistory } from 'vue-router'
import HallView from '@/views/HallView.vue'
import DiscussionView from '@/views/DiscussionView.vue'
import ProjectDetailView from '@/views/ProjectDetailView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'hall',
      component: HallView,
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/project/:projectId',
      name: 'project-detail',
      component: ProjectDetailView,
    },
    {
      path: '/project/:projectId/doc/:docId',
      name: 'document',
      component: () => import('@/views/DocumentView.vue'),
    },
    {
      path: '/discussion/:id',
      name: 'discussion',
      component: DiscussionView,
    },
    // Admin routes kept for backward compat
    {
      path: '/admin/login',
      name: 'admin-login',
      component: () => import('@/views/admin/LoginView.vue'),
      meta: { isAdminRoute: true },
    },
    {
      path: '/admin',
      component: () => import('@/views/admin/AdminLayout.vue'),
      meta: { isAdminRoute: true, requiresAuth: true },
      beforeEnter: async (to) => {
        const { useAdminStore } = await import('@/stores/admin')
        const adminStore = useAdminStore()
        if (!adminStore.isAuthenticated) {
          return { path: '/admin/login', query: { redirect: to.fullPath } }
        }
        return true
      },
      children: [
        { path: '', name: 'admin-dashboard', component: () => import('@/views/admin/DashboardView.vue') },
        { path: 'llm', name: 'admin-llm', component: () => import('@/views/admin/LlmConfigView.vue') },
        { path: 'langfuse', name: 'admin-langfuse', component: () => import('@/views/admin/LangfuseConfigView.vue') },
        { path: 'image', name: 'admin-image', component: () => import('@/views/admin/ImageConfigView.vue') },
        { path: 'discussion', name: 'admin-discussion', component: () => import('@/views/admin/DiscussionConfigView.vue') },
        { path: 'logs', name: 'admin-logs', component: () => import('@/views/admin/AuditLogView.vue') },
      ],
    },
    // Catch-all redirect
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// Auth guard
router.beforeEach(async (to) => {
  if (to.meta.isAdminRoute) return true

  const { useUserStore } = await import('@/stores/user')
  const userStore = useUserStore()

  // 已登录用户不能访问 /login，直接回大厅
  if (to.meta.guestOnly && userStore.isAuthenticated) {
    return { name: 'hall' }
  }

  // 未登录用户访问需要登录的页面，跳到 /login 并记录来源
  const publicRoutes = ['hall', 'login']
  if (!userStore.isAuthenticated && !publicRoutes.includes(to.name as string)) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  return true
})

export default router
