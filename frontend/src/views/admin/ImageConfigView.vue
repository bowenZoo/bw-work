<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">图像生成配置</h1>
        <p class="text-zinc-400 mt-1">配置通用图像生成接口</p>
      </div>
    </div>

    <!-- OpenAI Compatible Image Generation -->
    <div class="bg-zinc-800 rounded-lg p-6 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-white">OpenAI 兼容接口</h2>
          <p class="text-zinc-400 text-sm">支持通过 chat/completions 生成图片的模型</p>
        </div>
        <div class="flex items-center space-x-3">
          <span
            :class="[
              'px-3 py-1 rounded-full text-sm',
              openaiConfig.configured
                ? 'bg-emerald-900/50 text-emerald-400'
                : 'bg-yellow-900/50 text-yellow-400'
            ]"
          >
            {{ openaiConfig.configured ? '已配置' : '未配置' }}
          </span>
          <!-- Enable/Disable Toggle -->
          <button
            type="button"
            @click="openaiForm.enabled = !openaiForm.enabled"
            :class="[
              'relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2 focus:ring-offset-zinc-900',
              openaiForm.enabled ? 'bg-emerald-500' : 'bg-zinc-600'
            ]"
          >
            <span
              :class="[
                'pointer-events-none inline-block h-6 w-6 transform rounded-full shadow ring-0 transition duration-200 ease-in-out',
                openaiForm.enabled ? 'translate-x-5 bg-white' : 'translate-x-0 bg-zinc-400'
              ]"
            />
          </button>
        </div>
      </div>

      <!-- Base URL -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">Base URL</label>
        <input
          v-model="openaiForm.base_url"
          type="text"
          placeholder="https://api.wenwen-ai.com/v1"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <p class="text-zinc-500 text-sm mt-1">需填写完整路径（含 /v1）</p>
      </div>

      <!-- API Key -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">API 密钥</label>
        <div class="flex space-x-2">
          <input
            v-model="openaiForm.api_key"
            :type="showOpenaiKey ? 'text' : 'password'"
            :placeholder="openaiConfig.api_key || '请输入 API 密钥...'"
            class="flex-1 px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
          />
          <button
            type="button"
            @click="showOpenaiKey = !showOpenaiKey"
            class="px-3 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-zinc-400 hover:text-white transition-colors"
          >
            <svg v-if="showOpenaiKey" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Model -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">默认模型</label>
        <input
          v-model="openaiForm.model"
          type="text"
          list="openai-image-models"
          placeholder="gemini-2.5-flash-image"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <datalist id="openai-image-models">
          <option value="gemini-2.5-flash-image">Gemini 2.5 Flash Image</option>
          <option value="gemini-2.5-pro-image">Gemini 2.5 Pro Image</option>
          <option value="gpt-4o-image">GPT-4o Image</option>
          <option value="dall-e-3">DALL-E 3</option>
        </datalist>
        <p class="text-zinc-500 text-sm mt-1">可选择预设或输入自定义模型名称</p>
      </div>

      <!-- Save Button -->
      <div class="flex justify-end pt-2">
        <button
          @click="saveOpenaiConfig"
          :disabled="savingOpenai || !hasOpenaiChanges"
          class="px-4 py-2 bg-white text-black rounded-lg hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ savingOpenai ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </div>

    <!-- MJ Interface -->
    <div class="bg-zinc-800 rounded-lg p-6 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-white">Midjourney 接口</h2>
          <p class="text-zinc-400 text-sm">支持 /mj/submit/imagine 格式的接口</p>
        </div>
        <div class="flex items-center space-x-3">
          <span
            :class="[
              'px-3 py-1 rounded-full text-sm',
              mjConfig.configured
                ? 'bg-emerald-900/50 text-emerald-400'
                : 'bg-yellow-900/50 text-yellow-400'
            ]"
          >
            {{ mjConfig.configured ? '已配置' : '未配置' }}
          </span>
          <!-- Enable/Disable Toggle -->
          <button
            type="button"
            @click="mjForm.enabled = !mjForm.enabled"
            :class="[
              'relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2 focus:ring-offset-zinc-900',
              mjForm.enabled ? 'bg-emerald-500' : 'bg-zinc-600'
            ]"
          >
            <span
              :class="[
                'pointer-events-none inline-block h-6 w-6 transform rounded-full shadow ring-0 transition duration-200 ease-in-out',
                mjForm.enabled ? 'translate-x-5 bg-white' : 'translate-x-0 bg-zinc-400'
              ]"
            />
          </button>
        </div>
      </div>

      <!-- Base URL -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">Base URL</label>
        <input
          v-model="mjForm.base_url"
          type="text"
          placeholder="https://api.wenwen-ai.com"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <p class="text-zinc-500 text-sm mt-1">不含路径后缀，系统会自动拼接 /mj/submit/imagine</p>
      </div>

      <!-- API Key -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">API 密钥</label>
        <div class="flex space-x-2">
          <input
            v-model="mjForm.api_key"
            :type="showMjKey ? 'text' : 'password'"
            :placeholder="mjConfig.api_key || '请输入 API 密钥...'"
            class="flex-1 px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
          />
          <button
            type="button"
            @click="showMjKey = !showMjKey"
            class="px-3 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-zinc-400 hover:text-white transition-colors"
          >
            <svg v-if="showMjKey" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Mode -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">默认模式</label>
        <select
          v-model="mjForm.mode"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-zinc-400"
        >
          <option value="RELAX">RELAX（慢速）</option>
          <option value="FAST">FAST（快速）</option>
        </select>
      </div>

      <!-- Save Button -->
      <div class="flex justify-end pt-2">
        <button
          @click="saveMjConfig"
          :disabled="savingMj || !hasMjChanges"
          class="px-4 py-2 bg-white text-black rounded-lg hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ savingMj ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </div>

    <!-- Result Message -->
    <div
      v-if="message"
      :class="[
        'p-4 rounded-lg',
        messageType === 'success'
          ? 'bg-emerald-900/30 border border-emerald-700 text-emerald-300'
          : 'bg-red-900/30 border border-red-700 text-red-300'
      ]"
    >
      {{ message }}
    </div>

    <!-- Info Box -->
    <div class="bg-zinc-800/50 border border-zinc-700 rounded-lg p-4">
      <h3 class="text-zinc-400 font-medium mb-2">接口说明</h3>
      <div class="text-zinc-400 text-sm space-y-3">
        <div>
          <span class="text-zinc-300 font-medium">OpenAI 兼容接口</span>
          <p class="mt-1">使用 chat/completions 格式，通过提示词生成图片。支持 Gemini、GPT-4o 等模型。</p>
        </div>
        <div>
          <span class="text-zinc-300 font-medium">Midjourney 接口</span>
          <p class="mt-1">使用 /mj/submit/imagine 格式，支持 MJ 参数如 --v、--ar、--q 等。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

