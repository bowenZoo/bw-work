import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import DiscussionView from '@/views/DiscussionView.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/discussion/:id?',
      name: 'discussion',
      component: DiscussionView,
    },
  ],
});

export default router;
