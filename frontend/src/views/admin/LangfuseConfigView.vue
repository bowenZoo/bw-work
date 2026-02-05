<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">Langfuse 配置</h1>
        <p class="text-zinc-400 mt-1">配置 Langfuse 监控设置</p>
      </div>
      <div class="flex items-center space-x-2">
        <span
          :class="[
            'px-3 py-1 rounded-full text-sm',
            config.enabled
              ? 'bg-emerald-900/50 text-emerald-400'
              : 'bg-zinc-700 text-zinc-400'
          ]"
        >
          {{ config.enabled ? '已启用' : '已禁用' }}
        </span>
      </div>
    </div>

    <!-- Configuration Form -->
    <div class="bg-zinc-800 rounded-lg p-6 space-y-6">
      <!-- Enable/Disable Toggle -->
      <div class="flex items-center justify-between">
        <div>
          <label class="text-sm font-medium text-zinc-300">启用 Langfuse 监控</label>
          <p class="text-zinc-500 text-sm">启用或禁用 Langfuse 集成</p>
        </div>
        <button
          @click="form.enabled = !form.enabled"
          :class="[
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
            form.enabled ? 'bg-emerald-500' : 'bg-zinc-600'
          ]"
        >
          <span
            :class="[
              'inline-block h-4 w-4 transform rounded-full transition-transform',
              form.enabled ? 'translate-x-6 bg-white' : 'translate-x-1 bg-zinc-400'
            ]"
          />
        </button>
      </div>

      <!-- Public Key -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          公钥
        </label>
        <input
          v-model="form.public_key"
          type="text"
          :placeholder="config.public_key || 'pk-lf-...'"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
      </div>

      <!-- Secret Key -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          私钥
        </label>
        <div class="flex space-x-2">
          <input
            v-model="form.secret_key"
            :type="showSecretKey ? 'text' : 'password'"
            :placeholder="config.secret_key || 'sk-lf-...'"
            class="flex-1 px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
          />
          <button
            type="button"
            @click="showSecretKey = !showSecretKey"
            class="px-3 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-zinc-400 hover:text-white transition-colors"
          >
            <svg v-if="showSecretKey" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </button>
        </div>
        <p class="text-zinc-500 text-sm mt-1">
          您的私钥将被加密安全存储
        </p>
      </div>

      <!-- Host -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          服务器
        </label>
        <select
          v-model="form.host"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-zinc-400"
        >
          <option value="https://cloud.langfuse.com">云服务 (cloud.langfuse.com)</option>
          <option value="https://us.cloud.langfuse.com">美国云 (us.cloud.langfuse.com)</option>
          <option value="https://eu.cloud.langfuse.com">欧洲云 (eu.cloud.langfuse.com)</option>
          <option value="custom">自定义</option>
        </select>
      </div>

      <!-- Custom Host -->
      <div v-if="form.host === 'custom'">
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          自定义服务器 URL
        </label>
        <input
          v-model="form.custom_host"
          type="text"
          placeholder="https://your-langfuse-instance.com"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
      </div>

      <!-- Actions -->
      <div class="flex items-center justify-between pt-4 border-t border-zinc-700">
        <button
          @click="testConnection"
          :disabled="testing || !config.configured && !form.public_key"
          class="px-4 py-2 bg-zinc-700 text-white rounded-lg hover:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span v-if="testing" class="flex items-center">
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            测试中...
          </span>
          <span v-else>测试连接</span>
        </button>

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

    <!-- Test Result -->
    <div
      v-if="testResult"
      :class="[
        'p-4 rounded-lg',
        testResult.success
          ? 'bg-emerald-900/30 border border-emerald-700 text-emerald-300'
          : 'bg-red-900/30 border border-red-700 text-red-300'
      ]"
    >
      <div class="flex items-center">
        <svg v-if="testResult.success" class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        <svg v-else class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
        <span>{{ testResult.message }}</span>
        <span v-if="testResult.latency_ms" class="ml-2 text-sm opacity-75">
          ({{ testResult.latency_ms.toFixed(0) }}ms)
        </span>
      </div>
    </div>

    <!-- Info Box -->
    <div class="bg-zinc-800/50 border border-zinc-700 rounded-lg p-4">
      <h3 class="text-zinc-400 font-medium mb-2">关于 Langfuse</h3>
      <ul class="text-zinc-400 text-sm space-y-1">
        <li>- Langfuse 提供 LLM 可观测性和监控</li>
        <li>- 追踪 LLM 调用的成本、延迟和质量</li>
        <li>- 私钥在存储前会被加密</li>
        <li>- 重新初始化 Langfuse 后配置立即生效</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

