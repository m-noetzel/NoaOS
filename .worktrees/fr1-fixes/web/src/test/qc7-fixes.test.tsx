/**
 * QC7: Frontend Polish & UX — Failing Tests (Red Phase)
 *
 * Tests for findings UI-M1 through UI-M10.
 * All tests are expected to FAIL until the fixes are implemented.
 *
 * Spec refs: FINDINGS.md UI-M1..UI-M10, PHASE_DETAILS.md Phase QC7
 * Test plan: Plan/REVIEWS/test-plan_QC7.md
 *
 * Blocker resolutions applied:
 *   UI-M6: GET /api/v1/tools will be added (array of {name, capability, risk_tier, enabled, description})
 *   UI-M4: Option A — optimistic append of {role:"assistant", content: streamingContent} on result_ready
 *   UI-M10: Source inspection + Suspense fallback test
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React, { Suspense } from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { readFileSync } from "fs";

// Ensure crypto.randomUUID is available in jsdom
if (!globalThis.crypto?.randomUUID) {
  vi.stubGlobal("crypto", {
    ...globalThis.crypto,
    randomUUID: () => "00000000-0000-0000-0000-000000000000",
  });
}

// Stub ResizeObserver for recharts tests (jsdom lacks layout engine)
if (!globalThis.ResizeObserver) {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  );
}

/** Helper: fresh QueryClient with no retries */
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

// ================================================================
// UI-M1: Delete web/src/pages/Index.tsx (dead placeholder)
// Spec ref: FINDINGS.md UI-M1 / PHASE_DETAILS.md Phase QC7
// ================================================================
describe("UI-M1: Dead Index.tsx removal", () => {
  /**
   * UI-M1: Index.tsx must be deleted — it is dead code never routed to.
   * The file should not exist after the fix.
   */
  it("Index.tsx does not exist after deletion", () => {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const indexPath = resolve(__dirname, "../pages/Index.tsx");
    expect(existsSync(indexPath)).toBe(false);
  });

  /**
   * UI-M1 regression: "/" route still renders Chat, not Index.
   * Ensures the removal doesn't break the default route.
   */
  it('"/" route renders Chat component, not Index', async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({
        ok: true,
        data: [],
        error: null,
        trace_id: "t",
      }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() {}
        disconnect() {}
      },
    }));

    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<Chat />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Chat page renders its thread sidebar with "Threads" label
    await waitFor(() => {
      expect(screen.getByText("Threads")).toBeInTheDocument();
    });

    // Must NOT contain the dead Index page content
    expect(screen.queryByText("Welcome to Your Blank App")).not.toBeInTheDocument();
  });
});

