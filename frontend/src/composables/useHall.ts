import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { createCurrentDiscussion, getDiscussionStyles } from '@/api/discussion'
import type {
  AttachmentInfo,
  AgentConfig,
  DiscussionStyleFull,
  DiscussionStyleOverrides,
  CreateCurrentDiscussionResponse,
} from '@/types'

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

  // Discussion styles
  const discussionStylesFull = ref<DiscussionStyleFull[]>([])
  const defaultStyleId = ref('socratic')

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

  async function loadStyles() {
    try {
      const data = await getDiscussionStyles()
      discussionStylesFull.value = data.styles
      defaultStyleId.value = data.default
    } catch {
      discussionStylesFull.value = [
        { id: 'socratic', name: '苏格拉底式', description: '不断追问「为什么」，逼迫每个决策回到第一性原理', overrides: { goal: '', backstory: '', communication_style: '', focus_areas: [] } },
        { id: 'directive', name: '主策划主导制', description: '主策划提出框架，团队挑战补充，主策划有否决权', overrides: { goal: '', backstory: '', communication_style: '', focus_areas: [] } },
        { id: 'debate', name: '辩论制', description: '各策划独立提案，互相质疑辩论，主策划裁决', overrides: { goal: '', backstory: '', communication_style: '', focus_areas: [] } },
      ]
    }
  }

  async function createDiscussion(opts: {
    topic: string
    projectId?: string
    briefing?: string
    autoPauseInterval?: number
    attachment?: AttachmentInfo | null
    agents?: string[]
    agentConfigs?: Record<string, Partial<AgentConfig>>
    discussionStyle?: string
    password?: string
    customOverrides?: DiscussionStyleOverrides | null
  }): Promise<CreateCurrentDiscussionResponse> {
    const agentConfigsFinal = { ...(opts.agentConfigs || {}) }

    // Merge custom prompt overrides into agent_configs for lead_planner
    if (opts.customOverrides && opts.discussionStyle) {
      const defaultStyle = discussionStylesFull.value.find(s => s.id === opts.discussionStyle)
      const overridesChanged = defaultStyle && JSON.stringify(opts.customOverrides) !== JSON.stringify(defaultStyle.overrides)
      if (overridesChanged) {
        agentConfigsFinal['lead_planner'] = {
          ...(agentConfigsFinal['lead_planner'] || {}),
          ...opts.customOverrides,
        }
      }
    }

    // Clean empty configs
    const cleanConfigs: Record<string, Partial<AgentConfig>> = {}
    for (const [role, config] of Object.entries(agentConfigsFinal)) {
      const nonEmpty: Partial<AgentConfig> = {}
      for (const [key, val] of Object.entries(config)) {
        if (val !== undefined && val !== '' && !(Array.isArray(val) && val.length === 0)) {
          (nonEmpty as any)[key] = val
        }
      }
      if (Object.keys(nonEmpty).length > 0) {
        cleanConfigs[role] = nonEmpty
      }
    }

    return createCurrentDiscussion({
      topic: opts.topic,
      project_id: opts.projectId || undefined,
      briefing: opts.briefing || undefined,
      rounds: 10,
      auto_pause_interval: opts.autoPauseInterval ?? 5,
      attachment: opts.attachment || null,
      agents: opts.agents && opts.agents.length > 0 ? opts.agents : undefined,
      agent_configs: Object.keys(cleanConfigs).length > 0 ? cleanConfigs : undefined,
      discussion_style: opts.discussionStyle || undefined,
      password: opts.password || undefined,
    })
  }

  async function createProject(name: string, description?: string, isPublic?: boolean): Promise<any> {
    const base = import.meta.env.VITE_API_BASE || ''
    const body: Record<string, any> = { name }
    if (description) body.description = description
    if (isPublic !== undefined) body.is_public = isPublic
    const res = await fetch(`${base}/api/projects`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${userStore.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`Create project failed: ${res.status}`)
    return res.json()
  }

  return { items, loading, refresh, createProject, createDiscussion, loadStyles, discussionStylesFull, defaultStyleId }
}
