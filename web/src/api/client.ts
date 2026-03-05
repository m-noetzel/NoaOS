/**
 * API client with auth token management and auto-refresh.
 * All requests go through apiClient which adds Authorization header
 * and handles 401 token refresh transparently.
 */

const API_BASE = "http://localhost:8000/api/v1";

interface ApiResponse<T = unknown> {
  data: T;
  meta?: {
    request_id: string;
    trace_id: string;
    timestamp: string;
  };
  error?: {
    code: string;
    message: string;
  };
}

async function refreshTokens(): Promise<boolean> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        refresh_token: refreshToken,
        device_id: "web-client",
      }),
    });

    if (!res.ok) return false;

    const json: ApiResponse<{
      access_token: string;
      refresh_token: string;
    }> = await res.json();

    if (json.data) {
      localStorage.setItem("access_token", json.data.access_token);
      localStorage.setItem("refresh_token", json.data.refresh_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

async function request<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResponse<T>> {
  const token = localStorage.getItem("access_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // Auto-refresh on 401
  if (res.status === 401) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      const newToken = localStorage.getItem("access_token");
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
      });
    }
  }

  const json: ApiResponse<T> = await res.json();

  if (!res.ok && !json.data) {
    throw new Error(json.error?.message ?? `Request failed: ${res.status}`);
  }

  return json;
}

export const apiClient = {
  get<T = unknown>(path: string): Promise<ApiResponse<T>> {
    return request<T>(path, { method: "GET" });
  },

  post<T = unknown>(
    path: string,
    body?: unknown,
  ): Promise<ApiResponse<T>> {
    return request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  },
};

export async function login(
  username: string,
  password: string,
): Promise<{ access_token: string; refresh_token: string }> {
  const res = await apiClient.post<{
    access_token: string;
    refresh_token: string;
  }>("/auth/login", {
    username,
    password,
    device_id: "web-client",
  });

  const tokens = res.data;
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
  return tokens;
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post("/auth/logout");
  } finally {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }
}