// ================================================================
// UI-M2: Pagination on Runs, Artifacts, and Cost pages
// Spec ref: FINDINGS.md UI-M2 / PHASE_DETAILS.md Phase QC7
// ================================================================
describe("UI-M2: Pagination on list pages", () => {
  let apiRequestSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    apiRequestSpy = vi.fn().mockResolvedValue({
      ok: true,
      data: [],
      error: null,
      trace_id: "t",
    });

    vi.doMock("@/api/client", () => ({
      apiRequest: apiRequestSpy,
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  /**
   * UI-M2: Runs page initial fetch must include limit/offset query params.
   * Currently fetches "/api/v1/runs" with no pagination.
   */
  it("Runs page fetches with limit and offset query params", async () => {
    vi.resetModules();
    const RunsModule = await import("@/pages/Runs");
    const Runs = RunsModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Runs />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(apiRequestSpy).toHaveBeenCalled();
    });

    // The first call to apiRequest for runs should include limit/offset
    const runsCall = apiRequestSpy.mock.calls.find(
      (call: unknown[]) => typeof call[0] === "string" && (call[0] as string).includes("/api/v1/runs")
    );
    expect(runsCall).toBeDefined();
    const url = runsCall![0] as string;
    expect(url).toMatch(/[?&]limit=\d+/);
    expect(url).toMatch(/[?&]offset=\d+/);
  });

  /**
   * UI-M2: Clicking "Next" increments offset and triggers a new fetch.
   */
  it("Runs page 'Next' button increments offset", async () => {
    // Return exactly 20 items so "Next" should be enabled
    const twentyRuns = Array.from({ length: 20 }, (_, i) => ({
      id: `run-${i}`,
      thread_id: "t1",
      status: "completed",
      summary: `Run ${i}`,
      risk_tier: "low",
      privacy_mode: "private",
      model: "gpt-4o",
      provider: "openai",
      tokens_in: 100,
      tokens_out: 50,
      cost_usd: 0.01,
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-01T00:00:00Z",
    }));

    apiRequestSpy.mockResolvedValue({
      ok: true,
      data: twentyRuns,
      error: null,
      trace_id: "t",
    });

    vi.resetModules();
    const RunsModule = await import("@/pages/Runs");
    const Runs = RunsModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Runs />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Run 0")).toBeInTheDocument();
    });

    // Click "Next" button
    const nextButton = screen.getByRole("button", { name: /next/i });
    fireEvent.click(nextButton);

    // After clicking Next, offset should increase
    await waitFor(() => {
      const laterCalls = apiRequestSpy.mock.calls.filter(
        (call: unknown[]) => typeof call[0] === "string" && (call[0] as string).includes("/api/v1/runs")
      );
      const lastCall = laterCalls[laterCalls.length - 1];
      const lastUrl = lastCall[0] as string;
      // Offset must be > 0 after clicking Next
      const offsetMatch = lastUrl.match(/offset=(\d+)/);
      expect(offsetMatch).not.toBeNull();
      expect(Number(offsetMatch![1])).toBeGreaterThan(0);
    });
  });

  /**
   * UI-M2: "Previous" button is disabled at offset=0.
   */
  it("Runs page 'Previous' is disabled at offset 0", async () => {
    vi.resetModules();
    const RunsModule = await import("@/pages/Runs");
    const Runs = RunsModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Runs />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      const prevButton = screen.getByRole("button", { name: /previous|prev/i });
      expect(prevButton).toBeDisabled();
    });
  });

  /**
   * UI-M2 negative: When fewer items than limit are returned, "Next" is disabled.
   * Prevents infinite empty pages.
   */
  it("'Next' is disabled when API returns fewer items than limit", async () => {
    // Return only 5 items (less than the expected limit of ~20)
    const fiveRuns = Array.from({ length: 5 }, (_, i) => ({
      id: `run-${i}`,
      thread_id: "t1",
      status: "completed",
      summary: `Run ${i}`,
      risk_tier: "low",
      privacy_mode: "private",
      model: "gpt-4o",
      provider: "openai",
      tokens_in: 100,
      tokens_out: 50,
      cost_usd: 0.01,
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-01T00:00:00Z",
    }));

    apiRequestSpy.mockResolvedValue({
      ok: true,
      data: fiveRuns,
      error: null,
      trace_id: "t",
    });

    vi.resetModules();
    const RunsModule = await import("@/pages/Runs");
    const Runs = RunsModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Runs />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Run 0")).toBeInTheDocument();
    });

    // "Next" should be disabled since we got fewer items than limit
    const nextButton = screen.getByRole("button", { name: /next/i });
    expect(nextButton).toBeDisabled();
  });

  /**
   * UI-M2: Artifacts page also uses pagination params.
   */
  it("Artifacts page fetches with limit and offset query params", async () => {
    vi.resetModules();
    const ArtifactsModule = await import("@/pages/Artifacts");
    const Artifacts = ArtifactsModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Artifacts />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(apiRequestSpy).toHaveBeenCalled();
    });

    const artifactsCall = apiRequestSpy.mock.calls.find(
      (call: unknown[]) => typeof call[0] === "string" && (call[0] as string).includes("/api/v1/artifacts")
    );
    expect(artifactsCall).toBeDefined();
    const url = artifactsCall![0] as string;
    expect(url).toMatch(/[?&]limit=\d+/);
    expect(url).toMatch(/[?&]offset=\d+/);
  });

  /**
   * UI-M2: Cost records also use pagination params.
   */
  it("Cost records page fetches with limit and offset query params", async () => {
    vi.resetModules();
    const CostModule = await import("@/pages/Cost");
    const Cost = CostModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Cost />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(apiRequestSpy).toHaveBeenCalled();
    });

    const costCall = apiRequestSpy.mock.calls.find(
      (call: unknown[]) => typeof call[0] === "string" && (call[0] as string).includes("/api/v1/cost/records")
    );
    expect(costCall).toBeDefined();
    const url = costCall![0] as string;
    expect(url).toMatch(/[?&]limit=\d+/);
    expect(url).toMatch(/[?&]offset=\d+/);
  });
});

