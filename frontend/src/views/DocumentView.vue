<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const doc = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/documents/${route.params.docId}`, {
      headers: { Authorization: `Bearer ${userStore.accessToken}` },
    })
    if (res.ok) doc.value = await res.json()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="doc-view">
    <header class="doc-header">
      <button class="back-btn" @click="router.back()">← 返回</button>
      <h1 v-if="doc">{{ doc.title }}</h1>
    </header>
    <div v-if="loading" class="doc-loading">加载中...</div>
    <div v-else-if="doc" class="doc-content">
      <pre>{{ doc.content }}</pre>
    </div>
    <div v-else class="doc-loading">文档未找到</div>
  </div>
</template>

<style scoped>
.doc-view { min-height: 100vh; background: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
.doc-header { display: flex; align-items: center; gap: 16px; padding: 16px 24px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.doc-header h1 { font-size: 20px; font-weight: 700; margin: 0; }
.back-btn { background: none; border: none; color: #4f46e5; font-size: 14px; cursor: pointer; }
.doc-loading { text-align: center; padding: 60px; color: #9ca3af; }
.doc-content { max-width: 800px; margin: 24px auto; background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.doc-content pre { white-space: pre-wrap; font-size: 14px; line-height: 1.6; }
</style>
