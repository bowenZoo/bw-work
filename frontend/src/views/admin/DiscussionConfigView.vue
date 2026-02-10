<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-white">讨论设置</h1>
      <p class="text-zinc-400 mt-1">配置讨论并发控制</p>
    </div>

    <!-- Configuration Form -->
    <div class="bg-zinc-800 rounded-lg p-6 space-y-6">
      <!-- Max Concurrent -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          最大并发讨论数
        </label>
        <input
          v-model.number="form.max_concurrent"
          type="number"
          min="1"
          max="10"
          class="w-32 px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <p class="text-zinc-500 text-sm mt-1">
          同时运行的讨论数量上限，超出的将排队等待（默认 2）
        </p>
      </div>

      <!-- Actions -->
      <div class="flex items-center justify-end pt-4 border-t border-zinc-700">
        <button
          @click="saveConfig"
          :disabled="saving || !hasChanges"
          class="px-4 py-2 bg-white text-black rounded-lg hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span v-if="saving">保存中...</span>
          <span v-else>保存更改</span>
        </button>
      </div>
    </div>

    <!-- Save Result -->
    <div
      v-if="saveResult"
      :class="[
        'p-4 rounded-lg',
        saveResult.success
          ? 'bg-emerald-900/30 border border-emerald-700 text-emerald-300'
          : 'bg-red-900/30 border border-red-700 text-red-300'
      ]"
    >
      <p>{{ saveResult.message }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

const currentMaxConcurrent = ref(2)

const form = ref({
  max_concurrent: 2,
})

const saving = ref(false)
const saveResult = ref<{ success: boolean; message: string } | null>(null)

const hasChanges = computed(() => {
  return form.value.max_concurrent !== currentMaxConcurrent.value
})

async function loadConfig() {
  try {
    const configs = await apiRequest<Array<{ category: string; key: string; value: string }>>('/config?category=discussion')
    const maxConcurrentItem = configs.find(c => c.key === 'max_concurrent')
    if (maxConcurrentItem) {
      const val = parseInt(maxConcurrentItem.value, 10)
      if (!isNaN(val) && val > 0) {
        currentMaxConcurrent.value = val
        form.value.max_concurrent = val
      }
    }
  } catch {
    // Config may not exist yet, use defaults
  }
}

async function saveConfig() {
  saving.value = true
  saveResult.value = null

  try {
    await apiRequest('/config/discussion/max_concurrent', {
      method: 'PUT',
      body: JSON.stringify({
        value: String(form.value.max_concurrent),
        encrypted: false,
      }),
    })

    currentMaxConcurrent.value = form.value.max_concurrent

    saveResult.value = {
      success: true,
      message: `并发数已更新为 ${form.value.max_concurrent}，立即生效`,
    }
  } catch (error) {
    saveResult.value = {
      success: false,
      message: error instanceof Error ? error.message : '保存失败',
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>