interface ImageConfig {
  base_url: string | null
  api_key: string | null
  model?: string
  mode?: string
  enabled: boolean
  configured: boolean
}

// OpenAI 兼容接口配置
const openaiConfig = ref<ImageConfig>({
  base_url: null,
  api_key: null,
  model: 'gemini-2.5-flash-image',
  enabled: false,
  configured: false,
})

const openaiForm = ref({
  base_url: '',
  api_key: '',
  model: 'gemini-2.5-flash-image',
  enabled: false,
})

// MJ 接口配置
const mjConfig = ref<ImageConfig>({
  base_url: null,
  api_key: null,
  mode: 'RELAX',
  enabled: false,
  configured: false,
})

const mjForm = ref({
  base_url: '',
  api_key: '',
  mode: 'RELAX',
  enabled: false,
})

const showOpenaiKey = ref(false)
const showMjKey = ref(false)
const savingOpenai = ref(false)
const savingMj = ref(false)
const message = ref('')
const messageType = ref<'success' | 'error'>('success')

const hasOpenaiChanges = computed(() => {
  return (
    openaiForm.value.api_key !== '' ||
    openaiForm.value.base_url !== (openaiConfig.value.base_url || '') ||
    openaiForm.value.model !== (openaiConfig.value.model || 'gemini-2.5-flash-image') ||
    openaiForm.value.enabled !== openaiConfig.value.enabled
  )
})