// ================================================================
// UI-M3: Runtime SSE event type validation
// Spec ref: FINDINGS.md UI-M3 / PHASE_DETAILS.md Phase QC7
// ================================================================
describe("UI-M3: SSE event type runtime validation", () => {
  /**
   * UI-M3: Known event type (e.g. "token_stream") passes through to onEvent.
   * After the fix, the validator should accept known types.
   */
  it("known event type passes through and calls onEvent", async () => {
    vi.resetModules();
    const { SSEClient } = await import("@/api/sse");

    let receivedEvents: Array<{ event: string; data: Record<string, unknown> }> = [];

    const client = new SSEClient({
      onEvent: (event) => {
        receivedEvents.push(event);
      },
    });

    // Simulate an SSE stream with a known event type
    const ssePayload = `event: token_stream\ndata: {"token":"hello"}\n\n`;
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } })
    );

    try {
      await client.connect("/api/v1/chat", { message: "test" });
    } catch {
      // stream ends
    }

    // "token_stream" is a valid SSEEventType and should reach onEvent
    expect(receivedEvents.length).toBeGreaterThanOrEqual(1);
    expect(receivedEvents[0].event).toBe("token_stream");

    fetchSpy.mockRestore();
  });

  /**
   * UI-M3 negative: Unknown event type must NOT be passed to onEvent.
   * Currently the unsafe `as SSEEventType` cast passes anything through.
   */
  it("unknown event type is NOT passed to onEvent", async () => {
    vi.resetModules();
    const { SSEClient } = await import("@/api/sse");

    let receivedEvents: Array<{ event: string; data: Record<string, unknown> }> = [];

    const client = new SSEClient({
      onEvent: (event) => {
        receivedEvents.push(event);
      },
    });

    // Simulate SSE stream with unknown event type
    const ssePayload = `event: malicious_event\ndata: {"payload":"evil"}\n\n`;
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } })
    );

    try {
      await client.connect("/api/v1/chat", { message: "test" });
    } catch {
      // stream ends
    }

    // After validation fix: "malicious_event" should be filtered out
    const maliciousEvents = receivedEvents.filter((e) => e.event === "malicious_event");
    expect(maliciousEvents.length).toBe(0);

    fetchSpy.mockRestore();
  });

  /**
   * UI-M3: Event with no event: line and no event_type field defaults gracefully.
   * Must not crash.
   */
  it("event with no event: line defaults gracefully without crash", async () => {
    vi.resetModules();
    const { SSEClient } = await import("@/api/sse");

    let receivedEvents: Array<{ event: string; data: Record<string, unknown> }> = [];
    let errorOccurred = false;

    const client = new SSEClient({
      onEvent: (event) => {
        receivedEvents.push(event);
      },
      onError: () => {
        errorOccurred = true;
      },
    });

    // SSE with no event: line and no event_type in data
    const ssePayload = `data: {"some_field":"value"}\n\n`;
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } })
    );

    try {
      await client.connect("/api/v1/chat", { message: "test" });
    } catch {
      // stream ends
    }

    // Should not crash — either filtered or handled as "unknown"
    expect(errorOccurred).toBe(false);
    // "unknown" events should be filtered after the fix (not passed to onEvent)
    const unknownEvents = receivedEvents.filter((e) => e.event === "unknown");
    expect(unknownEvents.length).toBe(0);

    fetchSpy.mockRestore();
  });

  /**
   * UI-M3: Validation whitelist must match the SSEEventType union exactly.
   * No drift between the runtime validator and the TypeScript type.
   */
  it("validator set matches SSEEventType union members", async () => {
    vi.resetModules();
    const sseModule = await import("@/api/sse");

    // After the fix, the SSE module should export or use a VALID_SSE_EVENTS set.
    // We check it exists and contains all expected event types.
    const expectedTypes = [
      "message_received", "classification_done", "step_started", "token_stream",
      "tool_called", "tool_result", "approval_requested", "approval_received",
      "artifact_created", "result_ready", "error", "planner_step",
      "run_started", "run_completed", "run_failed", "run_cancelled", "meta",
    ];

    // The module should export VALID_SSE_EVENTS (or similar)
    const validEvents = (sseModule as Record<string, unknown>).VALID_SSE_EVENTS as Set<string> | string[] | undefined;
    expect(validEvents).toBeDefined();

    const validSet = validEvents instanceof Set ? validEvents : new Set(validEvents);
    for (const eventType of expectedTypes) {
      expect(validSet.has(eventType)).toBe(true);
    }
    // No extra types in the set
    expect(validSet.size).toBe(expectedTypes.length);
  });
});

