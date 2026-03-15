import { describe, it, expect, beforeEach, vi } from "vitest";
import { handleMockRequest } from "@/api/mock/handlers";
import type { ApiResponse } from "@/api/types";
import {
  setTokens,
  getAccessToken,
  getRefreshToken,
  clearTokens,
  hasTokens,
} from "@/auth/tokens";

// Ensure crypto.randomUUID is available in jsdom
if (!globalThis.crypto?.randomUUID) {
  vi.stubGlobal("crypto", {
    ...globalThis.crypto,
    randomUUID: () => "00000000-0000-0000-0000-000000000000",
  });
}

// ----------------------------------------------------------------
// 1. API Types
// ----------------------------------------------------------------
describe("API Types", () => {
  it("ApiResponse envelope has ok, data, error, and trace_id fields", () => {
    const response: ApiResponse<string> = {
      ok: true,
      data: "hello",
      error: null,
      trace_id: "abc-123",
    };

    expect(response).toHaveProperty("ok");
    expect(response).toHaveProperty("data");
    expect(response).toHaveProperty("error");
    expect(response).toHaveProperty("trace_id");
  });

  it("ApiResponse error variant carries code and message", () => {
    const response: ApiResponse<null> = {
      ok: false,
      data: null,
      error: { code: "NOT_FOUND", message: "Resource not found" },
      trace_id: "def-456",
    };

    expect(response.ok).toBe(false);
    expect(response.error).toBeTruthy();
    expect(response.error!.code).toBe("NOT_FOUND");
    expect(response.error!.message).toBe("Resource not found");
  });
});

// ----------------------------------------------------------------
// 2. Mock Handlers
// ----------------------------------------------------------------
describe("Mock Handlers", () => {
  it("POST /api/v1/auth/login returns access_token and refresh_token", async () => {
    const res = await handleMockRequest("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@b.com", password: "pw", device_id: "d1" }),
    });

    expect(res.ok).toBe(true);
    expect(res.data).toBeTruthy();
    const data = res.data as { access_token: string; refresh_token: string };
    expect(data.access_token).toBeTruthy();
    expect(data.refresh_token).toBeTruthy();
  });

  it("GET /api/v1/threads returns ok", async () => {
    const res = await handleMockRequest("/api/v1/threads");

    expect(res.ok).toBe(true);
    expect(Array.isArray(res.data)).toBe(true);
  });

  it("GET /api/v1/memory/facts returns ok", async () => {
    const res = await handleMockRequest("/api/v1/memory/facts");

    expect(res.ok).toBe(true);
    expect(Array.isArray(res.data)).toBe(true);
  });

  it("GET /api/v1/settings returns ok with default_model", async () => {
    const res = await handleMockRequest("/api/v1/settings");

    expect(res.ok).toBe(true);
    const data = res.data as {
      default_model: string;
      default_privacy_mode: string;
      budget_daily_usd: number;
      budget_monthly_usd: number;
    };
    expect(data.default_model).toBeTruthy();
    expect(data.default_privacy_mode).toBeTruthy();
    expect(typeof data.budget_daily_usd).toBe("number");
    expect(typeof data.budget_monthly_usd).toBe("number");
  });

  it("PUT /api/v1/settings returns ok", async () => {
    const res = await handleMockRequest("/api/v1/settings", {
      method: "PUT",
      body: JSON.stringify({ default_model: "gpt-4o" }),
    });

    expect(res.ok).toBe(true);
  });

  it("POST /api/v1/threads creates and returns a new thread", async () => {
    const res = await handleMockRequest("/api/v1/threads", {
      method: "POST",
      body: JSON.stringify({ title: "New Thread" }),
    });

    expect(res.ok).toBe(true);
    const data = res.data as { id: string; title: string; message_count: number };
    expect(data.id).toBeTruthy();
    expect(data.title).toBe("New Thread");
    expect(data.message_count).toBe(0);
  });

  it("POST /api/v1/memory/facts/{id}/approve returns ok", async () => {
    const res = await handleMockRequest("/api/v1/memory/facts/f1/approve", {
      method: "POST",
    });

    expect(res.ok).toBe(true);
    const data = res.data as { id: string; status: string };
    expect(data.id).toBe("f1");
  });

  it("DELETE /api/v1/memory/facts/{id} returns ok", async () => {
    const res = await handleMockRequest("/api/v1/memory/facts/f2", {
      method: "DELETE",
    });

    expect(res.ok).toBe(true);
    const data = res.data as { id: string; status: string };
    expect(data.id).toBe("f2");
    expect(data.status).toBe("deleted");
  });

  it("POST /api/v1/approvals/{id}/decide returns ok", async () => {
    const res = await handleMockRequest("/api/v1/approvals/a1/decide", {
      method: "POST",
      body: JSON.stringify({ decision: "approved" }),
    });

    expect(res.ok).toBe(true);
    const data = res.data as { approval_id: string; status: string };
    expect(data.approval_id).toBe("a1");
    expect(data.status).toBe("decided");
  });

  it("returns error for unknown routes", async () => {
    const res = await handleMockRequest("/api/v1/nonexistent");

    expect(res.ok).toBe(false);
    expect(res.error).toBeTruthy();
    expect(res.error!.code).toBe("NOT_FOUND");
  });
});

// ----------------------------------------------------------------
// 3. Token Storage
// ----------------------------------------------------------------
describe("Token Storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("setTokens is a no-op (AU1: tokens live in httpOnly cookies)", () => {
    setTokens("access_abc", "refresh_xyz");

    // AU1: tokens.ts is a no-op stub — auth state comes from /auth/me startup check
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(hasTokens()).toBe(false);
  });

  it("clearTokens is a no-op (AU1: no localStorage flag to clear)", () => {
    setTokens("access_abc", "refresh_xyz");
    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("hasTokens always returns false (AU1: no localStorage auth flag)", () => {
    expect(hasTokens()).toBe(false);

    setTokens("access_abc", "refresh_xyz");
    expect(hasTokens()).toBe(false);
  });

  it("hasTokens returns false regardless of localStorage contents (AU1)", () => {
    localStorage.setItem("noa_access_token", "access_abc");
    expect(hasTokens()).toBe(false);
  });
});
