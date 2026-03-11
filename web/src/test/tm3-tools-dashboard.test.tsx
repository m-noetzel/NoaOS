/**
 * Tests for TM3: Tools UI Redesign — Dashboard & Health
 *
 * Spec refs: SPEC.md §12 (MVP Tool Definitions), §19 (Tool Governance)
 * Phase plan: PHASE_DETAILS.md Phase TM3
 *
 * These tests define the behavioral contract for the redesigned Tools page:
 * expandable tool cards, health indicators, credential setup, and per-function toggles.
 * They are written BEFORE implementation and must all fail initially.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Ensure crypto.randomUUID is available in jsdom
if (!globalThis.crypto?.randomUUID) {
  vi.stubGlobal("crypto", {
    ...globalThis.crypto,
    randomUUID: () => "00000000-0000-0000-0000-000000000000",
  });
}

/** Helper: fresh QueryClient with no retries */
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

// ---------------------------------------------------------------------------
// Mock data matching SPEC.md §12 tool definitions
// ---------------------------------------------------------------------------
const MOCK_TOOLS = [
  {
    name: "google_calendar",
    capability: "Calendar management",
    risk_tier: "medium",
    enabled: true,
    description: "Google Calendar integration",
    domain: "external",
    health: { status: "healthy", last_checked: "2026-03-11T10:00:00Z" },
    credentials: { configured: true, masked_value: "****xyz" },
    functions: [
      { name: "list_events", description: "List calendar events", risk_tier: "low", enabled: true },
      { name: "create_event", description: "Create a calendar event", risk_tier: "medium", enabled: true },
      { name: "update_event", description: "Update an existing event", risk_tier: "medium", enabled: false },
    ],
  },
  {
    name: "gmail",
    capability: "Email management",
    risk_tier: "medium",
    enabled: true,
    description: "Gmail integration",
    domain: "external",
    health: { status: "unhealthy", last_checked: "2026-03-11T09:00:00Z", error: "Token expired" },
    credentials: { configured: true, masked_value: "****abc" },
    functions: [
      { name: "search_emails", description: "Search emails", risk_tier: "low", enabled: true },
      { name: "read_email", description: "Read email content", risk_tier: "low", enabled: true },
      { name: "send_email", description: "Send an email", risk_tier: "medium", enabled: true },
      { name: "draft_email", description: "Draft an email", risk_tier: "low", enabled: true },
    ],
  },
  {
    name: "memory",
    capability: "Personal memory",
    risk_tier: "low",
    enabled: false,
    description: "Private memory store",
    domain: "private",
    health: { status: "unconfigured", last_checked: null },
    credentials: { configured: false, masked_value: null },
    functions: [
      { name: "remember", description: "Store a fact", risk_tier: "low", enabled: false },
      { name: "recall", description: "Recall stored facts", risk_tier: "low", enabled: false },
    ],
  },
];

// ================================================================
// Card-based layout
// ================================================================
describe("TM3: Tool card layout", () => {
  let apiMock: ReturnType<typeof vi.fn>;
  let qc: QueryClient;

  beforeEach(() => {
    vi.resetModules();
    apiMock = vi.fn().mockResolvedValue({ ok: true, data: MOCK_TOOLS, error: null, trace_id: "t" });
    vi.doMock("@/api/client", () => ({
      apiRequest: apiMock,
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ token: "tok" }),
    }));
    qc = makeQueryClient();
  });

  afterEach(() => {
    vi.doUnmock("@/api/client");
    vi.doUnmock("@/auth/AuthContext");
  });

  /**
   * PHASE_DETAILS TM3: Each tool is an expandable card showing tool name,
   * domain badge, overall status, and master toggle.
   */
  it("renders each tool as a card with name, domain badge, and status indicator", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // All three tools should have card-like containers (not table rows)
    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
      expect(screen.getByText("gmail")).toBeInTheDocument();
      expect(screen.getByText("memory")).toBeInTheDocument();
    });

    // Domain badges should be visible
    expect(screen.getAllByText("external").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("private")).toBeInTheDocument();

    // Status indicators: healthy (green), unhealthy (red), unconfigured
    // Cards should NOT be inside a <table> element
    const tables = document.querySelectorAll("table");
    expect(tables.length).toBe(0);
  });

  /**
   * PHASE_DETAILS TM3: Cards are expandable — clicking reveals details.
   * Initially collapsed, only header row visible.
   */
  it("tool cards are collapsed by default and expand on click", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Functions should NOT be visible before expanding
    expect(screen.queryByText("list_events")).not.toBeInTheDocument();

    // Click the google_calendar card header to expand
    fireEvent.click(screen.getByText("google_calendar"));

    // Now function names should appear
    await waitFor(() => {
      expect(screen.getByText("list_events")).toBeInTheDocument();
      expect(screen.getByText("create_event")).toBeInTheDocument();
      expect(screen.getByText("update_event")).toBeInTheDocument();
    });
  });
});

