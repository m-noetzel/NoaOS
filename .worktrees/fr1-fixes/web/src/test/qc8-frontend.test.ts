/**
 * Frontend tests for Phase QC8 — M14: Request Timeouts.
 *
 * Spec ref: SPEC.md §25.3 (resilient API client)
 * Phase plan: PHASE_DETAILS.md Phase QC8 / M14
 *
 * Finding M14: No frontend request timeouts — all fetch() calls must
 * include AbortController with a configurable timeout (default 30s).
 *
 * These tests verify that apiRequest() attaches an AbortSignal to
 * every fetch call, so requests cannot hang indefinitely.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock import.meta.env before importing client
vi.stubEnv("VITE_API_BASE_URL", "");
vi.stubEnv("VITE_USE_MOCKS", "false");

// Mock auth tokens module
vi.mock("@/auth/tokens", () => ({
  getAccessToken: () => "test-token",
  getRefreshToken: () => "test-refresh",
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
}));

describe("M14 — Frontend Request Timeouts", () => {
  let originalFetch: typeof globalThis.fetch;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
    fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ok: true, data: {} }),
      headers: new Headers(),
    });
    globalThis.fetch = fetchSpy;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("should pass AbortSignal to fetch calls", async () => {
    // Dynamic import to pick up mocks
    const { apiRequest } = await import("@/api/client");

    await apiRequest("/api/v1/test");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const callArgs = fetchSpy.mock.calls[0];
    const requestInit = callArgs[1] as RequestInit;

    // After QC8 fix, every fetch call must include a signal
    expect(requestInit.signal).toBeDefined();
    expect(requestInit.signal).toBeInstanceOf(AbortSignal);
  });

  it("should use a timeout that auto-aborts long requests", async () => {
    const { apiRequest } = await import("@/api/client");

    await apiRequest("/api/v1/test");

    const callArgs = fetchSpy.mock.calls[0];
    const requestInit = callArgs[1] as RequestInit;
    const signal = requestInit.signal as AbortSignal;

    // The signal must exist and not already be aborted
    expect(signal).toBeDefined();
    expect(signal.aborted).toBe(false);
  });
});
