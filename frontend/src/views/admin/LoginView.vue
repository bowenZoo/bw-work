<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-900 px-4">
    <div class="max-w-md w-full space-y-8">
      <!-- Header -->
      <div class="text-center">
        <h1 class="text-3xl font-bold text-white">管理后台登录</h1>
        <p class="mt-2 text-gray-400">登录以访问管理控制台</p>
      </div>

      <!-- Security Notice -->
      <div class="bg-blue-900/30 border border-blue-700 rounded-lg p-4 text-sm text-blue-300">
        <p>
          <strong>安全提示：</strong>本管理后台使用 JWT 认证，令牌存储于 localStorage。
          为确保安全，请在可信设备上使用，并在完成操作后退出登录。
        </p>
      </div>

      <!-- Login Form -->
      <form class="mt-8 space-y-6" @submit.prevent="handleSubmit">
        <!-- Error Message -->
        <div
          v-if="error"
          class="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300"
        >
          {{ error }}
        </div>

        <div class="space-y-4">
          <!-- Username -->
          <div>
            <label for="username" class="block text-sm font-medium text-gray-300">
              用户名
            </label>
            <input
              id="username"
              v-model="form.username"
              type="text"
              required
              autocomplete="username"
              class="mt-1 block w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="请输入用户名"
            />
          </div>

          <!-- Password -->
          <div>
            <label for="password" class="block text-sm font-medium text-gray-300">
              密码
            </label>
            <input
              id="password"
              v-model="form.password"
              type="password"
              required
              autocomplete="current-password"
              class="mt-1 block w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="请输入密码"
            />
          </div>
        </div>

        <!-- Submit Button -->
        <button
          type="submit"
          :disabled="loading || !isFormValid"
          class="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <svg
            v-if="loading"
            class="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            />
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <!-- Back Link -->
      <div class="text-center">
        <router-link
          to="/"
          class="text-sm text-gray-400 hover:text-gray-300 transition-colors"
        >
          返回主应用
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminAuth } from '@/composables/useAdminAuth'

const router = useRouter()
const { login, isAuthenticated, loading, error, clearError } = useAdminAuth()

const form = ref({
  username: '',
  password: '',
})

const isFormValid = computed(() => {
  return form.value.username.trim() !== '' && form.value.password !== ''
})

onMounted(() => {
  // If already authenticated, redirect to dashboard
  if (isAuthenticated) {
    router.push('/admin')
  }
  // Clear any previous errors
  clearError()
})

async function handleSubmit() {
  if (!isFormValid.value) return

  const success = await login({
    username: form.value.username,
    password: form.value.password,
  })

  if (success) {
    // Redirect to admin dashboard
    const redirect = router.currentRoute.value.query.redirect as string
    router.push(redirect || '/admin')
  }
}
</script>
