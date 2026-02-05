/**
 * Admin authentication composable.
 */

import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore, type AdminUser, type LoginResponse } from '@/stores/admin'

const API_BASE = '/api/admin'

export interface LoginCredentials {
  username: string
  password: string
}

export interface AuthError {
  detail: string
  error_code?: string
}

export function useAdminAuth() {
  const store = useAdminStore()
  const router = useRouter()
  const isRefreshing = ref(false)

  /**
   * Make authenticated API request
   */
  async function apiRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = store.getAccessToken()

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    })

    if (response.status === 401 && token && !isRefreshing.value) {
      // Try to refresh token
      const refreshed = await refreshTokens()
      if (refreshed) {
        // Retry the request with new token
        const newToken = store.getAccessToken()
        if (newToken) {
          (headers as Record<string, string>)['Authorization'] = `Bearer ${newToken}`
        }
        const retryResponse = await fetch(`${API_BASE}${endpoint}`, {
          ...options,
          headers,
        })
        if (retryResponse.ok) {
          return retryResponse.json()
        }
      }
      // Refresh failed, redirect to login
      await logout(false)
      router.push('/admin/login')
      throw new Error('Session expired')
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(errorData.detail || 'Request failed')
    }

    // Handle empty responses
    const text = await response.text()
    if (!text) {
      return {} as T
    }
    return JSON.parse(text)
  }

  /**
   * Login with credentials
   */
  async function login(credentials: LoginCredentials): Promise<boolean> {
    store.setLoading(true)
    store.clearError()

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Login failed' }))

        if (response.status === 423) {
          // Account locked
          store.setError('账号已锁定，登录失败次数过多，请稍后再试')
        } else {
          store.setError(errorData.detail === 'Invalid username or password' ? '用户名或密码错误' : (errorData.detail || '登录失败'))
        }
        return false
      }

      const tokens: LoginResponse = await response.json()
      store.setTokens(tokens)

      // Fetch user info
      await fetchCurrentUser()

      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed'
      store.setError(message)
      return false
    } finally {
      store.setLoading(false)
    }
  }

  /**
   * Logout current user
   */
  async function logout(callApi = true): Promise<void> {
    if (callApi && store.getRefreshToken()) {
      try {
        await apiRequest('/auth/logout', {
          method: 'POST',
          body: JSON.stringify({ refresh_token: store.getRefreshToken() }),
        })
      } catch {
        // Ignore logout errors
      }
    }

    store.clearTokens()
  }

  /**
   * Refresh access token
   */
  async function refreshTokens(): Promise<boolean> {
    const refreshToken = store.getRefreshToken()
    if (!refreshToken || isRefreshing.value) {
      return false
    }

    isRefreshing.value = true

    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      if (!response.ok) {
        return false
      }

      const tokens: LoginResponse = await response.json()
      store.setTokens(tokens)
      return true
    } catch {
      return false
    } finally {
      isRefreshing.value = false
    }
  }

  /**
   * Fetch current user info
   */
  async function fetchCurrentUser(): Promise<AdminUser | null> {
    try {
      const user = await apiRequest<AdminUser>('/auth/me')
      store.setUser(user)
      return user
    } catch {
      return null
    }
  }

  /**
   * Check if user is authenticated and token is valid
   */
  async function checkAuth(): Promise<boolean> {
    if (!store.isAuthenticated) {
      return false
    }

    // Try to fetch user info to validate token
    const user = await fetchCurrentUser()
    return user !== null
  }

  /**
   * Logout from all sessions
   */
  async function logoutAll(): Promise<void> {
    try {
      await apiRequest('/auth/logout-all', {
        method: 'POST',
      })
    } finally {
      store.clearTokens()
    }
  }

  return {
    // State from store
    isAuthenticated: store.isAuthenticated,
    currentUser: store.currentUser,
    loading: store.loading,
    error: store.error,
    // Actions
    login,
    logout,
    refreshTokens,
    fetchCurrentUser,
    checkAuth,
    logoutAll,
    apiRequest,
    clearError: store.clearError,
  }
}