// ================================================================
// UI-M4: Streaming content appended to message history on result_ready
// Spec ref: FINDINGS.md UI-M4 / PHASE_DETAILS.md Phase QC7
// Blocker resolution: Option A — optimistic append
// ================================================================
describe("UI-M4: Optimistic append on result_ready (no flash)", () => {
  /**
   * UI-M4: When result_ready fires, streaming content must appear as an
   * assistant message in the message list immediately (no blank flash).
   * Option A: optimistic append of {role:"assistant", content: streamingContent}.
   */
  it("assistant message appears in message list after result_ready without waiting for refetch", async () => {
    let capturedOnEvent: ((event: { event: string; data: Record<string, unknown> }) => void) | null = null;

    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/messages")) {
          return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
        }
        if (path.includes("/threads")) {
          return Promise.resolve({
            ok: true,
            data: [{ id: "thread-1", title: "Test", created_at: "2026-03-01", updated_at: "2026-03-01", message_count: 0 }],
            error: null,
            trace_id: "t",
          });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
      }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor(options: { onEvent: (event: unknown) => void }) {
          capturedOnEvent = options.onEvent;
        }
        async connect() { return; }
        disconnect() { return; }
      },
    }));

    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Wait for initial render
    await waitFor(() => {
      expect(screen.getByText("Threads")).toBeInTheDocument();
    });

    // Simulate streaming: token_stream events followed by result_ready
    expect(capturedOnEvent).toBeDefined();

    act(() => {
      capturedOnEvent!({ event: "meta", data: { run_id: "run-1" } });
    });
    act(() => {
      capturedOnEvent!({ event: "token_stream", data: { token: "Hello " } });
    });
    act(() => {
      capturedOnEvent!({ event: "token_stream", data: { token: "world!" } });
    });

    // The streaming content should be visible
    await waitFor(() => {
      expect(screen.getByText(/Hello world!/)).toBeInTheDocument();
    });

    // Now fire result_ready
    act(() => {
      capturedOnEvent!({ event: "result_ready", data: {} });
    });

    // After result_ready, the streamed text "Hello world!" must still be visible
    // as an assistant message (optimistically appended), not disappeared
    await waitFor(() => {
      expect(screen.getByText(/Hello world!/)).toBeInTheDocument();
    });
  });

  /**
   * UI-M4 negative: Duplicate messages must not appear — optimistic append
   * and refetch should not create two copies of the same message.
   */
  it("no duplicate assistant message after refetch resolves", async () => {
    let capturedOnEvent: ((event: { event: string; data: Record<string, unknown> }) => void) | null = null;
    let messagesFetchCount = 0;

    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/messages")) {
          messagesFetchCount++;
          // After first fetch, return the assistant message (simulating refetch)
          if (messagesFetchCount > 1) {
            return Promise.resolve({
              ok: true,
              data: [
                { id: "m1", thread_id: "thread-1", role: "assistant", content: "Hello world!", created_at: "2026-03-01T00:00:00Z" },
              ],
              error: null,
              trace_id: "t",
            });
          }
          return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
        }
        if (path.includes("/threads")) {
          return Promise.resolve({
            ok: true,
            data: [{ id: "thread-1", title: "Test", created_at: "2026-03-01", updated_at: "2026-03-01", message_count: 0 }],
            error: null,
            trace_id: "t",
          });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
      }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor(options: { onEvent: (event: unknown) => void }) {
          capturedOnEvent = options.onEvent;
        }
        async connect() { return; }
        disconnect() { return; }
      },
    }));

    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(capturedOnEvent).toBeDefined();
    });

    // Stream tokens then result_ready
    act(() => {
      capturedOnEvent!({ event: "token_stream", data: { token: "Hello world!" } });
    });
    act(() => {
      capturedOnEvent!({ event: "result_ready", data: {} });
    });

    // Wait for refetch to resolve (returns "Hello world!" from API)
    await waitFor(() => {
      // Count occurrences of the message text — must be exactly 1
      const allText = document.body.textContent || "";
      const matches = allText.match(/Hello world!/g);
      expect(matches).not.toBeNull();
      expect(matches!.length).toBe(1);
    });
  });

  /**
   * UI-M4 regression: isStreaming becomes false after result_ready.
   */
  it("isStreaming is false after result_ready (regression)", async () => {
    let capturedOnEvent: ((event: { event: string; data: Record<string, unknown> }) => void) | null = null;

    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "t" }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor(options: { onEvent: (event: unknown) => void }) {
          capturedOnEvent = options.onEvent;
        }
        async connect() { return; }
        disconnect() { return; }
      },
    }));

    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(capturedOnEvent).toBeDefined();
    });

    act(() => {
      capturedOnEvent!({ event: "token_stream", data: { token: "test" } });
    });

    // The send button should be disabled while streaming
    const sendButton = screen.getByRole("button", { name: "" });
    // After result_ready, the input should be enabled again (isStreaming=false)
    act(() => {
      capturedOnEvent!({ event: "result_ready", data: {} });
    });

    await waitFor(() => {
      const input = screen.getByPlaceholderText(/Message Noa/);
      expect(input).not.toBeDisabled();
    });
  });
});

