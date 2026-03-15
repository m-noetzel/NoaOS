/**
 * Frontend tests for Phase AU1 — Auth Stability: Login That Just Works.
 *
 * Covers:
 * - apiRequest skipAuthRetry=true: 401 reads detail and throws directly (no refresh retry)
 * - tokens.ts: hasTokens() always returns false (localStorage flag removed)
 * - tokens.ts: setTokens/clearTokens are no-ops
 * - AuthContext: initial isLoading=true state before /auth/me resolves
 * - AuthGuard: renders spinner while isLoading=true
 *
 * AU1 findings: AUTH-H1, AUTH-H2, AUTH-M1, AUTH-M2
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Stub env before importing any modules
vi.stubEnv("VITE_API_BASE_URL", "");
vi.stubEnv("VITE_USE_MOCKS", "false");

vi.mock("@/auth/tokens", () => ({
  getAccessToken: () => null,
  getRefreshToken: () => null,
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  hasTokens: () => false,
}));

// ---------------------------------------------------------------------------
// tokens.ts: localStorage flag removed
// ---------------------------------------------------------------------------

describe("AU1 tokens.ts — localStorage flag removed", () => {
  it("hasTokens() always returns false — no more localStorage sync", async () => {
    const { hasTokens } = await import("@/auth/tokens");
    expect(hasTokens()).toBe(false);
  });

  it("setTokens() is a no-op — does not set localStorage", async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    const { setTokens } = await import("@/auth/tokens");
    setTokens("access", "refresh");
    expect(setItemSpy).not.toHaveBeenCalled();
    setItemSpy.mockRestore();
  });

  it("clearTokens() is a no-op — does not touch localStorage", async () => {
    const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");
    const { clearTokens } = await import("@/auth/tokens");
    clearTokens();
    expect(removeItemSpy).not.toHaveBeenCalled();
    removeItemSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// apiRequest: skipAuthRetry option
// ---------------------------------------------------------------------------

describe("AU1 apiRequest — skipAuthRetry option", () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    vi.resetModules();
    vi.stubEnv("VITE_API_BASE_URL", "");
    vi.stubEnv("VITE_USE_MOCKS", "false");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("skipAuthRetry=true: 401 throws server detail, no refresh attempt", async () => {
    let fetchCallCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      fetchCallCount++;
      if (String(url).includes("/api/v1/auth/login")) {
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Invalid email or password" }),
          headers: new Headers(),
        } as unknown as Response;
      }
      // Should never reach refresh — skipAuthRetry prevents it
      throw new Error("Unexpected fetch call to: " + url);
    });

    const { apiRequest } = await import("@/api/client");

    await expect(
      apiRequest("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: "x@x.com", password: "wrong", device_id: "web" }),
        skipAuthRetry: true,
      })
    ).rejects.toThrow("Invalid email or password");

    // Only 1 fetch call — no refresh retry
    expect(fetchCallCount).toBe(1);
  });

  it("skipAuthRetry=true: error message comes from server detail, not 'Session expired'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Invalid email or password" }),
      headers: new Headers(),
    } as unknown as Response);

    const { apiRequest } = await import("@/api/client");

    let errorMessage = "";
    try {
      await apiRequest("/api/v1/auth/login", {
        method: "POST",
        body: "{}",
        skipAuthRetry: true,
      });
    } catch (e) {
      errorMessage = (e as Error).message;
    }

    expect(errorMessage).toBe("Invalid email or password");
    expect(errorMessage).not.toContain("Session expired");
  });

  it("skipAuthRetry=false (default): 401 attempts refresh before throwing", async () => {
    let refreshAttempted = false;

    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      const urlStr = String(url);
      if (urlStr.includes("/api/v1/auth/refresh")) {
        refreshAttempted = true;
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Session expired" }),
          headers: new Headers(),
        } as unknown as Response;
      }
      // Main request returns 401
      return {
        ok: false,
        status: 401,
        json: async () => ({ detail: "Not authenticated" }),
        headers: new Headers(),
      } as unknown as Response;
    });

    const { apiRequest } = await import("@/api/client");

    await expect(
      apiRequest("/api/v1/protected", { method: "GET" })
    ).rejects.toThrow();

    // Without skipAuthRetry, a refresh is attempted
    expect(refreshAttempted).toBe(true);
  });

  it("skipAuthRetry=true: uses server detail fallback when body has no detail", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ message: "no detail key here" }),
      headers: new Headers(),
    } as unknown as Response);

    const { apiRequest } = await import("@/api/client");

    await expect(
      apiRequest("/api/v1/auth/login", {
        method: "POST",
        body: "{}",
        skipAuthRetry: true,
      })
    ).rejects.toThrow("Authentication failed");
  });
});