interface LangfuseConfig {
  public_key: string | null
  secret_key: string | null
  host: string
  enabled: boolean
  configured: boolean
}

interface TestResult {
  success: boolean
  message: string
  latency_ms?: number
}

const config = ref<LangfuseConfig>({
  public_key: null,
  secret_key: null,
  host: 'https://cloud.langfuse.com',
  enabled: false,
  configured: false,
})

const form = ref({
  public_key: '',
  secret_key: '',
  host: 'https://cloud.langfuse.com',
  custom_host: '',
  enabled: false,
})

const showSecretKey = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref<TestResult | null>(null)

const hasChanges = computed(() => {
  return (
    form.value.public_key !== '' ||
    form.value.secret_key !== '' ||
    form.value.enabled !== config.value.enabled ||
    getEffectiveHost() !== config.value.host
  )
})

function getEffectiveHost(): string {
  return form.value.host === 'custom' ? form.value.custom_host : form.value.host
}

async function loadConfig() {
  try {
    const data = await apiRequest<LangfuseConfig>('/config/langfuse')
    config.value = data
    form.value.enabled = data.enabled

    // Determine if host is standard or custom
    const standardHosts = [
      'https://cloud.langfuse.com',
      'https://us.cloud.langfuse.com',
      'https://eu.cloud.langfuse.com',
    ]
    if (standardHosts.includes(data.host)) {
      form.value.host = data.host
    } else {
      form.value.host = 'custom'
      form.value.custom_host = data.host
    }
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

async function saveConfig() {
  saving.value = true
  testResult.value = null

  try {
    // Save public key if provided
    if (form.value.public_key) {
      await apiRequest('/config/langfuse/public_key', {
        method: 'PUT',
        body: JSON.stringify({
          value: form.value.public_key,
          encrypted: true,
        }),
      })
    }

    // Save secret key if provided
    if (form.value.secret_key) {
      await apiRequest('/config/langfuse/secret_key', {
        method: 'PUT',
        body: JSON.stringify({
          value: form.value.secret_key,
          encrypted: true,
        }),
      })
    }

    // Save host
    await apiRequest('/config/langfuse/host', {
      method: 'PUT',
      body: JSON.stringify({
        value: getEffectiveHost(),
        encrypted: false,
      }),
    })

    // Save enabled status
    await apiRequest('/config/langfuse/enabled', {
      method: 'PUT',
      body: JSON.stringify({
        value: form.value.enabled ? 'true' : 'false',
        encrypted: false,
      }),
    })

    // Reload config
    await loadConfig()
    form.value.public_key = ''
    form.value.secret_key = ''

    testResult.value = {
      success: true,
      message: 'Configuration saved successfully',
    }
  } catch (error) {
    testResult.value = {
      success: false,
      message: error instanceof Error ? error.message : 'Failed to save configuration',
    }
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null

  try {
    const result = await apiRequest<TestResult>('/config/test/langfuse', {
      method: 'POST',
    })
    testResult.value = result
  } catch (error) {
    testResult.value = {
      success: false,
      message: error instanceof Error ? error.message : 'Test failed',
    }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>
