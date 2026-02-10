<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-white">LLM 配置</h1>
        <p class="text-zinc-400 mt-1">管理多个 LLM 供应商配置方案</p>
      </div>
      <button
        @click="startCreate"
        class="px-4 py-2 bg-white text-black rounded-lg hover:bg-zinc-200 transition-colors text-sm font-medium"
      >
        + 新增方案
      </button>
    </div>

    <!-- Profile List -->
    <div v-if="profiles.length === 0 && !editing" class="bg-zinc-800 rounded-lg p-8 text-center">
      <p class="text-zinc-400">暂无配置方案，点击右上角新增</p>
    </div>

    <div v-for="profile in profiles" :key="profile.id" class="bg-zinc-800 rounded-lg p-5">
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-3">
          <!-- Active indicator -->
          <span
            :class="[
              'w-3 h-3 rounded-full flex-shrink-0',
              profile.is_active ? 'bg-emerald-400' : 'bg-zinc-600'
            ]"
          />
          <div>
            <div class="flex items-center space-x-2">
              <span class="text-white font-medium">{{ profile.name }}</span>
              <span
                v-if="profile.is_active"
                class="px-2 py-0.5 rounded text-xs bg-emerald-900/50 text-emerald-400"
              >
                当前激活
              </span>
              <span
                v-if="!profile.has_api_key"
                class="px-2 py-0.5 rounded text-xs bg-yellow-900/50 text-yellow-400"
              >
                未配置密钥
              </span>
            </div>
            <div class="text-zinc-500 text-sm mt-1">
              <span>{{ profile.model }}</span>
              <span v-if="profile.base_url" class="ml-3">{{ profile.base_url }}</span>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center space-x-2">
          <button
            @click="startEdit(profile)"
            class="px-3 py-1.5 text-sm bg-zinc-700 text-zinc-300 rounded hover:bg-zinc-600 transition-colors"
          >
            编辑
          </button>
          <button
            @click="testProfile(profile.id)"
            :disabled="testingId === profile.id"
            class="px-3 py-1.5 text-sm bg-zinc-700 text-zinc-300 rounded hover:bg-zinc-600 disabled:opacity-50 transition-colors"
          >
            <span v-if="testingId === profile.id">测试中...</span>
            <span v-else>测试</span>
          </button>
          <button
            v-if="!profile.is_active"
            @click="activateProfile(profile.id)"
            :disabled="activatingId === profile.id"
            class="px-3 py-1.5 text-sm bg-emerald-900/50 text-emerald-400 rounded hover:bg-emerald-900/70 disabled:opacity-50 transition-colors"
          >
            激活
          </button>
          <button
            v-if="!profile.is_active"
            @click="deleteProfile(profile.id, profile.name)"
            class="px-3 py-1.5 text-sm bg-zinc-700 text-red-400 rounded hover:bg-red-900/30 transition-colors"
          >
            删除
          </button>
        </div>
      </div>

      <!-- Test result for this profile -->
      <div
        v-if="testResults[profile.id]"
        :class="[
          'mt-3 p-3 rounded text-sm',
          testResults[profile.id].success
            ? 'bg-emerald-900/20 text-emerald-300'
            : 'bg-red-900/20 text-red-300'
        ]"
      >
        {{ testResults[profile.id].message }}
        <span v-if="testResults[profile.id].latency_ms" class="ml-1 opacity-75">
          ({{ testResults[profile.id].latency_ms.toFixed(0) }}ms)
        </span>
      </div>
    </div>

    <!-- Edit / Create Form -->
    <div v-if="editing" class="bg-zinc-800 rounded-lg p-6 space-y-5 border border-zinc-600">
      <h2 class="text-lg font-medium text-white">
        {{ isNew ? '新增方案' : `编辑方案: ${form.name}` }}
      </h2>

      <!-- Profile ID (only for new) -->
      <div v-if="isNew">
        <label class="block text-sm font-medium text-zinc-300 mb-2">
          方案 ID（可选，留空自动生成）
        </label>
        <input
          v-model="form.id"
          type="text"
          placeholder="如 deepseek, moonshot"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
      </div>

      <!-- Name -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">名称</label>
        <input
          v-model="form.name"
          type="text"
          placeholder="如 问问 AI、DeepSeek"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
      </div>

      <!-- API Key -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">API Key</label>
        <div class="flex space-x-2">
          <input
            v-model="form.api_key"
            :type="showApiKey ? 'text' : 'password'"
            :placeholder="isNew ? 'sk-...' : '留空保持不变'"
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
        <p class="text-zinc-500 text-sm mt-1">密钥使用 AES-256-GCM 加密存储</p>
      </div>

      <!-- Base URL -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">Base URL</label>
        <input
          v-model="form.base_url"
          type="text"
          placeholder="https://api.openai.com/v1"
          class="w-full px-4 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <p class="text-zinc-500 text-sm mt-1">需填写完整路径（含 /v1），留空则使用 OpenAI 默认端点</p>
      </div>

      <!-- Model -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">模型</label>
        <input
          v-model="form.model"
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
          </optgroup>
          <optgroup label="Moonshot (Kimi)">
            <option value="moonshot-v1-8k">Moonshot V1 8K</option>
            <option value="moonshot-v1-32k">Moonshot V1 32K</option>
            <option value="moonshot-v1-128k">Moonshot V1 128K</option>
            <option value="kimi-k2.5">Kimi K2.5</option>
          </optgroup>
          <optgroup label="DeepSeek">
            <option value="deepseek-chat">DeepSeek Chat</option>
            <option value="deepseek-coder">DeepSeek Coder</option>
          </optgroup>
          <optgroup label="通义千问 (Qwen)">
            <option value="qwen-max">Qwen Max</option>
            <option value="qwen-plus">Qwen Plus</option>
            <option value="qwen-turbo">Qwen Turbo</option>
          </optgroup>
          <optgroup label="MiniMax">
            <option value="abab6.5s-chat">ABAB 6.5s Chat</option>
            <option value="abab5.5-chat">ABAB 5.5 Chat</option>
          </optgroup>
        </datalist>
      </div>

      <!-- Form Actions -->
      <div class="flex items-center justify-end space-x-3 pt-4 border-t border-zinc-700">
        <button
          @click="cancelEdit"
          class="px-4 py-2 bg-zinc-700 text-zinc-300 rounded-lg hover:bg-zinc-600 transition-colors"
        >
          取消
        </button>
        <button
          @click="saveProfile"
          :disabled="saving || !form.name"
          class="px-4 py-2 bg-white text-black rounded-lg hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span v-if="saving">保存中...</span>
          <span v-else>保存</span>
        </button>
      </div>
    </div>

    <!-- Global message -->
    <div
      v-if="globalMessage"
      :class="[
        'p-4 rounded-lg',
        globalMessage.success
          ? 'bg-emerald-900/30 border border-emerald-700 text-emerald-300'
          : 'bg-red-900/30 border border-red-700 text-red-300'
      ]"
    >
      {{ globalMessage.text }}
    </div>

    <!-- Info Box -->
    <div class="bg-zinc-800/50 border border-zinc-700 rounded-lg p-4">
      <h3 class="text-zinc-400 font-medium mb-2">常用服务商配置参考</h3>
      <div class="text-zinc-400 text-sm space-y-2">
        <div class="bg-zinc-800/50 rounded p-2">
          <span class="text-zinc-300">问问 AI</span>
          <div class="text-xs mt-1">
            Base URL: <code class="text-emerald-400">https://api.wenwen-ai.com/v1</code>
          </div>
        </div>
        <div class="bg-zinc-800/50 rounded p-2">
          <span class="text-zinc-300">Moonshot (Kimi)</span>
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
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAdminAuth } from '@/composables/useAdminAuth'

