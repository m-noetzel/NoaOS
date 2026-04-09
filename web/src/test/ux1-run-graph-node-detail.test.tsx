/**
 * UX1: Execution Graph Node Detail Content
 *
 * Tests for:
 * - Classifier node detail shows task_type when event data is available
 * - Planner node detail shows plan content (archetype + plan text)
 * - Empty state shown when no data available for classifier/planner/evaluator
 * - Evaluator node detail shows eval scores and verdict
 * - Classifier node is inserted in graph when classification_done event present
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import type { RunEvent } from "@/api/types";

// ================================================================
// Mocks — only mock system boundaries
// ================================================================

vi.mock("@/components/runs/ReplayActions", () => ({
  NodeReplayActions: () => null,
}));

// ================================================================
// Helper: render RunGraph with events
// ================================================================

async function renderRunGraph(events: RunEvent[]) {
  // Dynamic import so vi.mock() is applied first
  const { RunGraph } = await import("@/components/runs/RunGraph");
  return render(<RunGraph events={events} runId="test-run-1" />);
}

function makeEvent(id: string, type: string, data: Record<string, unknown>): RunEvent {
  return {
    id,
    run_id: "test-run-1",
    type,
    data,
    created_at: "2026-04-01T10:00:00Z",
  };
}

// ================================================================
// Test: Classifier node appears when classification_done event present
// ================================================================

describe("UX1: Classifier node in graph", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.mock("@/components/runs/ReplayActions", () => ({
      NodeReplayActions: () => null,
    }));
  });

  it("renders a Classifier node when classification_done event is present", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Hello" }),
      makeEvent("e2", "classification_done", {
        task_type: "simple_utility",
        privacy_mode: "external",
        model: "gpt-4o-mini",
      }),
      makeEvent("e3", "result_ready", { response_text: "Hi there!" }),
    ];

    await renderRunGraph(events);

    // The node label "Classifier" appears in the truncate span inside the button
    const classifierNodes = screen.getAllByText("Classifier");
    expect(classifierNodes.length).toBeGreaterThan(0);
  });

  it("does not render Classifier node when no classification_done event", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Hello" }),
      makeEvent("e2", "planner_step", { step: "Planning", strategy_summary: "Simple response" }),
      makeEvent("e3", "result_ready", { response_text: "Hi there!" }),
    ];

    await renderRunGraph(events);

    expect(screen.queryByText("Classifier")).not.toBeInTheDocument();
    // Planner is still shown
    expect(screen.getAllByText("Planner").length).toBeGreaterThan(0);
  });
});

// ================================================================
// Test: Classifier detail panel shows task_type
// ================================================================

describe("UX1: Classifier detail panel", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.mock("@/components/runs/ReplayActions", () => ({
      NodeReplayActions: () => null,
    }));
  });

  it("shows task_type in detail panel when classifier node is clicked", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "What time is it?" }),
      makeEvent("e2", "classification_done", {
        task_type: "simple_utility",
        privacy_mode: "external",
        model: "gpt-4o-mini",
      }),
      makeEvent("e3", "result_ready", { response_text: "It's 10am." }),
    ];

    await renderRunGraph(events);

    // Click the Classifier node — use getAllByText since label + subtitle both say "Classifier"
    const classifierLabels = screen.getAllByText("Classifier");
    const classifierButton = classifierLabels[0].closest("button");
    expect(classifierButton).toBeTruthy();
    fireEvent.click(classifierButton!);

    // Detail panel should show task_type value
    expect(screen.getByText("simple_utility")).toBeInTheDocument();
    expect(screen.getByText("Task type:")).toBeInTheDocument();
  });

  it("shows privacy_mode in classifier detail panel", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "What time is it?" }),
      makeEvent("e2", "classification_done", {
        task_type: "research",
        privacy_mode: "private",
        model: "gpt-4o-mini",
      }),
      makeEvent("e3", "result_ready", { response_text: "Research done." }),
    ];

    await renderRunGraph(events);

    const classifierLabels = screen.getAllByText("Classifier");
    const classifierButton = classifierLabels[0].closest("button");
    fireEvent.click(classifierButton!);

    expect(screen.getByText("research")).toBeInTheDocument();
    expect(screen.getByText("private")).toBeInTheDocument();
  });

  it("shows empty state when classification_done has no task_type or privacy_mode", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Hello" }),
      makeEvent("e2", "classification_done", {}), // empty data
      makeEvent("e3", "result_ready", { response_text: "Hi" }),
    ];

    await renderRunGraph(events);

    const classifierLabels = screen.getAllByText("Classifier");
    const classifierButton = classifierLabels[0].closest("button");
    fireEvent.click(classifierButton!);

    expect(screen.getByText("No classification data available")).toBeInTheDocument();
  });
});

// ================================================================
// Test: Planner detail panel shows plan content
// ================================================================

describe("UX1: Planner detail panel", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.mock("@/components/runs/ReplayActions", () => ({
      NodeReplayActions: () => null,
    }));
  });

  it("shows plan text in planner detail panel", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Research quantum computing" }),
      makeEvent("e2", "planner_step", {
        step: "Planning",
        plan: "1. Search arxiv\n2. Synthesize findings\n3. Summarize key papers",
        archetype: "research",
        strategy_summary: "Multi-source research with synthesis",
      }),
      makeEvent("e3", "result_ready", { response_text: "Here are the findings..." }),
    ];

    await renderRunGraph(events);

    const plannerLabels = screen.getAllByText("Planner");
    const plannerButton = plannerLabels[0].closest("button");
    fireEvent.click(plannerButton!);

    expect(screen.getByText("Plan:")).toBeInTheDocument();
    // pre element contains multiline text — use a partial match
    expect(screen.getByText(/1\. Search arxiv/)).toBeInTheDocument();
  });

  it("shows archetype badge when planner event has archetype field", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Compare options" }),
      makeEvent("e2", "planner_step", {
        step: "Planning",
        archetype: "comparative_selection",
        plan: "1. Identify options\n2. Compare\n3. Recommend",
      }),
      makeEvent("e3", "result_ready", { response_text: "Here's the comparison..." }),
    ];

    await renderRunGraph(events);

    const plannerLabels = screen.getAllByText("Planner");
    const plannerButton = plannerLabels[0].closest("button");
    fireEvent.click(plannerButton!);

    expect(screen.getByText("Archetype:")).toBeInTheDocument();
    expect(screen.getByText("comparative_selection")).toBeInTheDocument();
  });

  it("shows empty state when planner event has no planning data", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Hello" }),
      makeEvent("e2", "planner_step", { step: "Planning" }), // no plan/archetype/strategy
      makeEvent("e3", "result_ready", { response_text: "Hi!" }),
    ];

    await renderRunGraph(events);

    const plannerLabels = screen.getAllByText("Planner");
    const plannerButton = plannerLabels[0].closest("button");
    fireEvent.click(plannerButton!);

    expect(screen.getByText("No planning data available")).toBeInTheDocument();
  });
});

// ================================================================
// Test: Evaluator node detail panel
// ================================================================

describe("UX1: Evaluator detail panel", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.mock("@/components/runs/ReplayActions", () => ({
      NodeReplayActions: () => null,
    }));
  });

  it("renders evaluator node when step_started evaluator event is present", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Hello" }),
      makeEvent("e2", "planner_step", { step: "Planning", strategy_summary: "Simple" }),
      makeEvent("e3", "step_started", { step: "evaluator" }),
      makeEvent("e4", "result_ready", {
        response_text: "Hi!",
        eval_verdict: "pass",
        eval_scores: { relevance: 0.9, clarity: 0.85 },
      }),
    ];

    await renderRunGraph(events);

    const evaluatorNodes = screen.getAllByText("Evaluator");
    expect(evaluatorNodes.length).toBeGreaterThan(0);
  });

  it("shows eval verdict and scores when evaluator node is clicked", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Hello" }),
      makeEvent("e2", "planner_step", { step: "Planning", strategy_summary: "Simple" }),
      makeEvent("e3", "step_started", { step: "evaluator" }),
      makeEvent("e4", "result_ready", {
        response_text: "Hi!",
        eval_verdict: "pass",
        eval_scores: { relevance: 0.9, clarity: 0.85 },
      }),
    ];

    await renderRunGraph(events);

    const evaluatorLabels = screen.getAllByText("Evaluator");
    const evaluatorButton = evaluatorLabels[0].closest("button");
    fireEvent.click(evaluatorButton!);

    expect(screen.getByText("Verdict:")).toBeInTheDocument();
    expect(screen.getByText("pass")).toBeInTheDocument();
    expect(screen.getByText("Scores:")).toBeInTheDocument();
    expect(screen.getByText("0.90")).toBeInTheDocument();
    expect(screen.getByText("0.85")).toBeInTheDocument();
  });

  it("shows empty state when evaluator node has no eval data", async () => {
    const events: RunEvent[] = [
      makeEvent("e1", "message_received", { text: "Hello" }),
      makeEvent("e2", "planner_step", { step: "Planning", strategy_summary: "Simple" }),
      makeEvent("e3", "step_started", { step: "evaluator" }),
      // No eval_verdict or eval_scores in result_ready
      makeEvent("e4", "result_ready", { response_text: "Hi!" }),
    ];

    await renderRunGraph(events);

    const evaluatorLabels = screen.getAllByText("Evaluator");
    const evaluatorButton = evaluatorLabels[0].closest("button");
    fireEvent.click(evaluatorButton!);

    expect(screen.getByText("No evaluation data available")).toBeInTheDocument();
  });
});

// ================================================================
// Test: No events / empty state
// ================================================================

describe("UX1: Empty state", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.mock("@/components/runs/ReplayActions", () => ({
      NodeReplayActions: () => null,
    }));
  });

  it("shows 'No events' message when events array is empty", async () => {
    await renderRunGraph([]);

    expect(screen.getByText("No events to visualize.")).toBeInTheDocument();
  });
});
