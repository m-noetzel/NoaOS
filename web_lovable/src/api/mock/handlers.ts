import type { ApiResponse } from "../types";
import {
  mockThreads, mockMessages, mockRuns, mockRunEvents,
  mockApprovals, mockQueue, mockFacts, mockArtifacts,
  mockCostRecords, mockCostSummary,
} from "./data";

function envelope<T>(data: T): ApiResponse<T> {
  return {
    data,
    meta: {
      request_id: crypto.randomUUID(),
      trace_id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
    },
    error: null,
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
      token_type: "bearer",
      expires_in: 3600,
    }) as ApiResponse<T>;
  }

  if (path === "/api/v1/auth/refresh" && method === "POST") {
    return envelope({
      access_token: "mock_access_token_refreshed_" + Date.now(),
      refresh_token: "mock_refresh_token_refreshed_" + Date.now(),
      token_type: "bearer",
      expires_in: 3600,
    }) as ApiResponse<T>;
  }

  // Threads
  if (path === "/api/v1/threads" && method === "GET") {
    return envelope(mockThreads) as ApiResponse<T>;
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

  const runMatch = path.match(/\/api\/v1\/runs\/(.+)\/events/);
  if (runMatch && method === "GET") {
    const runId = runMatch[1];
    return envelope(mockRunEvents.filter((e) => e.run_id === runId)) as ApiResponse<T>;
  }

  const runDetailMatch = path.match(/\/api\/v1\/runs\/(.+)$/);
  if (runDetailMatch && method === "GET") {
    const run = mockRuns.find((r) => r.id === runDetailMatch[1]);
    return envelope(run || null) as ApiResponse<T>;
  }

  // Approvals
  if (path === "/api/v1/approvals/pending" && method === "GET") {
    return envelope(mockApprovals.filter((a) => a.status === "pending")) as ApiResponse<T>;
  }

  if (path === "/api/v1/approvals" && method === "GET") {
    return envelope(mockApprovals) as ApiResponse<T>;
  }

  const approvalDecideMatch = path.match(/\/api\/v1\/approvals\/(.+)\/(approve|deny|decide)/);
  if (approvalDecideMatch && method === "POST") {
    return envelope({ success: true }) as ApiResponse<T>;
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

  // Queue
  if (path === "/api/v1/queue" && method === "GET") {
    return envelope(mockQueue) as ApiResponse<T>;
  }

  // Memory
  if (path === "/api/v1/memory/facts" && method === "GET") {
    return envelope(mockFacts) as ApiResponse<T>;
  }

  // Artifacts
  if (path === "/api/v1/artifacts" && method === "GET") {
    return envelope(mockArtifacts) as ApiResponse<T>;
  }

  const artifactRunMatch = path.match(/\/api\/v1\/runs\/(.+)\/artifacts/);
  if (artifactRunMatch && method === "GET") {
    const runId = artifactRunMatch[1];
    return envelope(mockArtifacts.filter((a) => a.run_id === runId)) as ApiResponse<T>;
  }

  // Cost
  if (path === "/api/v1/cost/records" && method === "GET") {
    return envelope(mockCostRecords) as ApiResponse<T>;
  }

  if (path === "/api/v1/cost/summary" && method === "GET") {
    return envelope(mockCostSummary) as ApiResponse<T>;
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

  // Fallback
  return {
    data: null as T,
    meta: {
      request_id: crypto.randomUUID(),
      trace_id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
    },
    error: { code: "NOT_FOUND", message: `Mock handler not found for ${method} ${path}` },
  };
}