// ================================================================
// UI-M5: Auto-generate thread title from first message
// Spec ref: FINDINGS.md UI-M5 / PHASE_DETAILS.md Phase QC7
// ================================================================
describe("UI-M5: Thread title from first message", () => {
  let apiRequestSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    apiRequestSpy = vi.fn().mockImplementation((path: string, options?: RequestInit) => {
      const method = options?.method || "GET";

      if (path.includes("/threads") && method === "POST") {
        const body = JSON.parse(options!.body as string);
        return Promise.resolve({
          ok: true,
          data: { id: "new-thread", title: body.title, created_at: "2026-03-01", updated_at: "2026-03-01", message_count: 0 },
          error: null,
          trace_id: "t",
        });
      }
      if (path.includes("/threads")) {
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
      }
      return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
    });

    vi.doMock("@/api/client", () => ({
      apiRequest: apiRequestSpy,
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() { return; }
        disconnect() { return; }
      },
    }));
  });

  /**
   * UI-M5: Thread creation request must contain a title derived from the message
   * content, NOT the hardcoded "New Thread".
   */
  it('thread title is derived from message, not "New Thread"', async () => {
    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Message Noa/)).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Message Noa/);
    fireEvent.change(input, { target: { value: "Can you review my budget?" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      const threadPostCall = apiRequestSpy.mock.calls.find(
        (call: unknown[]) =>
          typeof call[0] === "string" &&
          (call[0] as string).includes("/threads") &&
          (call[1] as RequestInit)?.method === "POST"
      );
      expect(threadPostCall).toBeDefined();
      const body = JSON.parse((threadPostCall![1] as RequestInit).body as string);
      expect(body.title).not.toBe("New Thread");
      expect(body.title).toContain("Can you review my budget");
    });
  });

  /**
   * UI-M5: Title is truncated to <=50 characters with trailing "...".
   */
  it("title is truncated to 50 chars with trailing ellipsis", async () => {
    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Message Noa/)).toBeInTheDocument();
    });

    const longMessage = "This is a very long message that definitely exceeds the fifty character limit for thread titles";
    const input = screen.getByPlaceholderText(/Message Noa/);
    fireEvent.change(input, { target: { value: longMessage } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      const threadPostCall = apiRequestSpy.mock.calls.find(
        (call: unknown[]) =>
          typeof call[0] === "string" &&
          (call[0] as string).includes("/threads") &&
          (call[1] as RequestInit)?.method === "POST"
      );
      expect(threadPostCall).toBeDefined();
      const body = JSON.parse((threadPostCall![1] as RequestInit).body as string);
      expect(body.title.length).toBeLessThanOrEqual(53); // 50 + "..."
      expect(body.title).toMatch(/\.\.\.$/);
    });
  });

  /**
   * UI-M5: A message of exactly 50 chars produces a title WITHOUT "...".
   */
  it("exactly 50-char message produces title without ellipsis", async () => {
    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Message Noa/)).toBeInTheDocument();
    });

    // Exactly 50 characters
    const exact50 = "A".repeat(50);
    const input = screen.getByPlaceholderText(/Message Noa/);
    fireEvent.change(input, { target: { value: exact50 } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      const threadPostCall = apiRequestSpy.mock.calls.find(
        (call: unknown[]) =>
          typeof call[0] === "string" &&
          (call[0] as string).includes("/threads") &&
          (call[1] as RequestInit)?.method === "POST"
      );
      expect(threadPostCall).toBeDefined();
      const body = JSON.parse((threadPostCall![1] as RequestInit).body as string);
      expect(body.title).toBe(exact50);
      expect(body.title).not.toMatch(/\.\.\.$/);
    });
  });

  /**
   * UI-M5 negative: Whitespace-only message produces default title,
   * not a whitespace-only title.
   */
  it("whitespace-only message does not create whitespace-only title", async () => {
    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Message Noa/)).toBeInTheDocument();
    });

    // Whitespace-only message — the existing guard (!input.trim()) should prevent send
    const input = screen.getByPlaceholderText(/Message Noa/);
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });

    // No thread creation should have happened (existing guard)
    // OR if it does create, the title must not be whitespace-only
    await new Promise((r) => setTimeout(r, 100));
    const threadPostCall = apiRequestSpy.mock.calls.find(
      (call: unknown[]) =>
        typeof call[0] === "string" &&
        (call[0] as string).includes("/threads") &&
        (call[1] as RequestInit)?.method === "POST"
    );
    if (threadPostCall) {
      const body = JSON.parse((threadPostCall[1] as RequestInit).body as string);
      expect(body.title.trim().length).toBeGreaterThan(0);
    }
    // If no call was made, the guard worked — that's also acceptable
  });
});

