/**
 * RV1: Run Viewer — Event Payload & Cost Fixes
 * Tests for buildCostItems() and the key-mismatch fixes.
 */
import { describe, it, expect } from "vitest";
import { buildCostItems } from "@/components/runs/CostBreakdown";
import type { RunEvent } from "@/api/types";

function makeEvent(
  type: string,
  data: Record<string, unknown>,
  id = Math.random().toString(36),
): RunEvent {
  return {
    id,
    run_id: "run-1",
    type,
    data,
    created_at: new Date().toISOString(),
  } as RunEvent;
}

describe("buildCostItems — llm_usage from result_ready", () => {
  it("returns LLM rows from result_ready.llm_usage", () => {
    const events = [
      makeEvent("result_ready", {
        response: "Hello",
        total_cost: 0.0012,
        llm_usage: [
          { provider: "openai", model: "gpt-4.1-mini", input_tokens: 200, output_tokens: 80, cost_usd: 0.0012 },
        ],
      }),
    ];
    const items = buildCostItems(events);
    expect(items).toHaveLength(1);
    expect(items[0].name).toBe("LLM · gpt-4.1-mini");
    expect(items[0].tokens_in).toBe(200);
    expect(items[0].tokens_out).toBe(80);
    expect(items[0].cost).toBeCloseTo(0.0012);
  });

  it("returns multiple LLM rows for multi-turn tool use", () => {
    const events = [
      makeEvent("result_ready", {
        response: "Done",
        total_cost: 0.003,
        llm_usage: [
          { provider: "openai", model: "gpt-4.1-mini", input_tokens: 300, output_tokens: 50, cost_usd: 0.0015 },
          { provider: "openai", model: "gpt-4.1-mini", input_tokens: 400, output_tokens: 100, cost_usd: 0.0015 },
        ],
      }),
    ];
    const items = buildCostItems(events);
    expect(items).toHaveLength(2);
    expect(items[0].name).toBe("LLM · gpt-4.1-mini");
    expect(items[1].name).toBe("LLM · gpt-4.1-mini");
  });

  it("falls back to total_cost row when llm_usage is empty", () => {
    const events = [
      makeEvent("result_ready", {
        response: "Done",
        total_cost: 0.005,
        llm_usage: [],
      }),
    ];
    const items = buildCostItems(events);
    expect(items).toHaveLength(1);
    expect(items[0].name).toBe("LLM (total)");
    expect(items[0].cost).toBeCloseTo(0.005);
  });

  it("returns empty when no result_ready and no tool_called events", () => {
    const events = [makeEvent("message_received", { message: "hi" })];
    const items = buildCostItems(events);
    expect(items).toHaveLength(0);
  });

  it("includes tool rows at $0 when tool_called events present", () => {
    const events = [
      makeEvent("tool_called", { tool_call: { name: "web_search", args: { query: "test" } }, tool_name: "web_search" }),
      makeEvent("tool_called", { tool_call: { name: "notion__create_page", args: {} }, tool_name: "notion__create_page" }),
      makeEvent("result_ready", {
        response: "Done",
        total_cost: 0.002,
        llm_usage: [{ provider: "openai", model: "gpt-4.1-mini", input_tokens: 100, output_tokens: 40, cost_usd: 0.002 }],
      }),
    ];
    const items = buildCostItems(events);
    // 1 LLM row + 2 tool rows
    expect(items).toHaveLength(3);
    const toolItems = items.filter((i) => i.name.startsWith("tool ·"));
    expect(toolItems).toHaveLength(2);
    expect(toolItems.every((i) => i.cost === 0)).toBe(true);
    expect(toolItems.map((i) => i.name)).toContain("tool · web_search");
    expect(toolItems.map((i) => i.name)).toContain("tool · notion__create_page");
  });

  it("uses run.steps when available (canonical source)", () => {
    const run = {
      steps: [
        { name: "Agent turn 1", tokens_in: 500, tokens_out: 200, cost: 0.005 },
        { name: "web_search", tokens_in: 0, tokens_out: 0, cost: 0 },
      ],
    } as unknown as import("@/api/types").Run;
    const items = buildCostItems([], run);
    expect(items).toHaveLength(2);
    expect(items[0].name).toBe("Agent turn 1");
    expect(items[0].cost).toBe(0.005);
  });

  it("uses provider as fallback label when model is missing", () => {
    const events = [
      makeEvent("result_ready", {
        response: "ok",
        total_cost: 0.001,
        llm_usage: [{ provider: "ollama", model: "", input_tokens: 100, output_tokens: 50, cost_usd: 0.001 }],
      }),
    ];
    const items = buildCostItems(events);
    expect(items[0].name).toBe("LLM · ollama");
  });

  it("estimates cost when cost_usd is missing from usage entry", () => {
    const events = [
      makeEvent("result_ready", {
        response: "ok",
        total_cost: 0,
        llm_usage: [{ provider: "openai", model: "gpt-4.1-mini", input_tokens: 1000, output_tokens: 500 }],
      }),
    ];
    const items = buildCostItems(events);
    expect(items[0].cost).toBeGreaterThan(0);
  });
});
