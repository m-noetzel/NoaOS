import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mocks/server";
import { apiClient, login, logout } from "../api/client";

const API_BASE = "http://localhost:8000/api/v1";

describe("apiClient", () => {
  beforeEach(() => {
    // Clear any stored tokens before each test
    localStorage.clear();
  });

  it("includes Authorization header from stored token", async () => {
    let capturedHeaders: Headers | null = null;

    server.use(
      http.get(`${API_BASE}/approvals/pending`, ({ request }) => {
        capturedHeaders = new Headers(request.headers);
        return HttpResponse.json({
          data: [],
          meta: {
            request_id: "req-1",
            trace_id: "trace-1",
            timestamp: new Date().toISOString(),
          },
        });
      }),
    );

    // Store a token
    localStorage.setItem("access_token", "my-secret-token");

    await apiClient.get("/approvals/pending");

    expect(capturedHeaders).not.toBeNull();
    expect(capturedHeaders!.get("Authorization")).toBe(
      "Bearer my-secret-token",
    );
  });

  it("refreshes token on 401 response", async () => {
    let callCount = 0;

    server.use(
      http.get(`${API_BASE}/approvals/pending`, () => {
        callCount++;
        if (callCount === 1) {
          return HttpResponse.json(
            {
              error: { code: "UNAUTHORIZED", message: "Token expired" },
              meta: {
                request_id: "req-1",
                trace_id: "trace-1",
                timestamp: new Date().toISOString(),
              },
            },
            { status: 401 },
          );
        }
        return HttpResponse.json({
          data: [],
          meta: {
            request_id: "req-2",
            trace_id: "trace-2",
            timestamp: new Date().toISOString(),
          },
        });
      }),
    );

    localStorage.setItem("access_token", "expired-token");
    localStorage.setItem("refresh_token", "valid-refresh-token");

    const response = await apiClient.get("/approvals/pending");

    // Should have retried after refreshing token
    expect(callCount).toBe(2);
    expect(response.data).toEqual([]);

    // Token should be updated in storage
    expect(localStorage.getItem("access_token")).toBe("new-access-token");
  });

  it("login stores tokens and returns user data", async () => {
    const result = await login("test", "password");

    expect(result.access_token).toBe("test-access-token");
    expect(result.refresh_token).toBe("test-refresh-token");

    // Tokens should be stored in localStorage
    expect(localStorage.getItem("access_token")).toBe("test-access-token");
    expect(localStorage.getItem("refresh_token")).toBe("test-refresh-token");
  });

  it("logout clears stored tokens", async () => {
    localStorage.setItem("access_token", "some-token");
    localStorage.setItem("refresh_token", "some-refresh-token");

    await logout();

    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });
});
