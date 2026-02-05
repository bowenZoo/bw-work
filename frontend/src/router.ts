import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import DiscussionView from '@/views/DiscussionView.vue';
import HistoryView from '@/views/HistoryView.vue';

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
    {
      path: '/history',
      name: 'history',
      component: HistoryView,
    },
    {
      path: '/discussion/:id/playback',
      name: 'discussion-playback',
      component: DiscussionView,
      props: { mode: 'playback' },
    },
  ],
});

export default router;