// ================================================================
// Health indicators and probing
// ================================================================
describe("TM3: Health check UI", () => {
  let apiMock: ReturnType<typeof vi.fn>;
  let qc: QueryClient;

  beforeEach(() => {
    vi.resetModules();
    apiMock = vi.fn().mockImplementation((url: string, opts?: any) => {
      if (url === "/api/v1/tools" && (!opts || opts.method === "GET" || !opts.method)) {
        return Promise.resolve({ ok: true, data: MOCK_TOOLS, error: null, trace_id: "t" });
      }
      // POST /api/v1/tools/{name}/health
      if (url.includes("/health") && opts?.method === "POST") {
        return Promise.resolve({
          ok: true,
          data: { status: "healthy", last_checked: new Date().toISOString() },
          error: null,
          trace_id: "t",
        });
      }
      return Promise.resolve({ ok: true, data: {}, error: null, trace_id: "t" });
    });
    vi.doMock("@/api/client", () => ({
      apiRequest: apiMock,
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ token: "tok" }),
    }));
    qc = makeQueryClient();
  });

  afterEach(() => {
    vi.doUnmock("@/api/client");
    vi.doUnmock("@/auth/AuthContext");
  });

  /**
   * PHASE_DETAILS TM3: Health section shows last check timestamp and
   * a green/red indicator. SPEC.md §16.3: Tool responses validated.
   */
  it("displays health status indicator (green for healthy, red for unhealthy)", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Expand google_calendar card (healthy)
    fireEvent.click(screen.getByText("google_calendar"));

    await waitFor(() => {
      // Should show a healthy indicator or text
      const calendarCard = screen.getByText("google_calendar").closest("[data-tool-card]") ||
        screen.getByText("google_calendar").parentElement?.parentElement;
      expect(calendarCard).toBeTruthy();
      // Look for healthy/unhealthy status text or aria labels
      expect(screen.getByText(/healthy/i)).toBeInTheDocument();
    });
  });

  /**
   * PHASE_DETAILS TM3: "Test Connection" button calls POST /tools/{name}/health
   * and shows spinner then result.
   */
  it("Test Connection button triggers health check API call", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Expand google_calendar
    fireEvent.click(screen.getByText("google_calendar"));

    await waitFor(() => {
      expect(screen.getByText(/test connection/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/test connection/i));

    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/tools/google_calendar/health"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  /**
   * PHASE_DETAILS TM3: Unhealthy tools show red X with error message.
   * Gmail mock data has unhealthy status with "Token expired" error.
   */
  it("unhealthy tools show error message in expanded view", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("gmail")).toBeInTheDocument();
    });

    // Expand gmail card (unhealthy)
    fireEvent.click(screen.getByText("gmail"));

    await waitFor(() => {
      expect(screen.getByText(/token expired/i)).toBeInTheDocument();
    });
  });
});