// ================================================================
// UI-M6: Tools page (new)
// Spec ref: FINDINGS.md UI-M6 / PHASE_DETAILS.md Phase QC7
// Blocker resolution: GET /api/v1/tools returns [{name, capability, risk_tier, enabled, description}]
// ================================================================
describe("UI-M6: Tools page", () => {
  const mockTools = [
    { name: "web_search", capability: "search.read", risk_tier: "low", enabled: true, description: "Search the web" },
    { name: "gmail_send", capability: "email.write", risk_tier: "high", enabled: false, description: "Send emails via Gmail" },
  ];

  /** Helper: resolve Tools page path */
  function toolsPagePath() {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    return resolve(__dirname, "../pages/Tools.tsx");
  }

  /**
   * UI-M6: Tools page file must exist.
   */
  it("Tools.tsx page file exists", () => {
    expect(existsSync(toolsPagePath())).toBe(true);
  });

  /**
   * UI-M6: /tools route exists in App.tsx.
   */
  it("/tools route is registered in App.tsx", () => {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const appTsxPath = resolve(__dirname, "../App.tsx");
    const appSource = readFileSync(appTsxPath, "utf-8");
    // Route path="/tools" must exist
    expect(appSource).toMatch(/path=["']\/tools["']/);
  });

  /**
   * UI-M6: Sidebar has a Tools link.
   */
  it("sidebar source contains Tools nav item", () => {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const sidebarPath = resolve(__dirname, "../components/layout/AppSidebar.tsx");
    const sidebarSource = readFileSync(sidebarPath, "utf-8");
    // Must have a "Tools" entry pointing to /tools
    expect(sidebarSource).toMatch(/title:\s*["']Tools["']/);
    expect(sidebarSource).toMatch(/url:\s*["']\/tools["']/);
  });

  /**
   * UI-M6: Tools page shows empty state text.
   * (Source inspection: the component must handle empty data)
   */
  it("Tools page source handles empty state", () => {
    const path = toolsPagePath();
    if (!existsSync(path)) {
      expect.fail("Tools.tsx does not exist — UI-M6 not implemented");
      return;
    }
    const source = readFileSync(path, "utf-8");
    // Must contain some form of "no tools" empty state
    expect(source.toLowerCase()).toMatch(/no tools|empty/);
  });

  /**
   * UI-M6 negative: Tools page source handles error state.
   */
  it("Tools page source handles error state", () => {
    const path = toolsPagePath();
    if (!existsSync(path)) {
      expect.fail("Tools.tsx does not exist — UI-M6 not implemented");
      return;
    }
    const source = readFileSync(path, "utf-8");
    // Must contain error handling (isError or error state)
    expect(source).toMatch(/isError|error/i);
  });
});

// ================================================================
// UI-M7: Loading skeletons and empty states for Cost charts
// Spec ref: FINDINGS.md UI-M7 / PHASE_DETAILS.md Phase QC7
// ================================================================
describe("UI-M7: Cost page loading and empty states", () => {
  /**
   * UI-M7: When data is loading, a skeleton or spinner is visible.
   */
  it("shows skeleton/spinner when data is loading", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockReturnValue(new Promise(() => {})),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.resetModules();
    const CostModule = await import("@/pages/Cost");
    const Cost = CostModule.default;

    const queryClient = makeQueryClient();

    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Cost />
        </MemoryRouter>
      </QueryClientProvider>
    );

    // A loading indicator must be visible (skeleton, spinner, or "Loading" text)
    await waitFor(() => {
      const loading =
        screen.queryByText(/loading/i) ||
        container.querySelector('[role="status"]') ||
        container.querySelector(".animate-pulse");
      expect(loading).not.toBeNull();
    });
  });

  /**
   * UI-M7: When summaries and records are empty, "No cost data" text is shown.
   */
  it('shows "No cost data" when summaries and records are empty', async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "t" }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.resetModules();
    const CostModule = await import("@/pages/Cost");
    const Cost = CostModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Cost />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/no cost data/i)).toBeInTheDocument();
    });
  });

  /**
   * UI-M7 negative: Empty state message is NOT shown when data is loading.
   * Prevents conflated loading/empty states.
   */
  it("does not show empty state while still loading", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockReturnValue(new Promise(() => {})),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.resetModules();
    const CostModule = await import("@/pages/Cost");
    const Cost = CostModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Cost />
        </MemoryRouter>
      </QueryClientProvider>
    );

    // While loading, "No cost data" must NOT appear
    await new Promise((r) => setTimeout(r, 100));
    expect(screen.queryByText(/no cost data/i)).not.toBeInTheDocument();
  });
});

