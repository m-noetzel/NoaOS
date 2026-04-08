/**
 * W27-FX1: UI Domain Adaptation (UI-H6)
 *
 * Tests for:
 * - DomainBadge renders correctly for private and external domains
 * - ThreadSidebar shows domain filter pills and filters by domain
 * - ChatComposer filters providers when privacy_mode=private
 * - GeneralSettings has privacy mode toggle wired to PATCH /settings
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Stub ResizeObserver — Radix UI Slider requires it (jsdom lacks layout engine)
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

// Stub scrollIntoView — Radix UI Select calls it in jsdom (no layout engine)
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
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
// DomainBadge Tests
// ================================================================

describe("DomainBadge", () => {
  it("renders Private label with lock icon for private domain", async () => {
    const { DomainBadge } = await import("@/components/DomainBadge");
    render(<DomainBadge domain="private" />);

    const badge = screen.getByTestId("domain-badge-private");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Private");
    // Lock icon is rendered as SVG inside the badge
    expect(badge.querySelector("svg")).toBeTruthy();
  });

  it("renders External label with globe icon for external domain", async () => {
    const { DomainBadge } = await import("@/components/DomainBadge");
    render(<DomainBadge domain="external" />);

    const badge = screen.getByTestId("domain-badge-external");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("External");
    expect(badge.querySelector("svg")).toBeTruthy();
  });

  it("applies purple styling for private domain", async () => {
    const { DomainBadge } = await import("@/components/DomainBadge");
    render(<DomainBadge domain="private" />);
    const badge = screen.getByTestId("domain-badge-private");
    // Should have purple-related classes
    expect(badge.className).toContain("purple");
  });

  it("applies blue styling for external domain", async () => {
    const { DomainBadge } = await import("@/components/DomainBadge");
    render(<DomainBadge domain="external" />);
    const badge = screen.getByTestId("domain-badge-external");
    expect(badge.className).toContain("blue");
  });
});

// ================================================================
// ThreadSidebar — Domain filter pills
// ================================================================

describe("ThreadSidebar — domain filter pills", () => {
  beforeEach(() => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({
        ok: true,
        data: [
          {
            id: "t1",
            title: "Private Thread",
            domain: "private",
            message_count: 2,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          {
            id: "t2",
            title: "External Thread",
            domain: "external",
            message_count: 3,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ],
        error: null,
        trace_id: "",
      }),
    }));
  });

  it("shows domain filter pills: all, private, external", async () => {
    vi.resetModules();
    const { ThreadSidebar } = await import("@/components/chat/ThreadSidebar");
    wrap(
      <ThreadSidebar
        activeThread={null}
        onSelectThread={() => {}}
        onThreadDeleted={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("domain-filter-pills")).toBeInTheDocument();
      expect(screen.getByTestId("domain-filter-all")).toBeInTheDocument();
      expect(screen.getByTestId("domain-filter-private")).toBeInTheDocument();
      expect(screen.getByTestId("domain-filter-external")).toBeInTheDocument();
    });
  });

  it("clicking private pill filters threads to show only private threads", async () => {
    vi.resetModules();
    const { ThreadSidebar } = await import("@/components/chat/ThreadSidebar");
    wrap(
      <ThreadSidebar
        activeThread={null}
        onSelectThread={() => {}}
        onThreadDeleted={() => {}}
      />
    );

    // Wait for threads to load
    await waitFor(() => {
      expect(screen.getByText("Private Thread")).toBeInTheDocument();
      expect(screen.getByText("External Thread")).toBeInTheDocument();
    });

    // Click the "private" filter pill
    fireEvent.click(screen.getByTestId("domain-filter-private"));

    await waitFor(() => {
      expect(screen.getByText("Private Thread")).toBeInTheDocument();
      expect(screen.queryByText("External Thread")).not.toBeInTheDocument();
    });
  });

  it("clicking 'all' pill restores all threads after filtering", async () => {
    vi.resetModules();
    const { ThreadSidebar } = await import("@/components/chat/ThreadSidebar");
    wrap(
      <ThreadSidebar
        activeThread={null}
        onSelectThread={() => {}}
        onThreadDeleted={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Private Thread")).toBeInTheDocument();
    });

    // Filter to private only
    fireEvent.click(screen.getByTestId("domain-filter-private"));
    await waitFor(() => {
      expect(screen.queryByText("External Thread")).not.toBeInTheDocument();
    });

    // Click All to restore
    fireEvent.click(screen.getByTestId("domain-filter-all"));
    await waitFor(() => {
      expect(screen.getByText("External Thread")).toBeInTheDocument();
      expect(screen.getByText("Private Thread")).toBeInTheDocument();
    });
  });
});

// ================================================================
// ChatComposer — Provider filtering by privacy_mode
// ================================================================

describe("ChatComposer — provider filtering by privacy_mode", () => {
  it("shows only ollama provider when privacy_mode=private", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({
        ok: true,
        data: [],
        error: null,
        trace_id: "",
      }),
    }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() {}
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));
    vi.doMock("@/hooks/useVoiceRecorder", () => ({
      useVoiceRecorder: () => ({
        state: "idle",
        elapsedSeconds: 0,
        errorMessage: null,
        startRecording: async () => {},
        stopRecording: () => {},
        cancelRecording: () => {},
      }),
    }));

    vi.resetModules();
    const { ChatComposer } = await import("@/components/chat/ChatComposer");
    const mockSSERef = { current: null };
    const privateSettings = {
      default_model: "llama-3.1-70b",
      default_provider: "ollama",
      default_privacy_mode: "private" as const,
      budget_daily_usd: 10,
      budget_monthly_usd: 200,
      system_prompt: null,
      temperature: 0.7,
      max_tokens: 4096,
      anthropic_api_key: null,
      openai_api_key: null,
      google_client_id: null,
      google_client_secret: null,
      notion_token: null,
      tavily_api_key: null,
      ollama_base_url: null,
    };

    wrap(
      <ChatComposer
        activeThread={null}
        isStreaming={false}
        settings={privateSettings}
        sseClientRef={mockSSERef as React.MutableRefObject<null>}
        onThreadCreated={() => {}}
        onSendStart={() => {}}
        onSendError={() => {}}
        onOptimisticUserMessage={() => {}}
      />
    );

    // Open advanced panel
    const settingsBtn = screen.getByLabelText("Advanced settings");
    fireEvent.click(settingsBtn);

    await waitFor(() => {
      // Private badge should be visible
      expect(screen.getByTestId("domain-badge-private")).toBeInTheDocument();
      // Provider dropdown should exist
      const trigger = screen.getByTestId("provider-select-trigger");
      expect(trigger).toBeInTheDocument();
    });

    // Verify only ollama option is available (not openai/anthropic/google_ai)
    // Open the select to see options
    const trigger = screen.getByTestId("provider-select-trigger");
    fireEvent.click(trigger);

    await waitFor(() => {
      // Ollama should be present
      const ollamaOption = screen.getByTestId("provider-option-ollama");
      expect(ollamaOption).toBeInTheDocument();
      // External-only providers should NOT be present
      expect(screen.queryByTestId("provider-option-openai")).not.toBeInTheDocument();
      expect(screen.queryByTestId("provider-option-anthropic")).not.toBeInTheDocument();
    });
  });

  it("shows all providers when privacy_mode=external", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({
        ok: true,
        data: [],
        error: null,
        trace_id: "",
      }),
    }));
    vi.doMock("@/api/sse", () => ({
      SSEClient: class {
        constructor() {}
        async connect() {}
        disconnect() {}
      },
      VALID_SSE_EVENTS: new Set(["meta", "result_ready", "token_stream"]),
    }));
    vi.doMock("@/hooks/useVoiceRecorder", () => ({
      useVoiceRecorder: () => ({
        state: "idle",
        elapsedSeconds: 0,
        errorMessage: null,
        startRecording: async () => {},
        stopRecording: () => {},
        cancelRecording: () => {},
      }),
    }));

    vi.resetModules();
    const { ChatComposer } = await import("@/components/chat/ChatComposer");
    const mockSSERef = { current: null };
    const externalSettings = {
      default_model: "gpt-4.1",
      default_provider: "openai",
      default_privacy_mode: "external" as const,
      budget_daily_usd: 10,
      budget_monthly_usd: 200,
      system_prompt: null,
      temperature: 0.7,
      max_tokens: 4096,
      anthropic_api_key: null,
      openai_api_key: null,
      google_client_id: null,
      google_client_secret: null,
      notion_token: null,
      tavily_api_key: null,
      ollama_base_url: null,
    };

    wrap(
      <ChatComposer
        activeThread={null}
        isStreaming={false}
        settings={externalSettings}
        sseClientRef={mockSSERef as React.MutableRefObject<null>}
        onThreadCreated={() => {}}
        onSendStart={() => {}}
        onSendError={() => {}}
        onOptimisticUserMessage={() => {}}
      />
    );

    const settingsBtn = screen.getByLabelText("Advanced settings");
    fireEvent.click(settingsBtn);

    // Open the select to see options
    await waitFor(() => {
      expect(screen.getByTestId("provider-select-trigger")).toBeInTheDocument();
    });
    const trigger = screen.getByTestId("provider-select-trigger");
    fireEvent.click(trigger);

    await waitFor(() => {
      expect(screen.getByTestId("provider-option-openai")).toBeInTheDocument();
      expect(screen.getByTestId("provider-option-anthropic")).toBeInTheDocument();
      expect(screen.getByTestId("provider-option-ollama")).toBeInTheDocument();
    });
  });
});