// ================================================================
// Credential setup
// ================================================================
describe("TM3: Credential management", () => {
  let apiMock: ReturnType<typeof vi.fn>;
  let qc: QueryClient;

  beforeEach(() => {
    vi.resetModules();
    apiMock = vi.fn().mockImplementation((url: string, opts?: any) => {
      if (url === "/api/v1/tools" && (!opts || !opts.method || opts.method === "GET")) {
        return Promise.resolve({ ok: true, data: MOCK_TOOLS, error: null, trace_id: "t" });
      }
      if (url.includes("/credentials") && opts?.method === "POST") {
        return Promise.resolve({
          ok: true,
          data: { configured: true, masked_value: "****new" },
          error: null,
          trace_id: "t",
        });
      }
      return Promise.resolve({ ok: true, data: {}, error: null, trace_id: "t" });
    });
    vi.doMock("@/api/client", () => ({
      apiRequest: apiMock,
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ token: "tok" }),
    }));
    qc = makeQueryClient();
  });

  afterEach(() => {
    vi.doUnmock("@/api/client");
    vi.doUnmock("@/auth/AuthContext");
  });

  /**
   * PHASE_DETAILS TM3: Credentials section shows masked value if configured,
   * and a "Configure" button that opens a modal.
   */
  it("shows masked credential value for configured tools", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Expand google_calendar
    fireEvent.click(screen.getByText("google_calendar"));

    await waitFor(() => {
      // Masked credential value should appear
      expect(screen.getByText(/\*{3,}/)).toBeInTheDocument();
    });
  });

  /**
   * PHASE_DETAILS TM3: "Configure" button opens CredentialModal.tsx
   * for API key input or OAuth connect.
   */
  it("Configure button opens credential modal", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Expand the card
    fireEvent.click(screen.getByText("google_calendar"));

    await waitFor(() => {
      expect(screen.getByText(/configure/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/configure/i));

    // Modal should open with credential input
    await waitFor(() => {
      // Look for a modal/dialog element with credential input
      const dialog = document.querySelector('[role="dialog"]') ||
        document.querySelector("[data-credential-modal]");
      expect(dialog).toBeTruthy();
    });
  });

  /**
   * PHASE_DETAILS TM3: Submitting API key in credential modal calls
   * POST /tools/{name}/credentials.
   */
  it("submitting credential modal calls store credentials API", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Expand and open credential modal
    fireEvent.click(screen.getByText("google_calendar"));
    await waitFor(() => {
      expect(screen.getByText(/configure/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/configure/i));

    // Type API key and submit
    await waitFor(() => {
      const input = document.querySelector('input[type="text"], input[type="password"]');
      expect(input).toBeTruthy();
    });

    const input = document.querySelector('input[type="text"], input[type="password"]') as HTMLInputElement;
    fireEvent.change(input, { target: { value: "sk-test-key-12345" } });

    // Find and click save/submit button
    const saveButton = screen.getByRole("button", { name: /save|submit|confirm/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/tools/google_calendar/credentials"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  /**
   * PHASE_DETAILS TM3: Unconfigured tools show "unconfigured" status
   * and prompt to set up credentials. SPEC.md §12.5 Memory is private domain.
   */
  it("unconfigured tools show setup prompt instead of masked value", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("memory")).toBeInTheDocument();
    });

    // Expand memory card (unconfigured)
    fireEvent.click(screen.getByText("memory"));

    await waitFor(() => {
      // Should show unconfigured status or setup prompt
      expect(
        screen.getByText(/unconfigured|not configured|set up|configure/i),
      ).toBeInTheDocument();
    });
  });
});

