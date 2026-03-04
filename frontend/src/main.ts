import { createApp } from 'vue';
import { createPinia } from 'pinia';
import './style.css';
import App from './App.vue';
import router from './router';

const app = createApp(App);

const pinia = createPinia();
app.use(pinia);
app.use(router);

// Init user store from localStorage before mount
import { useUserStore } from './stores/user'
const userStore = useUserStore(pinia)
userStore.init()

// Expose router for WebMCP bridge
;(window as any).__vue_router = router

app.mount('#app');

// WebMCP tools for AI testing
import { initWebMCP } from './webmcp'
initWebMCP()
