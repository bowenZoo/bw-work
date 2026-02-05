/**
 * Admin state management store.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// Token storage key
const ACCESS_TOKEN_KEY = 'admin_access_token'
const REFRESH_TOKEN_KEY = 'admin_refresh_token'

// Token storage mode - can be changed to sessionStorage for enhanced security
const storage = localStorage

export interface AdminUser {
  id: number
  username: string
  created_at: string
  last_login: string | null
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export const useAdminStore = defineStore('admin', () => {
  // State
  const user = ref<AdminUser | null>(null)
  const accessToken = ref<string | null>(storage.getItem(ACCESS_TOKEN_KEY))
  const refreshToken = ref<string | null>(storage.getItem(REFRESH_TOKEN_KEY))
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!accessToken.value)
  const currentUser = computed(() => user.value)

  // Actions
  function setTokens(tokens: LoginResponse) {
    accessToken.value = tokens.access_token
    refreshToken.value = tokens.refresh_token
    storage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
    storage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
  }

  function clearTokens() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    storage.removeItem(ACCESS_TOKEN_KEY)
    storage.removeItem(REFRESH_TOKEN_KEY)
  }

  function setUser(userData: AdminUser) {
    user.value = userData
  }

  function setLoading(isLoading: boolean) {
    loading.value = isLoading
  }

  function setError(errorMessage: string | null) {
    error.value = errorMessage
  }

  function clearError() {
    error.value = null
  }

  // Get current access token
  function getAccessToken(): string | null {
    return accessToken.value
  }

  // Get current refresh token
  function getRefreshToken(): string | null {
    return refreshToken.value
  }

  return {
    // State
    user,
    accessToken,
    refreshToken,
    loading,
    error,
    // Getters
    isAuthenticated,
    currentUser,
    // Actions
    setTokens,
    clearTokens,
    setUser,
    setLoading,
    setError,
    clearError,
    getAccessToken,
    getRefreshToken,
  }
})
