<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-white">讨论设置</h1>
      <p class="text-zinc-400 mt-1">配置讨论并发控制与阶段负责人</p>
    </div>

    <!-- Concurrent Config -->
    <div class="bg-zinc-800 rounded-lg p-6 space-y-6">
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">最大并发讨论数</label>
        <input
          v-model.number="form.max_concurrent"
          type="number" min="1" max="10"
          class="w-32 px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <p class="text-zinc-500 text-sm mt-1">同时运行的讨论数量上限，超出的将排队等待（默认 2）</p>
      </div>
      <div class="flex items-center justify-end pt-4 border-t border-zinc-700">
        <button @click="saveConfig" :disabled="saving || !hasChanges"
          class="px-4 py-2 bg-white text-black rounded-lg hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          <span v-if="saving">保存中...</span><span v-else>保存更改</span>
        </button>
      </div>
    </div>

    <!-- Stage Moderator Config -->
    <div class="bg-zinc-800 rounded-lg p-6">
      <h2 class="text-lg font-semibold text-white mb-1">阶段负责人</h2>
      <p class="text-zinc-400 text-sm mb-5">每个阶段的负责人将作为讨论主持，排在参与者列表第一位，主导开场、节奏控制与最终文档产出。</p>

      <div class="space-y-3">
        <div v-for="stage in STAGE_TEMPLATES" :key="stage.id" class="flex items-center justify-between gap-4 py-3 border-b border-zinc-700 last:border-0">
          <div>
            <div class="text-sm font-medium text-zinc-200">{{ stage.label }}</div>
            <div class="text-xs text-zinc-500">{{ stage.id }}</div>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-xs text-zinc-500" v-if="moderatorSaved[stage.id]">
              ✓ 已保存
            </span>
            <select
              v-model="moderators[stage.id]"
              @change="saveModerator(stage.id)"
              class="px-3 py-1.5 bg-zinc-700 border border-zinc-600 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-zinc-400"
            >
              <option v-for="agent in AGENT_OPTIONS" :key="agent.value" :value="agent.value">
                {{ agent.label }}
              </option>
            </select>
          </div>
        </div>
      </div>
    </div>

    <!-- Save Result -->
    <div v-if="saveResult" :class="['p-4 rounded-lg', saveResult.success ? 'bg-emerald-900/30 border border-emerald-700 text-emerald-300' : 'bg-red-900/30 border border-red-700 text-red-300']">
      <p>{{ saveResult.message }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

// ── Concurrent config ──────────────────────────────────────────────────────
const currentMaxConcurrent = ref(2)
const form = ref({ max_concurrent: 2 })
const saving = ref(false)
const saveResult = ref<{ success: boolean; message: string } | null>(null)
const hasChanges = computed(() => form.value.max_concurrent !== currentMaxConcurrent.value)

async function loadConfig() {
  try {
    const configs = await apiRequest<Array<{ category: string; key: string; value: string }>>('/config?category=discussion')
    const item = configs.find(c => c.key === 'max_concurrent')
    if (item) {
      const val = parseInt(item.value, 10)
      if (!isNaN(val) && val > 0) { currentMaxConcurrent.value = val; form.value.max_concurrent = val }
    }
  } catch {}
}

async function saveConfig() {
  saving.value = true; saveResult.value = null
  try {
    await apiRequest('/config/discussion/max_concurrent', { method: 'PUT', body: JSON.stringify({ value: String(form.value.max_concurrent), encrypted: false }) })
    currentMaxConcurrent.value = form.value.max_concurrent
    saveResult.value = { success: true, message: `并发数已更新为 ${form.value.max_concurrent}，立即生效` }
  } catch (error) {
    saveResult.value = { success: false, message: error instanceof Error ? error.message : '保存失败' }
  } finally { saving.value = false }
}

// ── Stage moderator config ─────────────────────────────────────────────────
const STAGE_TEMPLATES = [
  { id: 'concept',        label: '概念孵化' },
  { id: 'core-gameplay',  label: '核心玩法' },
  { id: 'art-style',      label: '美术风格' },
  { id: 'tech-prototype', label: '技术原型' },
  { id: 'system-design',  label: '系统设计' },
  { id: 'numbers',        label: '数值设计' },
  { id: 'ui-ux',          label: 'UI/UX' },
  { id: 'level-content',  label: '关卡与内容' },
  { id: 'art-assets',     label: '美术资产' },
  { id: 'default',        label: '默认（其他阶段）' },
]

const AGENT_OPTIONS = [
  { value: 'lead_planner',       label: '主策划' },
  { value: 'creative_director',  label: '创意总监' },
  { value: 'system_designer',    label: '系统策划' },
  { value: 'number_designer',    label: '数值策划' },
  { value: 'visual_concept',     label: '视觉概念设计师' },
  { value: 'market_director',    label: '市场总监' },
  { value: 'operations_analyst', label: '运营策划' },
  { value: 'player_advocate',    label: '玩家代言人' },
  { value: 'tech_director',      label: '技术总监' },
]

const moderators = ref<Record<string, string>>({})
const moderatorSaved = ref<Record<string, boolean>>({})

async function loadModerators() {
  try {
    const data = await apiRequest<{ moderators: Record<string, string> }>('/config/stage-moderators')
    moderators.value = data.moderators || {}
  } catch {}
}

async function saveModerator(templateId: string) {
  try {
    await apiRequest(`/config/stage-moderators/${templateId}`, {
      method: 'PUT',
      body: JSON.stringify({ role: moderators.value[templateId] }),
    })
    moderatorSaved.value[templateId] = true
    setTimeout(() => { moderatorSaved.value[templateId] = false }, 2000)
  } catch {
    saveResult.value = { success: false, message: `保存 ${templateId} 负责人失败` }
  }
}

onMounted(() => {
  loadConfig()
  loadModerators()
})
</script>
