<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">Langfuse Configuration</h1>
        <p class="text-gray-400 mt-1">Configure Langfuse monitoring settings</p>
      </div>
      <div class="flex items-center space-x-2">
        <span
          :class="[
            'px-3 py-1 rounded-full text-sm',
            config.enabled
              ? 'bg-green-900/50 text-green-400'
              : 'bg-gray-700 text-gray-400'
          ]"
        >
          {{ config.enabled ? 'Enabled' : 'Disabled' }}
        </span>
      </div>
    </div>

    <!-- Configuration Form -->
    <div class="bg-gray-800 rounded-lg p-6 space-y-6">
      <!-- Enable/Disable Toggle -->
      <div class="flex items-center justify-between">
        <div>
          <label class="text-sm font-medium text-gray-300">Enable Langfuse Monitoring</label>
          <p class="text-gray-500 text-sm">Enable or disable Langfuse integration</p>
        </div>
        <button
          @click="form.enabled = !form.enabled"
          :class="[
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
            form.enabled ? 'bg-blue-600' : 'bg-gray-600'
          ]"
        >
          <span
            :class="[
              'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
              form.enabled ? 'translate-x-6' : 'translate-x-1'
            ]"
          />
        </button>
      </div>

      <!-- Public Key -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-2">
          Public Key
        </label>
        <input
          v-model="form.public_key"
          type="text"
          :placeholder="config.public_key || 'pk-lf-...'"
          class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <!-- Secret Key -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-2">
          Secret Key
        </label>
        <div class="flex space-x-2">
          <input
            v-model="form.secret_key"
            :type="showSecretKey ? 'text' : 'password'"
            :placeholder="config.secret_key || 'sk-lf-...'"
            class="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="button"
            @click="showSecretKey = !showSecretKey"
            class="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-400 hover:text-white transition-colors"
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
        <p class="text-gray-500 text-sm mt-1">
          Your secret key will be encrypted and stored securely
        </p>
      </div>

      <!-- Host -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-2">
          Host
        </label>
        <select
          v-model="form.host"
          class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="https://cloud.langfuse.com">Cloud (cloud.langfuse.com)</option>
          <option value="https://us.cloud.langfuse.com">US Cloud (us.cloud.langfuse.com)</option>
          <option value="https://eu.cloud.langfuse.com">EU Cloud (eu.cloud.langfuse.com)</option>
          <option value="custom">Custom</option>
        </select>
      </div>

      <!-- Custom Host -->
      <div v-if="form.host === 'custom'">
        <label class="block text-sm font-medium text-gray-300 mb-2">
          Custom Host URL
        </label>
        <input
          v-model="form.custom_host"
          type="text"
          placeholder="https://your-langfuse-instance.com"
          class="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <!-- Actions -->
      <div class="flex items-center justify-between pt-4 border-t border-gray-700">
        <button
          @click="testConnection"
          :disabled="testing || !config.configured && !form.public_key"
          class="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span v-if="testing" class="flex items-center">
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Testing...
          </span>
          <span v-else>Test Connection</span>
        </button>

        <button
          @click="saveConfig"
          :disabled="saving || !hasChanges"
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span v-if="saving">Saving...</span>
          <span v-else>Save Changes</span>
        </button>
      </div>
    </div>

    <!-- Test Result -->
    <div
      v-if="testResult"
      :class="[
        'p-4 rounded-lg',
        testResult.success
          ? 'bg-green-900/30 border border-green-700 text-green-300'
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
    <div class="bg-blue-900/20 border border-blue-800 rounded-lg p-4">
      <h3 class="text-blue-400 font-medium mb-2">About Langfuse</h3>
      <ul class="text-gray-400 text-sm space-y-1">
        <li>- Langfuse provides LLM observability and monitoring</li>
        <li>- Track costs, latency, and quality of LLM calls</li>
        <li>- Secret keys are encrypted before storage</li>
        <li>- Changes take effect immediately when Langfuse is reinitialized</li>
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
