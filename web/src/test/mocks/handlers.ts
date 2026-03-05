import { http, HttpResponse } from "msw";

const API_BASE = "http://localhost:8000/api/v1";

export const handlers = [
  // Auth: login
  http.post(`${API_BASE}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as Record<string, string>;
    if (body.username === "test" && body.password === "password") {
      return HttpResponse.json({
        data: {
          access_token: "test-access-token",
          refresh_token: "test-refresh-token",
        },
        meta: {
          request_id: "req-1",
          trace_id: "trace-1",
          timestamp: new Date().toISOString(),
        },
      });
    }
    return HttpResponse.json(
      {
        error: { code: "UNAUTHORIZED", message: "Invalid credentials" },
        meta: {
          request_id: "req-1",
          trace_id: "trace-1",
          timestamp: new Date().toISOString(),
        },
      },
      { status: 401 },
    );
  }),

  // Auth: refresh
  http.post(`${API_BASE}/auth/refresh`, async () => {
    return HttpResponse.json({
      data: {
        access_token: "new-access-token",
        refresh_token: "new-refresh-token",
      },
      meta: {
        request_id: "req-2",
        trace_id: "trace-2",
        timestamp: new Date().toISOString(),
      },
    });
  }),

  // Auth: logout
  http.post(`${API_BASE}/auth/logout`, async () => {
    return HttpResponse.json({
      data: { success: true },
      meta: {
        request_id: "req-3",
        trace_id: "trace-3",
        timestamp: new Date().toISOString(),
      },
    });
  }),

  // Approvals: pending
  http.get(`${API_BASE}/approvals/pending`, async () => {
    return HttpResponse.json({
      data: [],
      meta: {
        request_id: "req-4",
        trace_id: "trace-4",
        timestamp: new Date().toISOString(),
      },
    });
  }),
];
