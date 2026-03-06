import { createApp } from 'vue';
import { createPinia } from 'pinia';
import './style.css';
import App from './App.vue';
import router from './router';
import { useUserStore } from './stores/user'

const app = createApp(App);

const pinia = createPinia();
app.use(pinia);
app.use(router);

// Await init before mount — ensures user.value is populated before router guard runs
const userStore = useUserStore(pinia)
await userStore.init()

// Expose router for WebMCP bridge
;(window as any).__vue_router = router

app.mount('#app');

// WebMCP tools for AI testing
import { initWebMCP } from './webmcp'
initWebMCP()