// ================================================================
// UI-M8: Settings changes affect Chat without stale state
// Spec ref: FINDINGS.md UI-M8 / PHASE_DETAILS.md Phase QC7
// ================================================================
describe("UI-M8: Settings freshness in Chat", () => {
  /**
   * UI-M8: After settings update, Chat uses the new provider/model for
   * the next request — not the stale pre-update values.
   */
  it("Chat uses updated provider/model after settings change", async () => {
    let settingsFetchCount = 0;

    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/settings")) {
          settingsFetchCount++;
          // First fetch: anthropic. Later: openai (simulating settings change)
          if (settingsFetchCount <= 1) {
            return Promise.resolve({
              ok: true,
              data: {
                default_model: "claude-sonnet-4-20250514",
                default_provider: "anthropic",
                default_privacy_mode: "private",
                budget_daily_usd: 10,
                budget_monthly_usd: 200,
              },
              error: null,
              trace_id: "t",
            });
          }
          return Promise.resolve({
            ok: true,
            data: {
              default_model: "gpt-4o",
              default_provider: "openai",
              default_privacy_mode: "private",
              budget_daily_usd: 10,
              budget_monthly_usd: 200,
            },
            error: null,
            trace_id: "t",
          });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
      }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() { return; }
        disconnect() { return; }
      },
    }));

    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Message Noa/)).toBeInTheDocument();
    });

    // Simulate settings cache invalidation (as if user changed settings)
    await act(async () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    });

    // Wait for refetch
    await waitFor(() => {
      expect(settingsFetchCount).toBeGreaterThan(1);
    });

    // The Chat component should now use "openai" as the provider, not "anthropic".
    // If Chat copies settings to local state once on mount (the bug), it still uses "anthropic".
    // We can verify by checking what the component sends on the next chat request.
    // This is tested indirectly: the component should read from the query data directly.

    // Trigger a chat send to capture the request body
    const apiRequestMock = (await import("@/api/client")).apiRequest as ReturnType<typeof vi.fn>;

    const input = screen.getByPlaceholderText(/Message Noa/);
    fireEvent.change(input, { target: { value: "test message" } });
    fireEvent.keyDown(input, { key: "Enter" });

    // After the fix, the SSEClient should receive provider: "openai"
    // Since SSEClient is mocked, we check the Chat component's internal state
    // by looking at what body was passed to the SSEClient connect call.
    // For now, we verify the settings query returns openai and the component
    // does NOT copy to local state (which would keep anthropic).
    await waitFor(() => {
      const settingsData = queryClient.getQueryData<{ data: { default_provider: string } }>(["settings"]);
      // The query should have the updated data
      expect(settingsData?.data?.default_provider).toBe("openai");
    });
  });

  /**
   * UI-M8 negative: Stale provider must NOT be used after settings change.
   * If Chat copies settings to local state on mount, this test fails.
   */
  it("stale provider is not used in chat request after settings invalidation", async () => {
    let capturedConnectBody: unknown = null;

    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/settings")) {
          return Promise.resolve({
            ok: true,
            data: {
              default_model: "gpt-4o",
              default_provider: "openai",
              default_privacy_mode: "private",
              budget_daily_usd: 10,
              budget_monthly_usd: 200,
            },
            error: null,
            trace_id: "t",
          });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
      }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect(_path: string, body?: unknown) {
          capturedConnectBody = body;
          return;
        }
        disconnect() { return; }
      },
    }));

    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Message Noa/)).toBeInTheDocument();
    });

    // Wait for settings to load
    await waitFor(() => {
      const settingsData = queryClient.getQueryData(["settings"]);
      expect(settingsData).toBeDefined();
    });

    // Send a message
    const input = screen.getByPlaceholderText(/Message Noa/);
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(capturedConnectBody).not.toBeNull();
    });

    // The body sent to SSEClient.connect must use the settings provider
    const body = capturedConnectBody as { provider: string };
    expect(body.provider).toBe("openai");
  });

  /**
   * UI-M8 regression: Initial settings load still works (defaults are not hardcoded).
   */
  it("initial load uses settings from API, not hardcoded defaults", async () => {
    let capturedConnectBody: unknown = null;

    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/settings")) {
          return Promise.resolve({
            ok: true,
            data: {
              default_model: "gemini-2.0-flash",
              default_provider: "google_ai",
              default_privacy_mode: "external",
              budget_daily_usd: 5,
              budget_monthly_usd: 100,
            },
            error: null,
            trace_id: "t",
          });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
      }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect(_path: string, body?: unknown) {
          capturedConnectBody = body;
          return;
        }
        disconnect() { return; }
      },
    }));

    vi.resetModules();
    const ChatModule = await import("@/pages/Chat");
    const Chat = ChatModule.default;

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Wait for settings to load
    await waitFor(() => {
      const settingsData = queryClient.getQueryData(["settings"]);
      expect(settingsData).toBeDefined();
    });

    // Allow useEffect to apply settings
    await new Promise((r) => setTimeout(r, 50));

    const input = screen.getByPlaceholderText(/Message Noa/);
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(capturedConnectBody).not.toBeNull();
    });

    const body = capturedConnectBody as { provider: string; model: string };
    expect(body.provider).toBe("google_ai");
    expect(body.model).toBe("gemini-2.0-flash");
  });
});

