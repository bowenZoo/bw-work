import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import DiscussionView from '@/views/DiscussionView.vue';
import { useAdminStore } from '@/stores/admin';

// Lazy load project view
const ProjectView = () => import('@/views/ProjectView.vue');

// Lazy load admin views
const AdminLayout = () => import('@/views/admin/AdminLayout.vue');
const AdminLoginView = () => import('@/views/admin/LoginView.vue');
const AdminDashboardView = () => import('@/views/admin/DashboardView.vue');
const AdminLlmConfigView = () => import('@/views/admin/LlmConfigView.vue');
const AdminLangfuseConfigView = () => import('@/views/admin/LangfuseConfigView.vue');
const AdminImageConfigView = () => import('@/views/admin/ImageConfigView.vue');
const AdminAuditLogView = () => import('@/views/admin/AuditLogView.vue');

// Route guard for admin routes
function requireAdminAuth(to: RouteLocationNormalized) {
  const adminStore = useAdminStore();
  if (!adminStore.isAuthenticated) {
    return {
      path: '/admin/login',
      query: { redirect: to.fullPath },
    };
  }
  return true;
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/discussion',
      name: 'discussion',
      component: DiscussionView,
    },
    {
      path: '/discussion/:id',
      name: 'discussion-by-id',
      component: DiscussionView,
    },
    {
      path: '/history',
      redirect: '/',
    },
    {
      path: '/project/:id',
      name: 'project',
      component: ProjectView,
    },
    {
      path: '/discussion/:id/playback',
      redirect: (to) => ({ name: 'discussion-by-id', params: { id: to.params.id } }),
    },
    // Admin routes
    {
      path: '/admin/login',
      name: 'admin-login',
      component: AdminLoginView,
      meta: { isAdminRoute: true },
    },
    {
      path: '/admin',
      component: AdminLayout,
      meta: { isAdminRoute: true, requiresAuth: true },
      beforeEnter: requireAdminAuth,
      children: [
        {
          path: '',
          name: 'admin-dashboard',
          component: AdminDashboardView,
        },
        {
          path: 'llm',
          name: 'admin-llm',
          component: AdminLlmConfigView,
        },
        {
          path: 'langfuse',
          name: 'admin-langfuse',
          component: AdminLangfuseConfigView,
        },
        {
          path: 'image',
          name: 'admin-image',
          component: AdminImageConfigView,
        },
        {
          path: 'logs',
          name: 'admin-logs',
          component: AdminAuditLogView,
        },
      ],
    },
  ],
});

// Global navigation guard for token expiration
router.beforeEach(async (to) => {
  // Skip for non-admin routes
  if (!to.meta.isAdminRoute) {
    return true;
  }

  // Skip for login page
  if (to.name === 'admin-login') {
    return true;
  }

  // Check authentication
  const adminStore = useAdminStore();
  if (to.meta.requiresAuth && !adminStore.isAuthenticated) {
    return {
      path: '/admin/login',
      query: { redirect: to.fullPath },
    };
  }

  return true;
});

export default router;
