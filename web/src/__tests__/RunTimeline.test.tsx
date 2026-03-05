import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RunTimeline } from "../components/Run/RunTimeline";
import { RunHistory } from "../components/Run/RunHistory";
import { useRunStore } from "../store/runs";
import type { Run, RunEvent } from "../store/runs";

/** Helper to build a RunEvent with defaults. */
function makeEvent(
  overrides: Partial<RunEvent> & { type: RunEvent["type"] },
): RunEvent {
  return {
    id: `evt-${Math.random().toString(36).slice(2, 8)}`,
    data: {},
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

/** Helper to build a Run with defaults. */
function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: `run-${Math.random().toString(36).slice(2, 8)}`,
    status: "running",
    risk_tier: "low",
    privacy_mode: "private",
    events: [],
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("RunTimeline", () => {
  it("renders events in chronological order", () => {
    const events: RunEvent[] = [
      makeEvent({
        id: "e3",
        type: "result_ready",
        timestamp: "2026-03-05T10:02:00Z",
        data: { result: "done" },
      }),
      makeEvent({
        id: "e1",
        type: "classification_done",
        timestamp: "2026-03-05T10:00:00Z",
        data: { class: "query" },
      }),
      makeEvent({
        id: "e2",
        type: "tool_called",
        timestamp: "2026-03-05T10:01:00Z",
        data: { tool: "search" },
      }),
    ];

    const run = makeRun({ events });
    render(<RunTimeline run={run} />);

    const list = screen.getByRole("list", { name: /run events/i });
    const items = within(list).getAllByRole("listitem");

    // Verify chronological ordering: classification_done -> tool_called -> result_ready
    expect(within(items[0]).getByText("Classification")).toBeInTheDocument();
    expect(within(items[1]).getByText("Tool Called")).toBeInTheDocument();
    expect(within(items[2]).getByText("Result Ready")).toBeInTheDocument();
  });

  it("renders each event type with appropriate indicator", () => {
    const eventTypes: RunEvent["type"][] = [
      "classification_done",
      "tool_called",
      "tool_result",
      "approval_requested",
      "result_ready",
      "error",
    ];

    const events = eventTypes.map((type, i) =>
      makeEvent({
        id: `ind-${i}`,
        type,
        timestamp: new Date(2026, 2, 5, 10, i).toISOString(),
      }),
    );

    const run = makeRun({ events });
    render(<RunTimeline run={run} />);

    // Each event type should have its own indicator rendered
    expect(screen.getByTestId("event-indicator-classification_done")).toBeInTheDocument();
    expect(screen.getByTestId("event-indicator-tool_called")).toBeInTheDocument();
    expect(screen.getByTestId("event-indicator-tool_result")).toBeInTheDocument();
    expect(screen.getByTestId("event-indicator-approval_requested")).toBeInTheDocument();
    expect(screen.getByTestId("event-indicator-result_ready")).toBeInTheDocument();
    expect(screen.getByTestId("event-indicator-error")).toBeInTheDocument();
  });

  it("event details are expandable (click to show args/results)", async () => {
    const user = userEvent.setup();
    const events = [
      makeEvent({
        id: "expand-1",
        type: "tool_called",
        data: { tool: "web_search", args: { query: "test query" } },
        timestamp: "2026-03-05T10:00:00Z",
      }),
    ];

    const run = makeRun({ events });
    render(<RunTimeline run={run} />);

    // Details should not be visible initially
    expect(screen.queryByRole("region", { name: /event details/i })).not.toBeInTheDocument();

    // Click to expand
    const expandButton = screen.getByRole("button", {
      name: /tool called event details/i,
    });
    expect(expandButton).toHaveAttribute("aria-expanded", "false");

    await user.click(expandButton);

    expect(expandButton).toHaveAttribute("aria-expanded", "true");
    const details = screen.getByRole("region", { name: /event details/i });
    expect(details).toBeInTheDocument();
    expect(details).toHaveTextContent("web_search");
    expect(details).toHaveTextContent("test query");

    // Click again to collapse
    await user.click(expandButton);
    expect(expandButton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("region", { name: /event details/i })).not.toBeInTheDocument();
  });

  it("displays run metadata (status, risk_tier, privacy_mode)", () => {
    const run = makeRun({
      status: "awaiting_approval",
      risk_tier: "high",
      privacy_mode: "external",
    });

    render(<RunTimeline run={run} />);

    expect(screen.getByTestId("run-status")).toHaveTextContent(
      "Awaiting Approval",
    );
    expect(screen.getByTestId("run-risk-tier")).toHaveTextContent("high");
    expect(screen.getByTestId("run-privacy-mode")).toHaveTextContent(
      "external",
    );
  });

  it("new events appear in real-time (simulated via state updates)", () => {
    const run = makeRun({
      id: "rt-run",
      events: [
        makeEvent({
          id: "rt-1",
          type: "classification_done",
          timestamp: "2026-03-05T10:00:00Z",
        }),
      ],
    });

    const { rerender } = render(<RunTimeline run={run} />);

    const list = screen.getByRole("list", { name: /run events/i });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);

    // Simulate new event arriving by re-rendering with updated run
    const updatedRun: Run = {
      ...run,
      events: [
        ...run.events,
        makeEvent({
          id: "rt-2",
          type: "tool_called",
          timestamp: "2026-03-05T10:01:00Z",
          data: { tool: "calculator" },
        }),
      ],
    };

    rerender(<RunTimeline run={updatedRun} />);

    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("Tool Called")).toBeInTheDocument();
  });

  it("error events render with error styling", () => {
    const events = [
      makeEvent({
        id: "err-1",
        type: "error",
        data: { message: "Something went wrong" },
        timestamp: "2026-03-05T10:00:00Z",
      }),
    ];

    const run = makeRun({ events });
    render(<RunTimeline run={run} />);

    const errorCard = screen.getByTestId("event-card-err-1");
    expect(errorCard).toHaveClass("event-card--error");
  });
});