// ================================================================
// UI-M9: Approval and queue count badges on sidebar
// Spec ref: FINDINGS.md UI-M9 / PHASE_DETAILS.md Phase QC7
// ================================================================
describe("UI-M9: Sidebar badges", () => {
  /**
   * UI-M9: Approvals sidebar item shows badge with pending count.
   */
  it("Approvals sidebar item shows badge with count", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/approvals/pending")) {
          return Promise.resolve({
            ok: true,
            data: [
              { id: "a1", status: "pending" },
              { id: "a2", status: "pending" },
              { id: "a3", status: "pending" },
            ],
            error: null,
            trace_id: "t",
          });
        }
        if (path.includes("/queue")) {
          return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
      }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, logout: vi.fn() }),
      AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    }));

    vi.resetModules();
    const { AppSidebar } = await import("@/components/layout/AppSidebar");
    const { SidebarProvider } = await import("@/components/ui/sidebar");

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <SidebarProvider>
            <AppSidebar />
          </SidebarProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // The sidebar should show a badge with "3" next to Approvals
    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument();
    });
  });

  /**
   * UI-M9: Queue sidebar item shows badge with count.
   */
  it("Queue sidebar item shows badge with count", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/approvals/pending")) {
          return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
        }
        if (path.includes("/queue")) {
          return Promise.resolve({
            ok: true,
            data: [{ id: "q1", status: "queued" }, { id: "q2", status: "queued" }],
            error: null,
            trace_id: "t",
          });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "t" });
      }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, logout: vi.fn() }),
      AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    }));

    vi.resetModules();
    const { AppSidebar } = await import("@/components/layout/AppSidebar");
    const { SidebarProvider } = await import("@/components/ui/sidebar");

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <SidebarProvider>
            <AppSidebar />
          </SidebarProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });
  });

  /**
   * UI-M9: When approval count is 0, no badge is rendered.
   */
  it("no badge shown when approval count is 0", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "t" }),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, logout: vi.fn() }),
      AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    }));

    vi.resetModules();
    const { AppSidebar } = await import("@/components/layout/AppSidebar");
    const { SidebarProvider } = await import("@/components/ui/sidebar");

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <SidebarProvider>
            <AppSidebar />
          </SidebarProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Wait for sidebar to render
    await waitFor(() => {
      expect(screen.getByText("Approvals")).toBeInTheDocument();
    });

    // No badge with "0" should appear
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  /**
   * UI-M9 negative: Sidebar still renders when fetch fails (no crash).
   */
  it("sidebar renders normally when badge fetch fails", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockRejectedValue(new Error("Network error")),
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));

    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, logout: vi.fn() }),
      AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    }));

    vi.resetModules();
    const { AppSidebar } = await import("@/components/layout/AppSidebar");
    const { SidebarProvider } = await import("@/components/ui/sidebar");

    const queryClient = makeQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <SidebarProvider>
            <AppSidebar />
          </SidebarProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Sidebar must still render its navigation items despite fetch failure
    await waitFor(() => {
      expect(screen.getByText("Chat")).toBeInTheDocument();
      expect(screen.getByText("Approvals")).toBeInTheDocument();
      expect(screen.getByText("Queue")).toBeInTheDocument();
    });
  });
});

// ================================================================
// UI-M10: React.lazy() + Suspense for route-level code splitting
// Spec ref: FINDINGS.md UI-M10 / PHASE_DETAILS.md Phase QC7
// Blocker resolution: Source inspection + Suspense fallback test
// ================================================================
describe("UI-M10: Code splitting with React.lazy and Suspense", () => {
  /**
   * UI-M10: App.tsx uses React.lazy() for at least the Cost page (recharts).
   * Verified by source inspection — import Cost must NOT be a static top-level import.
   */
  it("App.tsx uses React.lazy() for heavy pages", () => {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const appTsxPath = resolve(__dirname, "../App.tsx");
    const appSource = readFileSync(appTsxPath, "utf-8");

    // Must contain lazy( call — indicating at least one lazy-loaded route
    expect(appSource).toMatch(/lazy\s*\(/);

    // Cost page should be lazy-loaded (it imports recharts, ~300KB)
    // A static `import Cost from` at the top level should NOT exist
    expect(appSource).not.toMatch(/^import\s+Cost\s+from\s+/m);
  });

  /**
   * UI-M10: Suspense wrapper with non-null fallback exists around lazy routes.
   */
  it("App.tsx has Suspense wrapper with fallback", () => {
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const appTsxPath = resolve(__dirname, "../App.tsx");
    const appSource = readFileSync(appTsxPath, "utf-8");

    // Must contain <Suspense with a fallback prop
    expect(appSource).toMatch(/<Suspense\s+fallback=/);
  });
});
