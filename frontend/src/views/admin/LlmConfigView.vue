<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">LLM 配置</h1>
        <p class="text-zinc-400 mt-1">配置 OpenAI API 设置</p>
      </div>
      <div class="flex items-center space-x-2">
        <span
          :class="[
            'px-3 py-1 rounded-full text-sm',
            config.configured
              ? 'bg-emerald-900/50 text-emerald-400'
              : 'bg-yellow-900/50 text-yellow-400'
          ]"
        >
          {{ config.configured ? '已配置' : '未配置' }}
        </span>
      </div>
    </div>

    <!-- Configuration Form -->
    <div class="bg-zinc-800 rounded-lg p-6 space-y-6">
      <!-- API Key -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          OpenAI API Key
        </label>
        <div class="flex space-x-2">
          <input
            v-model="form.openai_api_key"
            :type="showApiKey ? 'text' : 'password'"
            :placeholder="config.openai_api_key || 'sk-...'"
            class="flex-1 px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
          />
          <button
            type="button"
            @click="showApiKey = !showApiKey"
            class="px-3 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-zinc-400 hover:text-white transition-colors"
          >
            <svg v-if="showApiKey" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </button>
        </div>
        <p class="text-zinc-500 text-sm mt-1">
          您的 API 密钥将被加密安全存储
        </p>
      </div>

      <!-- Base URL (Optional) -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          Base URL（可选）
        </label>
        <input
          v-model="form.openai_base_url"
          type="text"
          placeholder="https://api.openai.com/v1"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <p class="text-zinc-500 text-sm mt-1">
          需填写完整路径（含 /v1），留空则使用 OpenAI 默认端点
        </p>
      </div>

      <!-- Model Selection -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          默认模型
        </label>
        <div class="relative">
          <input
            v-model="form.openai_model"
            type="text"
            list="model-options"
            placeholder="输入或选择模型名称"
            class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
          />
          <datalist id="model-options">
            <optgroup label="OpenAI">
              <option value="gpt-4">GPT-4</option>
              <option value="gpt-4-turbo">GPT-4 Turbo</option>
              <option value="gpt-4o">GPT-4o</option>
              <option value="gpt-4o-mini">GPT-4o Mini</option>
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
            </optgroup>
            <optgroup label="Moonshot (Kimi)">
              <option value="moonshot-v1-8k">Moonshot V1 8K</option>
              <option value="moonshot-v1-32k">Moonshot V1 32K</option>
              <option value="moonshot-v1-128k">Moonshot V1 128K</option>
              <option value="kimi-k2.5">Kimi K2.5</option>
            </optgroup>
            <optgroup label="通义千问 (Qwen)">
              <option value="qwen-max">Qwen Max</option>
              <option value="qwen-plus">Qwen Plus</option>
              <option value="qwen-turbo">Qwen Turbo</option>
              <option value="qwen-long">Qwen Long</option>
            </optgroup>
            <optgroup label="MiniMax">
              <option value="abab6.5s-chat">ABAB 6.5s Chat</option>
              <option value="abab5.5-chat">ABAB 5.5 Chat</option>
            </optgroup>
            <optgroup label="DeepSeek">
              <option value="deepseek-chat">DeepSeek Chat</option>
              <option value="deepseek-coder">DeepSeek Coder</option>
            </optgroup>
          </datalist>
        </div>
        <p class="text-zinc-500 text-sm mt-1">
          可选择预设模型或直接输入自定义模型名称
        </p>
      </div>

      <!-- Actions -->
      <div class="flex items-center justify-between pt-4 border-t border-zinc-700">
        <button
          @click="testConnection"
          :disabled="testing || !config.configured && !form.openai_api_key"
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
      <h3 class="text-zinc-400 font-medium mb-2">关于 LLM 配置</h3>
      <ul class="text-zinc-400 text-sm space-y-1">
        <li>• API 密钥使用 AES-256-GCM 加密存储</li>
        <li>• 配置更改立即生效（热重载）</li>
        <li>• 环境变量优先于数据库配置</li>
        <li>• 支持 OpenAI 兼容 API 的服务商</li>
      </ul>

      <h4 class="text-zinc-400 font-medium mt-4 mb-2">常用服务商配置</h4>
      <div class="text-zinc-400 text-sm space-y-2">
        <div class="bg-zinc-800/50 rounded p-2">
          <span class="text-zinc-300">Moonshot (Kimi) 中国区</span>
          <div class="text-xs mt-1">
            Base URL: <code class="text-emerald-400">https://api.moonshot.cn/v1</code><br>
            模型: moonshot-v1-8k / moonshot-v1-32k / moonshot-v1-128k
          </div>
        </div>
        <div class="bg-zinc-800/50 rounded p-2">
          <span class="text-zinc-300">DeepSeek</span>
          <div class="text-xs mt-1">
            Base URL: <code class="text-emerald-400">https://api.deepseek.com</code><br>
            模型: deepseek-chat / deepseek-coder
          </div>
        </div>
        <div class="bg-zinc-800/50 rounded p-2">
          <span class="text-zinc-300">智谱 AI (GLM)</span>
          <div class="text-xs mt-1">
            Base URL: <code class="text-emerald-400">https://open.bigmodel.cn/api/paas/v4</code><br>
            模型: glm-4 / glm-4-flash
          </div>
        </div>
        <div class="bg-zinc-800/50 rounded p-2">
          <span class="text-zinc-300">通义千问 (Qwen)</span>
          <div class="text-xs mt-1">
            Base URL: <code class="text-emerald-400">https://dashscope.aliyuncs.com/compatible-mode/v1</code><br>
            模型: qwen-max / qwen-plus / qwen-turbo
          </div>
        </div>
        <div class="bg-zinc-800/50 rounded p-2">
          <span class="text-zinc-300">MiniMax</span>
          <div class="text-xs mt-1">
            Base URL: <code class="text-emerald-400">https://api.minimaxi.com/v1</code><br>
            模型: abab6.5s-chat / abab5.5-chat
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