describe("RunHistory", () => {
  it("shows recent runs with status badges", () => {
    const runs: Run[] = [
      makeRun({
        id: "run-1",
        status: "completed",
        summary: "Search query completed",
        created_at: "2026-03-05T09:00:00Z",
      }),
      makeRun({
        id: "run-2",
        status: "failed",
        summary: "Tool execution failed",
        created_at: "2026-03-05T10:00:00Z",
      }),
      makeRun({
        id: "run-3",
        status: "running",
        summary: "Processing request",
        created_at: "2026-03-05T11:00:00Z",
      }),
    ];

    const onSelectRun = () => {};
    render(
      <RunHistory runs={runs} activeRunId={null} onSelectRun={onSelectRun} />,
    );

    const list = screen.getByRole("list", { name: /recent runs/i });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);

    // Runs should be sorted most recent first
    expect(within(items[0]).getByText("Processing request")).toBeInTheDocument();
    expect(within(items[1]).getByText("Tool execution failed")).toBeInTheDocument();
    expect(within(items[2]).getByText("Search query completed")).toBeInTheDocument();

    // Status badges should be present
    expect(screen.getByTestId("run-badge-run-1")).toHaveTextContent("completed");
    expect(screen.getByTestId("run-badge-run-2")).toHaveTextContent("failed");
    expect(screen.getByTestId("run-badge-run-3")).toHaveTextContent("running");
  });

  it("calls onSelectRun when a run is clicked", async () => {
    const user = userEvent.setup();
    const runs: Run[] = [
      makeRun({ id: "click-run", summary: "Click me" }),
    ];

    let selectedId: string | null = null;
    const onSelectRun = (id: string) => {
      selectedId = id;
    };

    render(
      <RunHistory runs={runs} activeRunId={null} onSelectRun={onSelectRun} />,
    );

    await user.click(screen.getByRole("button", { name: /run click-run/i }));
    expect(selectedId).toBe("click-run");
  });
});

describe("useRunStore", () => {
  it("manages runs and events via the Zustand store", () => {
    const store = useRunStore.getState();

    const run = makeRun({ id: "store-run-1", events: [] });
    store.addRun(run);

    expect(useRunStore.getState().runs).toHaveLength(1);
    expect(useRunStore.getState().getRun("store-run-1")?.status).toBe(
      "running",
    );

    store.updateRunStatus("store-run-1", "completed");
    expect(useRunStore.getState().getRun("store-run-1")?.status).toBe(
      "completed",
    );

    const event = makeEvent({ id: "store-evt-1", type: "tool_called" });
    store.addEvent("store-run-1", event);
    expect(
      useRunStore.getState().getRun("store-run-1")?.events,
    ).toHaveLength(1);

    store.setActiveRun("store-run-1");
    expect(useRunStore.getState().getActiveRun()?.id).toBe("store-run-1");
  });
});
