import type { ApiResponse } from "../types";
import {
  mockThreads, mockMessages, mockRuns, mockRunEvents,
  mockApprovals, mockQueue, mockFacts, mockArtifacts,
  mockCostRecords, mockCostSummary,
} from "./data";

function envelope<T>(data: T): ApiResponse<T> {
  return {
    ok: true,
    data,
    error: null,
    trace_id: crypto.randomUUID(),
  };
}

function errorEnvelope(code: string, message: string): ApiResponse<null> {
  return {
    ok: false,
    data: null,
    error: { code, message },
    trace_id: crypto.randomUUID(),
  };
}

// Simulated delay
const delay = (ms = 200) => new Promise((r) => setTimeout(r, ms));

export async function handleMockRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  await delay();

  const method = (options.method || "GET").toUpperCase();

  // Auth
  if (path === "/api/v1/auth/login" && method === "POST") {
    return envelope({
      access_token: "mock_access_token_" + Date.now(),
      refresh_token: "mock_refresh_token_" + Date.now(),
    }) as ApiResponse<T>;
  }

  if (path === "/api/v1/auth/refresh" && method === "POST") {
    return envelope({
      access_token: "mock_access_token_refreshed_" + Date.now(),
      refresh_token: "mock_refresh_token_refreshed_" + Date.now(),
    }) as ApiResponse<T>;
  }

  if (path === "/api/v1/auth/logout" && method === "POST") {
    return envelope({ status: "logged_out" }) as ApiResponse<T>;
  }

  // Threads
  if (path === "/api/v1/threads" && method === "GET") {
    return envelope(mockThreads) as ApiResponse<T>;
  }

  if (path === "/api/v1/threads" && method === "POST") {
    return envelope({
      id: "t_" + Date.now(),
      title: "New Thread",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
    }) as ApiResponse<T>;
  }

  // Messages
  const messagesMatch = path.match(/\/api\/v1\/threads\/(.+)\/messages/);
  if (messagesMatch && method === "GET") {
    const threadId = messagesMatch[1];
    return envelope(mockMessages.filter((m) => m.thread_id === threadId)) as ApiResponse<T>;
  }

  // Runs
  if (path === "/api/v1/runs" && method === "GET") {
    return envelope(mockRuns) as ApiResponse<T>;
  }

  const runEventsMatch = path.match(/\/api\/v1\/runs\/(.+)\/events/);
  if (runEventsMatch && method === "GET") {
    const runId = runEventsMatch[1];
    return envelope(mockRunEvents.filter((e) => e.run_id === runId)) as ApiResponse<T>;
  }

  const runArtifactsMatch = path.match(/\/api\/v1\/runs\/(.+)\/artifacts/);
  if (runArtifactsMatch && method === "GET") {
    const runId = runArtifactsMatch[1];
    return envelope(mockArtifacts.filter((a) => a.run_id === runId)) as ApiResponse<T>;
  }

  const runDetailMatch = path.match(/\/api\/v1\/runs\/([^/]+)$/);
  if (runDetailMatch && method === "GET") {
    const run = mockRuns.find((r) => r.id === runDetailMatch[1]);
    return envelope(run || null) as ApiResponse<T>;
  }

  // Replay
  const replayMatch = path.match(/\/api\/v1\/runs\/(.+)\/replay/);
  if (replayMatch && method === "POST") {
    const originalRunId = replayMatch[1];
    const originalRun = mockRuns.find((r) => r.id === originalRunId);
    return envelope({
      ...(originalRun || mockRuns[0]),
      id: "r_replay_" + Date.now(),
      replay_of: { original_run_id: originalRunId, mode: "full" },
    }) as ApiResponse<T>;
  }

  // Approvals
  if (path === "/api/v1/approvals/pending" && method === "GET") {
    return envelope(mockApprovals.filter((a) => a.status === "pending")) as ApiResponse<T>;
  }

  if (path === "/api/v1/approvals" && method === "GET") {
    return envelope(mockApprovals) as ApiResponse<T>;
  }

  const approvalDecideMatch = path.match(/\/api\/v1\/approvals\/(.+)\/decide/);
  if (approvalDecideMatch && method === "POST") {
    return envelope({ approval_id: approvalDecideMatch[1], status: "decided" }) as ApiResponse<T>;
  }

  // Queue
  if (path === "/api/v1/queue" && method === "GET") {
    return envelope(mockQueue) as ApiResponse<T>;
  }

  // Memory
  if (path === "/api/v1/memory/facts" && method === "GET") {
    return envelope(mockFacts) as ApiResponse<T>;
  }

  const factActionMatch = path.match(/\/api\/v1\/memory\/facts\/(.+)\/(approve|update)/);
  if (factActionMatch && method === "POST") {
    return envelope({ id: factActionMatch[1], status: "updated" }) as ApiResponse<T>;
  }

  const factDeleteMatch = path.match(/\/api\/v1\/memory\/facts\/(.+)/);
  if (factDeleteMatch && method === "DELETE") {
    return envelope({ id: factDeleteMatch[1], status: "deleted" }) as ApiResponse<T>;
  }

  // Artifacts
  if (path === "/api/v1/artifacts" && method === "GET") {
    return envelope(mockArtifacts) as ApiResponse<T>;
  }

  // Cost
  if (path === "/api/v1/cost/records" && method === "GET") {
    return envelope(mockCostRecords) as ApiResponse<T>;
  }

  if (path === "/api/v1/cost/summary" && method === "GET") {
    return envelope(mockCostSummary) as ApiResponse<T>;
  }

  // Usage (§24)
  if (path === "/api/v1/usage" && method === "GET") {
    return envelope({
      daily: { used: 12500, limit: 100000, cost_usd: 0.06 },
      monthly: { used: 245000, limit: 2000000, cost_usd: 1.23 },
    }) as ApiResponse<T>;
  }

  // Settings
  if (path === "/api/v1/settings" && method === "GET") {
    return envelope({
      default_model: "claude-3.5-sonnet",
      default_privacy_mode: "private",
      budget_daily_usd: 5.0,
      budget_monthly_usd: 50.0,
    }) as ApiResponse<T>;
  }

  if (path === "/api/v1/settings" && (method === "PUT" || method === "POST")) {
    return envelope({ status: "saved" }) as ApiResponse<T>;
  }

  // Fallback
  return errorEnvelope("NOT_FOUND", `Mock handler not found for ${method} ${path}`) as ApiResponse<T>;
}
