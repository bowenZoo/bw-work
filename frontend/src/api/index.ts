/**
 * Simple API client for making HTTP requests.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

interface ApiResponse<T = any> {
  data: T;
  status: number;
}

interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

async function request<T = any>(
  method: string,
  url: string,
  data?: any
): Promise<ApiResponse<T>> {
  const fullUrl = url.startsWith('/') ? `${API_BASE_URL}${url}` : url;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  // Auto-attach auth token if available
  try {
    const raw = localStorage.getItem('bw_user_tokens');
    if (raw) {
      const tokens = JSON.parse(raw);
      if (tokens.access_token) {
        headers['Authorization'] = `Bearer ${tokens.access_token}`;
      }
    }
  } catch { /* ignore */ }

  const options: RequestInit = {
    method,
    headers,
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(fullUrl, options);
  const responseData = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error: ApiError = {
      response: {
        data: responseData,
      },
    };
    throw error;
  }

  return {
    data: responseData,
    status: response.status,
  };
}

export default {
  get: <T = any>(url: string) => request<T>('GET', url),
  post: <T = any>(url: string, data?: any) => request<T>('POST', url, data),
  put: <T = any>(url: string, data?: any) => request<T>('PUT', url, data),
  delete: <T = any>(url: string) => request<T>('DELETE', url),
};
