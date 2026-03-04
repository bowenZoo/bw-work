/**
 * Auth API client
 */

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

interface LoginRequest {
  username: string;
  password: string;
}

interface RegisterRequest {
  username: string;
  password: string;
  display_name?: string;
  email?: string;
  avatar?: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

export interface UserInfo {
  id: number;
  username: string;
  display_name: string | null;
  email: string | null;
  role: 'superadmin' | 'user';
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

async function authRequest<T>(method: string, url: string, data?: any, token?: string): Promise<T> {
  const fullUrl = `${API_BASE_URL}${url}`;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const options: RequestInit = { method, headers };
  if (data) options.body = JSON.stringify(data);

  const response = await fetch(fullUrl, options);
  const responseData = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(responseData.detail || `Request failed: ${response.status}`);
  }
  return responseData;
}

export const authApi = {
  login: (data: LoginRequest) => authRequest<TokenResponse>('POST', '/api/auth/login', data),
  register: (data: RegisterRequest) => authRequest<TokenResponse>('POST', '/api/auth/register', data),
  refresh: (refresh_token: string) => authRequest<TokenResponse>('POST', '/api/auth/refresh', { refresh_token }),
  logout: (token: string) => authRequest<any>('POST', '/api/auth/logout', undefined, token),
  getMe: (token: string) => authRequest<UserInfo>('GET', '/api/auth/me', undefined, token),
  updateMe: (token: string, data: { display_name?: string; email?: string }) =>
    authRequest<UserInfo>('PUT', '/api/auth/me', data, token),
  changePassword: (token: string, data: { old_password: string; new_password: string }) =>
    authRequest<any>('PUT', '/api/auth/password', data, token),
};

// Admin user management
export interface UserListResponse {
  items: UserInfo[];
  total: number;
  page: number;
  limit: number;
}

export const usersApi = {
  list: (token: string, page = 1, limit = 20, search?: string) => {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) params.set('search', search);
    return authRequest<UserListResponse>('GET', `/api/admin/users?${params}`, undefined, token);
  },
  update: (token: string, userId: number, data: { role?: string; is_active?: boolean; display_name?: string }) =>
    authRequest<UserInfo>('PUT', `/api/admin/users/${userId}`, data, token),
  delete: (token: string, userId: number) =>
    authRequest<any>('DELETE', `/api/admin/users/${userId}`, undefined, token),
  resetPassword: (token: string, userId: number) =>
    authRequest<{ new_password: string }>('POST', `/api/admin/users/${userId}/reset-password`, undefined, token),
};
