import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSSE } from "../hooks/useSSE";

// Mock EventSource since jsdom doesn't support it
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  readyState: number = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  private listeners: Record<string, ((event: MessageEvent) => void)[]> = {};

  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;

  constructor(url: string, init?: EventSourceInit) {
    this.url = url;
    this.readyState = MockEventSource.CONNECTING;
    MockEventSource.instances.push(this);

    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockEventSource.OPEN;
      if (this.onopen) {
        this.onopen(new Event("open"));
      }
    }, 0);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (!this.listeners[type]) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter((l) => l !== listener);
    }
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }

  // Test helper: simulate receiving an event
  _emit(type: string, data: unknown) {
    const event = new MessageEvent(type, {
      data: JSON.stringify(data),
    });
    if (this.listeners[type]) {
      this.listeners[type].forEach((l) => l(event));
    }
    if (type === "message" && this.onmessage) {
      this.onmessage(event);
    }
  }

  // Test helper: simulate error
  _error() {
    const event = new Event("error");
    if (this.onerror) {
      this.onerror(event);
    }
  }
}

describe("useSSE", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("connects to SSE endpoint with auth token", async () => {
    const runId = "run-123";
    const token = "test-access-token";

    const { result } = renderHook(() => useSSE(runId, token));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];
    // The URL should include the run ID and token for auth
    expect(es.url).toContain(`/api/v1/runs/${runId}/events`);
    expect(es.url).toContain(token);
  });

  it("receives and parses token_stream events", async () => {
    const { result } = renderHook(() =>
      useSSE("run-123", "test-access-token"),
    );

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es._emit("token_stream", { token: "Hello" });
    });

    expect(result.current.tokens).toContain("Hello");

    act(() => {
      es._emit("token_stream", { token: " world" });
    });

    expect(result.current.tokens).toBe("Hello world");
  });

  it("receives tool_called events", async () => {
    const { result } = renderHook(() =>
      useSSE("run-123", "test-access-token"),
    );

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es._emit("tool_called", {
        tool_name: "web_search",
        arguments: { query: "test" },
      });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]).toMatchObject({
      type: "tool_called",
      data: { tool_name: "web_search" },
    });
  });

  it("receives result_ready events", async () => {
    const { result } = renderHook(() =>
      useSSE("run-123", "test-access-token"),
    );

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es._emit("result_ready", {
        result: "The answer is 42",
        usage: { prompt_tokens: 100, completion_tokens: 50 },
      });
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.events).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: "result_ready" }),
      ]),
    );
  });

  it("handles connection errors gracefully", async () => {
    const { result } = renderHook(() =>
      useSSE("run-123", "test-access-token"),
    );

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    act(() => {
      es._error();
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.isConnected).toBe(false);
  });

  it("disconnects on cleanup", async () => {
    const { unmount } = renderHook(() =>
      useSSE("run-123", "test-access-token"),
    );

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });

    const es = MockEventSource.instances[0];

    unmount();

    expect(es.readyState).toBe(MockEventSource.CLOSED);
  });
});