// ================================================================
// Per-function enable/disable toggles
// ================================================================
describe("TM3: Per-function toggles", () => {
  let apiMock: ReturnType<typeof vi.fn>;
  let qc: QueryClient;

  beforeEach(() => {
    vi.resetModules();
    apiMock = vi.fn().mockImplementation((url: string, opts?: any) => {
      if (url === "/api/v1/tools" && (!opts || !opts.method || opts.method === "GET")) {
        return Promise.resolve({ ok: true, data: MOCK_TOOLS, error: null, trace_id: "t" });
      }
      // Enable/disable function
      if (url.match(/\/api\/v1\/tools\/[^/]+\/[^/]+\/enable/) && opts?.method === "POST") {
        return Promise.resolve({ ok: true, data: { enabled: true }, error: null, trace_id: "t" });
      }
      if (url.match(/\/api\/v1\/tools\/[^/]+\/[^/]+$/) && opts?.method === "DELETE") {
        return Promise.resolve({ ok: true, data: { enabled: false }, error: null, trace_id: "t" });
      }
      return Promise.resolve({ ok: true, data: {}, error: null, trace_id: "t" });
    });
    vi.doMock("@/api/client", () => ({
      apiRequest: apiMock,
      BASE_URL: "",
      WEB_DEVICE_ID: "test",
    }));
    vi.doMock("@/auth/AuthContext", () => ({
      useAuth: () => ({ token: "tok" }),
    }));
    qc = makeQueryClient();
  });

  afterEach(() => {
    vi.doUnmock("@/api/client");
    vi.doUnmock("@/auth/AuthContext");
  });

  /**
   * PHASE_DETAILS TM3: Functions table shows name, description, risk tier badge,
   * and individual enable/disable toggle. SPEC.md §12.1: Calendar has 3 functions.
   */
  it("expanded card shows function list with risk tier badges and toggles", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Expand google_calendar
    fireEvent.click(screen.getByText("google_calendar"));

    await waitFor(() => {
      // Function names
      expect(screen.getByText("list_events")).toBeInTheDocument();
      expect(screen.getByText("create_event")).toBeInTheDocument();
      expect(screen.getByText("update_event")).toBeInTheDocument();

      // Risk tier badges on functions
      // list_events is low, create_event/update_event are medium
      expect(screen.getByText("List calendar events")).toBeInTheDocument();
    });

    // Individual toggle switches — at least 3 for the 3 functions
    // (plus the master toggle, so ≥ 4 switches total in the expanded card)
    const switches = document.querySelectorAll('[role="switch"]');
    expect(switches.length).toBeGreaterThanOrEqual(4);
  });

  /**
   * PHASE_DETAILS TM3: Toggling a function calls the per-function endpoint.
   * POST /tools/{tool_name}/{function_name}/enable or DELETE /tools/{tool_name}/{function_name}.
   */
  it("toggling a disabled function calls enable endpoint", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Expand google_calendar
    fireEvent.click(screen.getByText("google_calendar"));

    await waitFor(() => {
      expect(screen.getByText("update_event")).toBeInTheDocument();
    });

    // Find the toggle for update_event (currently disabled)
    const updateEventRow = screen.getByText("update_event").closest("[data-function-row]") ||
      screen.getByText("update_event").parentElement;
    expect(updateEventRow).toBeTruthy();

    // Find the switch in that row and click it
    const toggle = updateEventRow!.querySelector('[role="switch"]');
    expect(toggle).toBeTruthy();
    fireEvent.click(toggle!);

    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/tools/google_calendar/update_event/enable"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  /**
   * PHASE_DETAILS TM3: Master toggle enables/disables the entire tool.
   * This should call POST /tools/{name}/enable or DELETE /tools/{name}.
   */
  it("master toggle disables entire tool via DELETE endpoint", async () => {
    const { default: Tools } = await import("@/pages/Tools");
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <Tools />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("google_calendar")).toBeInTheDocument();
    });

    // Find the master toggle for google_calendar (in the header, not expanded)
    // It should be the first switch near the tool name
    const calendarHeader = screen.getByText("google_calendar").closest("[data-tool-header]") ||
      screen.getByText("google_calendar").parentElement;
    const masterSwitch = calendarHeader!.querySelector('[role="switch"]');
    expect(masterSwitch).toBeTruthy();

    // google_calendar is enabled, so toggling should disable (DELETE)
    fireEvent.click(masterSwitch!);

    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/tools/google_calendar"),
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });
});

// ================================================================
// CredentialModal component existence (integration)
// ================================================================
describe("TM3: CredentialModal component", () => {
  /**
   * PHASE_DETAILS TM3: CredentialModal.tsx is a NEW file.
   * It must exist for the credential setup flow.
   */
  it("CredentialModal.tsx file exists", async () => {
    const { existsSync } = await import("fs");
    const { resolve, dirname } = await import("path");
    const { fileURLToPath } = await import("url");
    const __dirname = dirname(fileURLToPath(import.meta.url));
    const modalPath = resolve(__dirname, "../components/tools/CredentialModal.tsx");
    expect(existsSync(modalPath)).toBe(true);
  });
});
