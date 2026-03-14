/**
 * FR5: Cost, Runs & Dashboard UX Fixes
 *
 * Tests for:
 * - UX-H4: Runs page has proper empty state
 * - UX-M1: Runs shows "—" for $0.00 cost instead of $0.0000
 * - UX-M5: Artifacts page has meaningful empty state
 * - UX-M6: Queue page has holistic empty state
 * - UX-H7/H11: Cost summary includes budget_limit_usd / progress bar
 * - UX-M7: Cost records show run links
 * - UX-H8: Settings pricing reference table
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

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
// UX-H4: Runs page empty state
// ================================================================

describe("UX-H4: Runs shows empty state when no runs", () => {
  beforeEach(() => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
  });

  it("renders 'No runs yet' when runs array is empty", async () => {
    vi.resetModules();
    const { default: Runs } = await import("@/pages/Runs");
    wrap(<Runs />);

    await waitFor(() => {
      expect(screen.getByText("No runs yet")).toBeInTheDocument();
    });
  });

  it("renders empty state description pointing to Chat", async () => {
    vi.resetModules();
    const { default: Runs } = await import("@/pages/Runs");
    wrap(<Runs />);

    await waitFor(() => {
      expect(screen.getByText(/Start a conversation in Chat/)).toBeInTheDocument();
    });
  });
});

// ================================================================
// UX-M1: Runs shows "—" for zero cost
// ================================================================

describe("UX-M1: Runs shows dash for zero cost", () => {
  beforeEach(() => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({
        ok: true,
        data: [{
          id: "run-001",
          thread_id: "thread-001",
          status: "completed",
          summary: "Test run",
          risk_tier: "low",
          privacy_mode: "external",
          model: "gpt-4o",
          provider: "openai",
          tokens_in: 100,
          tokens_out: 50,
          cost_usd: 0,
          created_at: "2026-03-13T10:00:00Z",
          updated_at: "2026-03-13T10:01:00Z",
        }],
        error: null,
        trace_id: "",
      }),
    }));
  });

  it("renders '—' instead of '$0.0000' for zero cost run", async () => {
    vi.resetModules();
    const { default: Runs } = await import("@/pages/Runs");
    wrap(<Runs />);

    await waitFor(() => {
      expect(screen.getByText("Test run")).toBeInTheDocument();
    });

    // Should show "—" not "$0.0000"
    expect(screen.queryByText("$0.0000")).not.toBeInTheDocument();
    const dashes = screen.getAllByText("—");
    // At least one dash (cost column)
    expect(dashes.length).toBeGreaterThan(0);
  });
});

// ================================================================
// UX-M5: Artifacts page empty state
// ================================================================

describe("UX-M5: Artifacts shows empty state", () => {
  beforeEach(() => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
  });

  it("renders 'No artifacts yet' when artifacts array is empty", async () => {
    vi.resetModules();
    const { default: Artifacts } = await import("@/pages/Artifacts");
    wrap(<Artifacts />);

    await waitFor(() => {
      expect(screen.getByText("No artifacts yet")).toBeInTheDocument();
    });
  });

  it("renders empty state description mentioning agent outputs", async () => {
    vi.resetModules();
    const { default: Artifacts } = await import("@/pages/Artifacts");
    wrap(<Artifacts />);

    await waitFor(() => {
      expect(screen.getByText(/Artifacts are created when the agent/)).toBeInTheDocument();
    });
  });
});

// ================================================================
// UX-M6: Queue page holistic empty state
// ================================================================

describe("UX-M6: Queue shows holistic empty state", () => {
  beforeEach(() => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));
  });

  it("renders 'No active tasks' when queue is empty", async () => {
    vi.resetModules();
    const { default: Queue } = await import("@/pages/Queue");
    wrap(<Queue />);

    await waitFor(() => {
      expect(screen.getByText("No active tasks")).toBeInTheDocument();
    });
  });

  it("does not show separate Active/Queued sections when both are empty", async () => {
    vi.resetModules();
    const { default: Queue } = await import("@/pages/Queue");
    wrap(<Queue />);

    await waitFor(() => {
      expect(screen.getByText("No active tasks")).toBeInTheDocument();
    });

    // Should NOT show the per-section "Empty" text
    expect(screen.queryByText("Empty")).not.toBeInTheDocument();
  });
});

// ================================================================
// Cost page: loading, empty, budget progress bar, records
// ================================================================

describe("Cost renders loading state", () => {
  it("shows loading skeleton while fetching", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation(() => new Promise(() => {})), // never resolves
    }));

    vi.resetModules();
    const { default: Cost } = await import("@/pages/Cost");
    wrap(<Cost />);

    // While pending, the loading skeleton should be visible
    const loadingEl = document.querySelector('[role="status"]');
    expect(loadingEl).toBeTruthy();
  });
});

describe("Cost renders empty state", () => {
  it("shows 'No cost data' when no summaries and no records", async () => {
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockResolvedValue({ ok: true, data: [], error: null, trace_id: "" }),
    }));

    vi.resetModules();
    const { default: Cost } = await import("@/pages/Cost");
    wrap(<Cost />);

    await waitFor(() => {
      expect(screen.getByText("No cost data")).toBeInTheDocument();
    });
  });
});

describe("Cost renders budget progress bar", () => {
  it("renders Progress when summary has budget_limit_usd", async () => {
    const mockSummary = [
      { period: "daily", cost_usd: 3.0, tokens_in: 1000, tokens_out: 500, budget_limit_usd: 10.0 },
      { period: "monthly", cost_usd: 15.0, tokens_in: 5000, tokens_out: 2000, budget_limit_usd: 200.0 },
    ];
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/summary")) {
          return Promise.resolve({ ok: true, data: mockSummary, error: null, trace_id: "" });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "" });
      }),
    }));
    // Stub recharts to avoid ResizeObserver (not available in jsdom)
    vi.doMock("recharts", () => ({
      BarChart: () => null,
      Bar: () => null,
      XAxis: () => null,
      YAxis: () => null,
      Tooltip: () => null,
      ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
      PieChart: () => null,
      Pie: () => null,
      Cell: () => null,
    }));

    vi.resetModules();
    const { default: Cost } = await import("@/pages/Cost");
    wrap(<Cost />);

    await waitFor(() => {
      // Budget limit should be shown
      expect(screen.getByText("$10.00")).toBeInTheDocument();
    });
    // Progress element should be present
    const progress = document.querySelector('[role="progressbar"]');
    expect(progress).toBeTruthy();
  });
});

describe("Cost records show run links", () => {
  it("renders clickable row when record has run_id", async () => {
    const mockSummary = [
      { period: "daily", cost_usd: 0.05, tokens_in: 100, tokens_out: 50, budget_limit_usd: null },
    ];
    const mockRecords = [
      {
        run_id: "run-abc123",
        tokens_in: 100,
        tokens_out: 50,
        cost_usd: 0.05,
        provider: "openai",
        model: "gpt-4o",
        created_at: "2026-03-13T10:00:00Z",
      },
    ];
    vi.doMock("@/api/client", () => ({
      apiRequest: vi.fn().mockImplementation((path: string) => {
        if (path.includes("/summary")) {
          return Promise.resolve({ ok: true, data: mockSummary, error: null, trace_id: "" });
        }
        if (path.includes("/records")) {
          return Promise.resolve({ ok: true, data: mockRecords, error: null, trace_id: "" });
        }
        return Promise.resolve({ ok: true, data: [], error: null, trace_id: "" });
      }),
    }));
    // Stub recharts to avoid ResizeObserver (not available in jsdom)
    vi.doMock("recharts", () => ({
      BarChart: () => null,
      Bar: () => null,
      XAxis: () => null,
      YAxis: () => null,
      Tooltip: () => null,
      ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
      PieChart: () => null,
      Pie: () => null,
      Cell: () => null,
    }));

    vi.resetModules();
    const { default: Cost } = await import("@/pages/Cost");
    wrap(<Cost />);

    await waitFor(() => {
      // Cost records table section should be visible
      expect(screen.getByText("Cost Records")).toBeInTheDocument();
    });
    // Provider column should show openai
    expect(screen.getByText("openai")).toBeInTheDocument();
    // The clickable row should have the data-testid
    const row = document.querySelector('[data-testid="cost-record-run-run-abc123"]');
    expect(row).toBeTruthy();
    expect(row?.classList.contains("cursor-pointer")).toBe(true);
  });
});
