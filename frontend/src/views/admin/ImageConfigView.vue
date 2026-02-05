<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">Image Service Configuration</h1>
        <p class="text-gray-400 mt-1">Configure image generation providers</p>
      </div>
    </div>

    <!-- Default Provider -->
    <div class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-lg font-semibold text-white mb-4">Default Provider</h2>
      <select
        v-model="defaultProvider"
        @change="updateDefaultProvider"
        class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="dall_e">DALL-E (OpenAI)</option>
        <option value="kie_ai">Kie.ai</option>
        <option value="wenwen_ai">Wenwen AI</option>
        <option value="nanobanana">Nanobanana</option>
      </select>
    </div>

    <!-- Provider Cards -->
    <div class="grid gap-4">
      <div
        v-for="(provider, key) in providers"
        :key="key"
        class="bg-gray-800 rounded-lg p-6"
      >
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center space-x-3">
            <h2 class="text-lg font-semibold text-white">{{ getProviderName(key) }}</h2>
            <span
              :class="[
                'px-2 py-1 rounded text-xs',
                provider.configured
                  ? 'bg-green-900/50 text-green-400'
                  : 'bg-gray-700 text-gray-400'
              ]"
            >
              {{ provider.configured ? 'Configured' : 'Not Configured' }}
            </span>
          </div>

          <!-- Enable Toggle -->
          <button
            @click="toggleProvider(key)"
            :class="[
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
              provider.enabled ? 'bg-blue-600' : 'bg-gray-600'
            ]"
          >
            <span
              :class="[
                'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                provider.enabled ? 'translate-x-6' : 'translate-x-1'
              ]"
            />
          </button>
        </div>

        <!-- API Key Input -->
        <div class="space-y-2">
          <label class="block text-sm font-medium text-gray-300">API Key</label>
          <div class="flex space-x-2">
            <input
              v-model="formData[key].api_key"
              :type="showKeys[key] ? 'text' : 'password'"
              :placeholder="provider.api_key || 'Enter API key...'"
              class="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="button"
              @click="showKeys[key] = !showKeys[key]"
              class="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-400 hover:text-white transition-colors"
            >
              <svg v-if="showKeys[key]" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
              <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            </button>
            <button
              @click="saveProviderKey(key)"
              :disabled="!formData[key].api_key || savingProvider === key"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {{ savingProvider === key ? 'Saving...' : 'Save' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Result Message -->
    <div
      v-if="message"
      :class="[
        'p-4 rounded-lg',
        messageType === 'success'
          ? 'bg-green-900/30 border border-green-700 text-green-300'
          : 'bg-red-900/30 border border-red-700 text-red-300'
      ]"
    >
      {{ message }}
    </div>

    <!-- Info Box -->
    <div class="bg-blue-900/20 border border-blue-800 rounded-lg p-4">
      <h3 class="text-blue-400 font-medium mb-2">About Image Providers</h3>
      <ul class="text-gray-400 text-sm space-y-1">
        <li>- DALL-E uses your OpenAI API key (same as LLM configuration)</li>
        <li>- Each provider requires its own API key</li>
        <li>- API keys are encrypted before storage</li>
        <li>- Only enabled providers can be used for image generation</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

interface ProviderConfig {
  api_key: string | null
  enabled: boolean
  configured: boolean
}

const providers = ref<Record<string, ProviderConfig>>({
  dall_e: { api_key: null, enabled: false, configured: false },
  kie_ai: { api_key: null, enabled: false, configured: false },
  wenwen_ai: { api_key: null, enabled: false, configured: false },
  nanobanana: { api_key: null, enabled: false, configured: false },
})

const defaultProvider = ref('dall_e')
const showKeys = reactive<Record<string, boolean>>({
  dall_e: false,
  kie_ai: false,
  wenwen_ai: false,
  nanobanana: false,
})
const formData = reactive<Record<string, { api_key: string }>>({
  dall_e: { api_key: '' },
  kie_ai: { api_key: '' },
  wenwen_ai: { api_key: '' },
  nanobanana: { api_key: '' },
})
const savingProvider = ref<string | null>(null)
const message = ref('')
const messageType = ref<'success' | 'error'>('success')

const providerNames: Record<string, string> = {
  dall_e: 'DALL-E (OpenAI)',
  kie_ai: 'Kie.ai',
  wenwen_ai: 'Wenwen AI',
  nanobanana: 'Nanobanana',
}

function getProviderName(key: string): string {
  return providerNames[key] || key
}

async function loadConfig() {
  try {
    const data = await apiRequest<{
      default_provider: string
      providers: Record<string, ProviderConfig>
    }>('/config/image')

    defaultProvider.value = data.default_provider || 'dall_e'
    if (data.providers) {
      providers.value = data.providers
    }
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

async function updateDefaultProvider() {
  try {
    await apiRequest('/config/image/default_provider', {
      method: 'PUT',
      body: JSON.stringify({
        value: defaultProvider.value,
        encrypted: false,
      }),
    })
    showMessage('Default provider updated', 'success')
  } catch (error) {
    showMessage('Failed to update default provider', 'error')
  }
}

async function toggleProvider(key: string) {
  try {
    const newValue = !providers.value[key].enabled
    await apiRequest(`/config/image/${key}_enabled`, {
      method: 'PUT',
      body: JSON.stringify({
        value: newValue ? 'true' : 'false',
        encrypted: false,
      }),
    })
    providers.value[key].enabled = newValue
    showMessage(`${getProviderName(key)} ${newValue ? 'enabled' : 'disabled'}`, 'success')
  } catch (error) {
    showMessage('Failed to update provider status', 'error')
  }
}

async function saveProviderKey(key: string) {
  if (!formData[key].api_key) return

  savingProvider.value = key
  try {
    await apiRequest(`/config/image/${key}_api_key`, {
      method: 'PUT',
      body: JSON.stringify({
        value: formData[key].api_key,
        encrypted: true,
      }),
    })
    await loadConfig()
    formData[key].api_key = ''
    showMessage(`${getProviderName(key)} API key saved`, 'success')
  } catch (error) {
    showMessage('Failed to save API key', 'error')
  } finally {
    savingProvider.value = null
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