interface LlmConfig {
  openai_api_key: string | null
  openai_base_url: string | null
  openai_model: string
  configured: boolean
}

interface TestResult {
  success: boolean
  message: string
  latency_ms?: number
}

const config = ref<LlmConfig>({
  openai_api_key: null,
  openai_base_url: null,
  openai_model: 'gpt-4',
  configured: false,
})

const form = ref({
  openai_api_key: '',
  openai_base_url: '',
  openai_model: 'gpt-4',
})

const showApiKey = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref<TestResult | null>(null)

const hasChanges = computed(() => {
  return (
    form.value.openai_api_key !== '' ||
    form.value.openai_base_url !== (config.value.openai_base_url || '') ||
    form.value.openai_model !== config.value.openai_model
  )
})

async function loadConfig() {
  try {
    const data = await apiRequest<LlmConfig>('/config/llm')
    config.value = data
    form.value.openai_model = data.openai_model || 'gpt-4'
    form.value.openai_base_url = data.openai_base_url || ''
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

async function saveConfig() {
  saving.value = true
  testResult.value = null

  try {
    // Save API key if provided
    if (form.value.openai_api_key) {
      await apiRequest('/config/llm/openai_api_key', {
        method: 'PUT',
        body: JSON.stringify({
          value: form.value.openai_api_key,
          encrypted: true,
        }),
      })
    }

    // Save base URL
    if (form.value.openai_base_url) {
      await apiRequest('/config/llm/openai_base_url', {
        method: 'PUT',
        body: JSON.stringify({
          value: form.value.openai_base_url,
          encrypted: false,
        }),
      })
    }

    // Save model
    await apiRequest('/config/llm/openai_model', {
      method: 'PUT',
      body: JSON.stringify({
        value: form.value.openai_model,
        encrypted: false,
      }),
    })

    // Reload config
    await loadConfig()
    form.value.openai_api_key = ''

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
    const result = await apiRequest<TestResult>('/config/test/llm', {
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
