import type { ApiResponse, AuthTokens, RefreshRequest } from "./types";
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from "@/auth/tokens";

// In dev, Vite proxy handles /api → backend. In production, same origin.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

const WEB_DEVICE_ID = "web-client";

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

function generateIdempotencyKey(): string {
  return crypto.randomUUID();
}

async function refreshAccessToken(): Promise<boolean> {
  // C6: Refresh token is in httpOnly cookie, sent automatically
  try {
    const body: RefreshRequest = { refresh_token: "", device_id: WEB_DEVICE_ID };
    const res = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "include",
    });

    if (!res.ok) {
      clearTokens();
      return false;
    }

    const envelope = await res.json();
    if (!envelope.ok || envelope.error) {
      clearTokens();
      return false;
    }

    // Tokens are in httpOnly cookies; just confirm auth state
    setTokens("", "");
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

  const method = (options.method || "GET").toUpperCase();
  const isWrite = method === "POST" || method === "PUT" || method === "DELETE" || method === "PATCH";

  const makeRequest = async (): Promise<Response> => {
    const token = getAccessToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // §25.4: Idempotency key for all write operations
    if (isWrite) {
      headers["Idempotency-Key"] = generateIdempotencyKey();
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30_000);
    try {
      return await fetch(`${BASE_URL}${path}`, { ...options, headers, credentials: "include", signal: controller.signal });
    } finally {
      clearTimeout(timeoutId);
    }
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

  // §19.3: Rate limit handling
  if (response.status === 429) {
    const retryAfter = response.headers.get("Retry-After");
    throw new Error(
      retryAfter
        ? `Rate limited. Try again in ${retryAfter} seconds.`
        : "Too many requests. Please wait before trying again."
    );
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

export { BASE_URL, WEB_DEVICE_ID };
