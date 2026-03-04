import { useUserStore } from '@/stores/user';

export function useAdminApi() {
  const userStore = useUserStore();

  async function adminRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };
    if (userStore.accessToken) {
      headers['Authorization'] = `Bearer ${userStore.accessToken}`;
    }
    const resp = await fetch(`/api/admin${endpoint}`, { ...options, headers });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || err.message || `HTTP ${resp.status}`);
    }
    return resp.json();
  }

  return { adminRequest };
}
