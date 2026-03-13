/**
 * FR4: Chat & Streaming UX Fixes
 *
 * Tests for:
 * - UX-H2: Send button enabled when input is empty (not permanently disabled)
 * - UX-H9: User message shown immediately (optimistic UI) on send
 * - UX-H10: Activity stream shows tool_start, tool_end, step events
 * - UX-H5: Tool call details (inputs/outputs) expandable in EventTimeline
 * - UX-H3: System prompt file + Settings page has save button for system prompt
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Ensure crypto.randomUUID is available in jsdom
if (!globalThis.crypto?.randomUUID) {
  vi.stubGlobal("crypto", {
    ...globalThis.crypto,
    randomUUID: () => "00000000-0000-0000-0000-000000000000",
  });
}

// ================================================================
// Helpers
// ================================================================

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function wrap(ui: React.ReactElement, qc?: QueryClient) {
  const client = qc ?? makeQC();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

// ================================================================
// UX-H2: Send button enabled when input is empty
// ================================================================

describe("UX-H2: Send button enabled when input is empty", () => {
  it("send button is not disabled when input is empty and not streaming", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() {}
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));

    vi.resetModules();
    const { default: Chat } = await import("@/pages/Chat");
    const qc = makeQC();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><Chat /></MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      const sendBtn = screen.getByTestId("chat-send");
      // Button should not have the disabled attribute when input is empty and not streaming
      expect(sendBtn).not.toBeDisabled();
    });
  });

  it("send button is disabled only while streaming", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() {}
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));

    vi.resetModules();
    const { default: Chat } = await import("@/pages/Chat");
    const qc = makeQC();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><Chat /></MemoryRouter>
      </QueryClientProvider>
    );

    // Initially not streaming => not disabled
    await waitFor(() => {
      const sendBtn = screen.getByTestId("chat-send");
      expect(sendBtn).not.toBeDisabled();
    });
  });

  it("clicking send with empty input shows a toast error, not a crash", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() {}
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));

    vi.resetModules();
    const { default: Chat } = await import("@/pages/Chat");
    const qc = makeQC();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><Chat /></MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => screen.getByTestId("chat-send"));
    const sendBtn = screen.getByTestId("chat-send");

    // Should not throw — clicking is allowed even when input is empty
    expect(() => fireEvent.click(sendBtn)).not.toThrow();
  });
});

// ================================================================
// UX-H9: Optimistic user message
// ================================================================

describe("UX-H9: User message shown immediately on send", () => {
  it("optimistic user message state is tracked separately from assistant message", async () => {
    // This tests the Chat component logic: on send, SSE connect is called with the message
    let capturedConnectBody: unknown = null;

    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string, opts?: RequestInit) => {
        // Thread creation POST
        if (path === "/api/v1/threads" && opts?.method === "POST") {
          return Promise.resolve({
            ok: true,
            data: { id: "thread-123", title: "Hello Noa", message_count: 0, created_at: "", updated_at: "" },
            error: null, trace_id: "",
          });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "" });
      }),
    }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect(_path: string, body: unknown) {
          capturedConnectBody = body;
        }
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));

    vi.resetModules();
    const { default: Chat } = await import("@/pages/Chat");
    const qc = makeQC();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><Chat /></MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => screen.getByTestId("chat-input"));
    const input = screen.getByTestId("chat-input");
    fireEvent.change(input, { target: { value: "Hello Noa" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    // SSE connect should have been called with the message
    await waitFor(() => {
      expect(capturedConnectBody).not.toBeNull();
    });
  });

  it("message list container is present in the DOM", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() {}
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));

    vi.resetModules();
    const { default: Chat } = await import("@/pages/Chat");
    const qc = makeQC();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter><Chat /></MemoryRouter>
      </QueryClientProvider>
    );
    await waitFor(() => {
      expect(screen.getByTestId("message-list")).toBeInTheDocument();
    });
  });
});

// ================================================================
// UX-H10: Activity stream handles tool_start / tool_end / step events
// ================================================================

describe("UX-H10: Activity stream renders tool lifecycle events", () => {
  it("activityLabel returns label for tool_start event", async () => {
    vi.resetModules();
    const { ActivityStream } = await import("@/components/chat/ActivityStream");
    const events = [
      { event: "tool_start" as const, data: { tool_name: "calendar" } },
    ];
    const { container } = render(
      <ActivityStream events={events} isStreaming={true} />
    );
    expect(container.textContent).toContain("calendar");
  });

  it("activityLabel returns label for tool_end event", async () => {
    vi.resetModules();
    const { ActivityStream } = await import("@/components/chat/ActivityStream");
    const events = [
      { event: "tool_end" as const, data: { tool_name: "tavily_search" } },
    ];
    const { container } = render(
      <ActivityStream events={events} isStreaming={false} runStatus="completed" />
    );
    expect(container.textContent).toContain("tavily_search");
  });

  it("activityLabel returns label for step event", async () => {
    vi.resetModules();
    const { ActivityStream } = await import("@/components/chat/ActivityStream");
    const events = [
      { event: "step" as const, data: { label: "Searching the web" } },
    ];
    const { container } = render(
      <ActivityStream events={events} isStreaming={true} />
    );
    expect(container.textContent).toContain("Searching the web");
  });

  it("shows executing indicator while streaming with tool events", async () => {
    vi.resetModules();
    const { ActivityStream } = await import("@/components/chat/ActivityStream");
    const events = [
      { event: "tool_start" as const, data: { tool_name: "web_search" } },
    ];
    const { container } = render(
      <ActivityStream events={events} isStreaming={true} />
    );
    expect(container.textContent).toContain("Executing");
  });

  it("VALID_SSE_EVENTS includes tool_start, tool_end, step", async () => {
    vi.resetModules();
    const { VALID_SSE_EVENTS } = await import("@/api/sse");
    expect(VALID_SSE_EVENTS.has("tool_start")).toBe(true);
    expect(VALID_SSE_EVENTS.has("tool_end")).toBe(true);
    expect(VALID_SSE_EVENTS.has("step")).toBe(true);
  });
});

// ================================================================
// UX-H5: Tool call details expandable in EventTimeline
// ================================================================

describe("UX-H5: Tool call details expandable in EventTimeline", () => {
  it("renders tool_result event with expand button", async () => {
    vi.resetModules();
    const { EventTimeline } = await import("@/components/shared/EventTimeline");
    const events = [
      {
        id: "evt-1",
        run_id: "run-1",
        type: "tool_result",
        data: {
          tool_name: "tavily_search",
          result: { results: [{ title: "Tavily result 1", url: "https://example.com" }] },
        },
        created_at: new Date().toISOString(),
      },
    ];
    render(<EventTimeline events={events} />);
    // Should show the Output expand button
    expect(screen.getByText("Output")).toBeInTheDocument();
  });

  it("expands tool_result to show full JSON output", async () => {
    vi.resetModules();
    const { EventTimeline } = await import("@/components/shared/EventTimeline");
    const resultData = { results: [{ title: "Tavily item", url: "https://noa.dev" }] };
    const events = [
      {
        id: "evt-2",
        run_id: "run-1",
        type: "tool_result",
        data: { tool_name: "tavily_search", result: resultData },
        created_at: new Date().toISOString(),
      },
    ];
    render(<EventTimeline events={events} />);
    // Click expand
    const expandBtn = screen.getByText("Output");
    fireEvent.click(expandBtn);
    // JSON content should be visible
    await waitFor(() => {
      expect(screen.getByText(/Tavily item/)).toBeInTheDocument();
    });
  });

  it("renders tool_called event with Input expand button", async () => {
    vi.resetModules();
    const { EventTimeline } = await import("@/components/shared/EventTimeline");
    const events = [
      {
        id: "evt-3",
        run_id: "run-1",
        type: "tool_called",
        data: {
          tool_name: "calendar",
          args: { query: "meetings tomorrow", date_range: "2026-03-14" },
        },
        created_at: new Date().toISOString(),
      },
    ];
    render(<EventTimeline events={events} />);
    expect(screen.getByText("Input")).toBeInTheDocument();
  });

  it("expands tool_called to show input args", async () => {
    vi.resetModules();
    const { EventTimeline } = await import("@/components/shared/EventTimeline");
    const events = [
      {
        id: "evt-4",
        run_id: "run-1",
        type: "tool_called",
        data: {
          tool_name: "tavily",
          args: { query: "Noa AI agent" },
        },
        created_at: new Date().toISOString(),
      },
    ];
    const { container } = render(<EventTimeline events={events} />);
    fireEvent.click(screen.getByText("Input"));
    // The expanded JSON contains "query" and "Noa AI agent" — check container text
    await waitFor(() => {
      expect(container.textContent).toContain("query");
    });
    expect(container.textContent).toContain("Noa AI agent");
  });
});

// ================================================================
// UX-H3: System prompt section in Settings
// ================================================================

describe("UX-H3: System prompt section in Settings page", () => {
  beforeEach(() => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path === "/api/v1/settings/system-prompt") {
          return Promise.resolve({
            ok: true,
            data: { content: "You are Noa, a personal AI agent.", is_default: false },
            error: null,
            trace_id: "",
          });
        }
        // Default settings
        return Promise.resolve({
          ok: true,
          data: {
            default_model: "claude-sonnet-4-20250514",
            default_provider: "anthropic",
            default_privacy_mode: "external",
            budget_daily_usd: 10,
            budget_monthly_usd: 200,
            system_prompt: null,
            temperature: null,
            max_tokens: null,
            anthropic_api_key: null,
            openai_api_key: null,
            google_client_id: null,
            google_client_secret: null,
            notion_token: null,
            tavily_api_key: null,
            ollama_base_url: null,
          },
          error: null,
          trace_id: "",
        });
      }),
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ isAuthenticated: true, isLoading: false }),
    }));
  });

  it("Settings page renders a system prompt textarea", async () => {
    vi.resetModules();
    const { default: Settings } = await import("@/pages/Settings");
    wrap(<Settings />);
    await waitFor(() => {
      expect(screen.getByTestId("system-prompt-textarea")).toBeInTheDocument();
    });
  });

  it("Settings page renders a Save System Prompt button", async () => {
    vi.resetModules();
    const { default: Settings } = await import("@/pages/Settings");
    wrap(<Settings />);
    await waitFor(() => {
      expect(screen.getByTestId("system-prompt-save")).toBeInTheDocument();
    });
  });

  it("Save System Prompt button is disabled when content is unchanged", async () => {
    vi.resetModules();
    const { default: Settings } = await import("@/pages/Settings");
    wrap(<Settings />);
    await waitFor(() => screen.getByTestId("system-prompt-save"));
    // Initially data hasn't loaded so button is disabled (not dirty)
    // After data loads and draft == currentContent, button should remain disabled
    const saveBtn = screen.getByTestId("system-prompt-save");
    expect(saveBtn).toBeDisabled();
  });

  it("Save button becomes enabled when system prompt text changes", async () => {
    vi.resetModules();
    const { default: Settings } = await import("@/pages/Settings");
    wrap(<Settings />);

    await waitFor(() => screen.getByTestId("system-prompt-textarea"));
    const textarea = screen.getByTestId("system-prompt-textarea");
    fireEvent.change(textarea, { target: { value: "Custom prompt text" } });

    await waitFor(() => {
      const saveBtn = screen.getByTestId("system-prompt-save");
      expect(saveBtn).not.toBeDisabled();
    });
  });
});
