import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { authApi, type UserInfo } from '@/api/auth';

const STORAGE_KEY = 'bw_user_tokens';

interface StoredTokens {
  access_token: string;
  refresh_token: string;
}

export const useUserStore = defineStore('user', () => {
  const user = ref<UserInfo | null>(null);
  const accessToken = ref<string | null>(null);
  const refreshToken = ref<string | null>(null);

  const isAuthenticated = computed(() => !!accessToken.value && !!user.value);
  const isAdmin = computed(() => user.value?.role === 'superadmin');

  // Load from localStorage on init
  function loadFromStorage() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const tokens: StoredTokens = JSON.parse(raw);
        accessToken.value = tokens.access_token;
        refreshToken.value = tokens.refresh_token;
        return true;
      }
    } catch { /* ignore */ }
    return false;
  }

  function saveToStorage() {
    if (accessToken.value && refreshToken.value) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        access_token: accessToken.value,
        refresh_token: refreshToken.value,
      }));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  function setTokens(at: string, rt: string, u: UserInfo) {
    accessToken.value = at;
    refreshToken.value = rt;
    user.value = u;
    saveToStorage();
  }

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password });
    setTokens(res.access_token, res.refresh_token, res.user);
  }

  async function register(username: string, password: string, display_name?: string, avatar?: string) {
    const res = await authApi.register({ username, password, display_name, avatar });
    setTokens(res.access_token, res.refresh_token, res.user);
  }

  async function logout() {
    if (accessToken.value) {
      try { await authApi.logout(accessToken.value); } catch { /* ignore */ }
    }
    user.value = null;
    accessToken.value = null;
    refreshToken.value = null;
    saveToStorage();
  }

  async function doRefreshToken() {
    if (!refreshToken.value) throw new Error('No refresh token');
    const res = await authApi.refresh(refreshToken.value);
    setTokens(res.access_token, res.refresh_token, res.user);
  }

  async function fetchMe() {
    if (!accessToken.value) return;
    try {
      const u = await authApi.getMe(accessToken.value);
      user.value = u;
    } catch {
      // Token might be expired, try refresh
      try {
        await doRefreshToken();
      } catch {
        await logout();
      }
    }
  }

  async function init() {
    if (loadFromStorage()) {
      await fetchMe();
    }
  }


  async function updateProfile(data: { display_name?: string; avatar?: string; email?: string }) {
    const resp = await authApi.updateMe(accessToken.value!, data);
    user.value = resp;
    saveToStorage();
    return resp;
  }

  async function changePassword(old_password: string, new_password: string) {
    await authApi.changePassword(accessToken.value!, { old_password, new_password });
  }

  return {
    user, accessToken, refreshToken,
    isAuthenticated, isAdmin,
    login, register, logout, doRefreshToken, fetchMe, init, updateProfile, changePassword,
  };
});
