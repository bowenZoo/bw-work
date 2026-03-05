import { ref } from 'vue'
import { useUserStore } from '@/stores/user'

export interface StageDocument {
  id: string
  title: string
  content: string
  current_version: number
  created_at: string
  updated_at: string
}

export interface StageDiscussion {
  id: string
  topic: string
  owner_name: string
  status: string
  message_count: number
  created_at: string
}

export interface Stage {
  id: string
  name: string
  status: 'completed' | 'active' | 'locked'
  sort_order: number
  prerequisites: string[]
  documents: StageDocument[]
  discussions: StageDiscussion[]
}

export interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

export function useProjectDetail(projectId: () => string) {
  const project = ref<Project | null>(null)
  const stages = ref<Stage[]>([])
  const loading = ref(false)
  const userStore = useUserStore()

  function apiHeaders(): Record<string, string> {
    return {
      Authorization: `Bearer ${userStore.accessToken}`,
      'Content-Type': 'application/json',
    }
  }

  async function refresh() {
    loading.value = true
    try {
      const base = import.meta.env.VITE_API_BASE || ''
      const res = await fetch(`${base}/api/projects/${projectId()}/detail`, {
        headers: apiHeaders(),
      })
      if (!res.ok) throw new Error(`Project detail fetch failed: ${res.status}`)
      const data = await res.json()
      project.value = data.project
      stages.value = data.stages || []
    } catch (e) {
      console.error('useProjectDetail refresh error:', e)
    } finally {
      loading.value = false
    }
  }

  async function completeStage(stageId: string) {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects/${projectId()}/stages/${stageId}/complete`, {
      method: 'POST',
      headers: apiHeaders(),
    })
    if (!res.ok) throw new Error(`Complete stage failed: ${res.status}`)
    const data = await res.json()
    await refresh()
    return data
  }

  async function createDocument(stageId: string, title: string, content: string = '') {
    const base = import.meta.env.VITE_API_BASE || ''
    const res = await fetch(`${base}/api/projects/${projectId()}/stages/${stageId}/documents`, {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ title, content }),
    })
    if (!res.ok) throw new Error(`Create document failed: ${res.status}`)
    const data = await res.json()
    await refresh()
    return data
  }

  return { project, stages, loading, refresh, completeStage, createDocument }
}
