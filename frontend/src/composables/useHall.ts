import { ref } from 'vue'
import { useUserStore } from '@/stores/user'

export interface HallItem {
  type: 'discussion' | 'project'
  id: string
  name: string
  description: string
  updated_at: string
  extra: Record<string, any>
}

export function useHall() {
  const items = ref<HallItem[]>([])
  const loading = ref(false)
  const userStore = useUserStore()

  async function refresh() {
    loading.value = true
    try {
      const base = import.meta.env.VITE_API_BASE || ''
      const res = await fetch(`${base}/api/hall`, {
        headers: { Authorization: `Bearer ${userStore.accessToken}` },
      })
      if (!res.ok) throw new Error(`Hall fetch failed: ${res.status}`)
      const data = await res.json()
      items.value = data.items || []
    } catch (e) {
      console.error('useHall refresh error:', e)
    } finally {
      loading.value = false
    }
  }

  async function createProject(name: string): Promise<any> {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userStore.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name }),
    })
    if (!res.ok) throw new Error(`Create project failed: ${res.status}`)
    return res.json()
  }

  return { items, loading, refresh, createProject }
}