const { apiRequest } = useAdminAuth()

interface LlmProfile {
  id: string
  name: string
  base_url: string
  model: string
  has_api_key: boolean
  is_active: boolean
}

interface TestResult {
  success: boolean
  message: string
  latency_ms?: number
}

const profiles = ref<LlmProfile[]>([])
const editing = ref(false)
const isNew = ref(false)
const saving = ref(false)
const showApiKey = ref(false)
const testingId = ref<string | null>(null)
const activatingId = ref<string | null>(null)
const testResults = reactive<Record<string, TestResult>>({})
const globalMessage = ref<{ success: boolean; text: string } | null>(null)

const form = ref({
  id: '',
  name: '',
  api_key: '',
  base_url: '',
  model: 'gpt-4',
})

// Currently editing profile ID (for PUT vs POST)
const editingProfileId = ref<string | null>(null)

async function loadProfiles() {
  try {
    profiles.value = await apiRequest<LlmProfile[]>('/config/llm/profiles')
  } catch (error) {
    console.error('Failed to load profiles:', error)
  }
}

function startCreate() {
  editing.value = true
  isNew.value = true
  editingProfileId.value = null
  form.value = { id: '', name: '', api_key: '', base_url: '', model: 'gpt-4' }
  showApiKey.value = false
}