const hasMjChanges = computed(() => {
  return (
    mjForm.value.api_key !== '' ||
    mjForm.value.base_url !== (mjConfig.value.base_url || '') ||
    mjForm.value.mode !== (mjConfig.value.mode || 'RELAX') ||
    mjForm.value.enabled !== mjConfig.value.enabled
  )
})

async function loadConfig() {
  try {
    const data = await apiRequest<{
      openai: ImageConfig
      mj: ImageConfig
    }>('/config/image')

    if (data.openai) {
      openaiConfig.value = data.openai
      openaiForm.value.base_url = data.openai.base_url || ''
      openaiForm.value.model = data.openai.model || 'gemini-2.5-flash-image'
      openaiForm.value.enabled = data.openai.enabled || false
    }
    if (data.mj) {
      mjConfig.value = data.mj
      mjForm.value.base_url = data.mj.base_url || ''
      mjForm.value.mode = data.mj.mode || 'RELAX'
      mjForm.value.enabled = data.mj.enabled || false
    }
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

async function saveOpenaiConfig() {
  savingOpenai.value = true
  try {
    // Save API key if provided
    if (openaiForm.value.api_key) {
      await apiRequest('/config/image/openai_api_key', {
        method: 'PUT',
        body: JSON.stringify({
          value: openaiForm.value.api_key,
          encrypted: true,
        }),
      })
    }

    // Save base URL
    if (openaiForm.value.base_url) {
      await apiRequest('/config/image/openai_base_url', {
        method: 'PUT',
        body: JSON.stringify({
          value: openaiForm.value.base_url,
          encrypted: false,
        }),
      })
    }

    // Save model
    await apiRequest('/config/image/openai_model', {
      method: 'PUT',
      body: JSON.stringify({
        value: openaiForm.value.model,
        encrypted: false,
      }),
    })

    // Save enabled
    await apiRequest('/config/image/openai_enabled', {
      method: 'PUT',
      body: JSON.stringify({
        value: openaiForm.value.enabled ? 'true' : 'false',
        encrypted: false,
      }),
    })

    await loadConfig()
    openaiForm.value.api_key = ''
    showMessage('OpenAI 兼容接口配置已保存', 'success')
  } catch (error) {
    showMessage('保存失败', 'error')
  } finally {
    savingOpenai.value = false
  }
}

async function saveMjConfig() {
  savingMj.value = true
  try {
    // Save API key if provided
    if (mjForm.value.api_key) {
      await apiRequest('/config/image/mj_api_key', {
        method: 'PUT',
        body: JSON.stringify({
          value: mjForm.value.api_key,
          encrypted: true,
        }),
      })
    }

    // Save base URL
    if (mjForm.value.base_url) {
      await apiRequest('/config/image/mj_base_url', {
        method: 'PUT',
        body: JSON.stringify({
          value: mjForm.value.base_url,
          encrypted: false,
        }),
      })
    }

    // Save mode
    await apiRequest('/config/image/mj_mode', {
      method: 'PUT',
      body: JSON.stringify({
        value: mjForm.value.mode,
        encrypted: false,
      }),
    })

    // Save enabled
    await apiRequest('/config/image/mj_enabled', {
      method: 'PUT',
      body: JSON.stringify({
        value: mjForm.value.enabled ? 'true' : 'false',
        encrypted: false,
      }),
    })

    await loadConfig()
    mjForm.value.api_key = ''
    showMessage('Midjourney 接口配置已保存', 'success')
  } catch (error) {
    showMessage('保存失败', 'error')
  } finally {
    savingMj.value = false
  }
}

function showMessage(msg: string, type: 'success' | 'error') {
  message.value = msg
  messageType.value = type
  setTimeout(() => {
    message.value = ''
  }, 3000)
}

onMounted(() => {
  loadConfig()
})
</script>
