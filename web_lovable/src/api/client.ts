import type { ApiResponse, AuthTokens, RefreshRequest } from "./types";
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from "@/auth/tokens";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true" || !import.meta.env.VITE_API_BASE_URL;

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;

  try {
    const res = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh } satisfies RefreshRequest),
    });

    if (!res.ok) {
      clearTokens();
      return false;
    }

    const envelope: ApiResponse<AuthTokens> = await res.json();
    if (envelope.error) {
      clearTokens();
      return false;
    }

    setTokens(envelope.data.access_token, envelope.data.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

async function handleTokenRefresh(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  isRefreshing = true;
  refreshPromise = refreshAccessToken().finally(() => {
    isRefreshing = false;
    refreshPromise = null;
  });

  return refreshPromise;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  if (USE_MOCKS) {
    const { handleMockRequest } = await import("./mock/handlers");
    return handleMockRequest<T>(path, options);
  }

  const makeRequest = async (): Promise<Response> => {
    const token = getAccessToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return fetch(`${BASE_URL}${path}`, { ...options, headers });
  };

  let response = await makeRequest();

  // 401 → try refresh → retry once
  if (response.status === 401) {
    const refreshed = await handleTokenRefresh();
    if (refreshed) {
      response = await makeRequest();
    } else {
      clearTokens();
      window.location.href = "/login";
      throw new Error("Session expired");
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `Request failed: ${response.status}`);
  }

  return response.json();
}

export function getSSEUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

export function isUsingMocks(): boolean {
  return USE_MOCKS;
}

export { BASE_URL };