function startEdit(profile: LlmProfile) {
  editing.value = true
  isNew.value = false
  editingProfileId.value = profile.id
  form.value = {
    id: profile.id,
    name: profile.name,
    api_key: '',
    base_url: profile.base_url,
    model: profile.model,
  }
  showApiKey.value = false
}

function cancelEdit() {
  editing.value = false
  editingProfileId.value = null
}

async function saveProfile() {
  saving.value = true
  globalMessage.value = null

  try {
    const payload: Record<string, unknown> = {
      name: form.value.name,
      base_url: form.value.base_url,
      model: form.value.model,
    }

    if (form.value.api_key) {
      payload.api_key = form.value.api_key
    }

    if (isNew.value) {
      payload.id = form.value.id
      await apiRequest('/config/llm/profiles', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      globalMessage.value = { success: true, text: '方案创建成功' }
    } else {
      await apiRequest(`/config/llm/profiles/${editingProfileId.value}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      globalMessage.value = { success: true, text: '方案保存成功' }
    }

    editing.value = false
    editingProfileId.value = null
    await loadProfiles()
  } catch (error) {
    globalMessage.value = {
      success: false,
      text: error instanceof Error ? error.message : '保存失败',
    }
  } finally {
    saving.value = false
  }
}

async function testProfile(profileId: string) {
  testingId.value = profileId
  delete testResults[profileId]

  try {
    const result = await apiRequest<TestResult>(`/config/test/llm/${profileId}`, {
      method: 'POST',
    })
    testResults[profileId] = result
  } catch (error) {
    testResults[profileId] = {
      success: false,
      message: error instanceof Error ? error.message : '测试失败',
    }
  } finally {
    testingId.value = null
  }
}

async function activateProfile(profileId: string) {
  activatingId.value = profileId
  globalMessage.value = null

  try {
    await apiRequest(`/config/llm/profiles/${profileId}/activate`, {
      method: 'POST',
    })
    globalMessage.value = { success: true, text: '已切换激活方案' }
    await loadProfiles()
  } catch (error) {
    globalMessage.value = {
      success: false,
      text: error instanceof Error ? error.message : '激活失败',
    }
  } finally {
    activatingId.value = null
  }
}

async function deleteProfile(profileId: string, name: string) {
  if (!confirm(`确定删除方案「${name}」？此操作不可撤销。`)) return

  globalMessage.value = null

  try {
    await apiRequest(`/config/llm/profiles/${profileId}`, {
      method: 'DELETE',
    })
    globalMessage.value = { success: true, text: `已删除方案「${name}」` }
    await loadProfiles()
  } catch (error) {
    globalMessage.value = {
      success: false,
      text: error instanceof Error ? error.message : '删除失败',
    }
  }
}

onMounted(() => {
  loadProfiles()
})
</script>
