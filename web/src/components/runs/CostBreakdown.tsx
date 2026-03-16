import type { Run, RunEvent } from "@/api/types";
import { DollarSign, AlertTriangle } from "lucide-react";
import { asString, asRecord } from "@/lib/utils";

interface CostItem {
  name: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
}

// Simple cost model: $3/M input, $15/M output (Claude 3.5 Sonnet-like)
function estimateCost(tokensIn: number, tokensOut: number): number {
  return (tokensIn * 3 + tokensOut * 15) / 1_000_000;
}

export function buildCostItems(events: RunEvent[], run?: Run): CostItem[] {
  // If run has steps, use those directly (canonical source)
  if (run?.steps?.length) {
    return run.steps.map((s) => ({
      name: s.name,
      tokens_in: s.tokens_in,
      tokens_out: s.tokens_out,
      cost: s.cost,
    }));
  }

  // Fallback: estimate from events
  const items: CostItem[] = [];

  const plannerEvents = events.filter((e) => e.type === "planner_step");
  if (plannerEvents.length) {
    const tIn = plannerEvents.reduce((s, e) => s + (typeof e.data.tokens_in === "number" ? e.data.tokens_in : 0), 0);
    const tOut = plannerEvents.reduce((s, e) => s + (typeof e.data.tokens_out === "number" ? e.data.tokens_out : 0), 0);
    items.push({ name: "Planner", tokens_in: tIn, tokens_out: tOut, cost: estimateCost(tIn, tOut) });
  }

  const toolCalls = events.filter((e) => e.type === "tool_called");
  const toolResults = events.filter((e) => e.type === "tool_result");
  for (const tc of toolCalls) {
    const tcInner = asRecord(tc.data.tool_call);
    const toolName = asString(tcInner.name) || asString(tc.data.tool_name) || "tool";
    const result = toolResults.find((r) => {
      const trInner = asRecord(r.data.tool_result);
      return (asString(trInner.name) || asString(r.data.tool_name)) === toolName;
    });
    const tIn = typeof result?.data.tokens_in === "number" ? result.data.tokens_in : 0;
    const tOut = typeof result?.data.tokens_out === "number" ? result.data.tokens_out : 0;
    items.push({ name: toolName, tokens_in: tIn, tokens_out: tOut, cost: estimateCost(tIn, tOut) });
  }

  const resultEvent = events.find((e) => e.type === "result_ready");
  if (resultEvent) {
    const tIn = typeof resultEvent.data.tokens_in === "number" ? resultEvent.data.tokens_in : 0;
    const tOut = typeof resultEvent.data.tokens_out === "number" ? resultEvent.data.tokens_out : 0;
    items.push({ name: "Final response", tokens_in: tIn, tokens_out: tOut, cost: estimateCost(tIn, tOut) });
  }

  return items;
}

interface CostBreakdownProps {
  events: RunEvent[];
  run?: Run;
}

export function CostBreakdown({ events, run }: CostBreakdownProps) {
  const items = buildCostItems(events, run);
  const stepTotal = items.reduce((s, i) => s + i.cost, 0);
  const headerTotal = run?.cost_usd;
  // Only show mismatch when we have real step-level costs (from run.steps), not estimated
  const hasRealStepCosts = !!(run?.steps?.length);
  const hasMismatch = hasRealStepCosts && headerTotal !== undefined && Math.abs(headerTotal - stepTotal) > 0.0001;

  if (!items.length) return null;

  return (
    <div className="rounded-xl border border-border/40 glass p-4 space-y-3">
      <div className="flex items-center gap-2">
        <DollarSign className="h-4 w-4 text-success" />
        <h3 className="text-sm font-semibold">Cost Breakdown</h3>
      </div>

      {hasMismatch && (
        <div className="flex items-center gap-2 rounded-lg bg-warning/10 border border-warning/30 p-2.5 text-xs text-warning">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <div>
            <span className="font-medium">Cost mismatch detected</span>
            <span className="text-warning/70 ml-1">
              Header: ${headerTotal!.toFixed(4)} · Steps: ${stepTotal.toFixed(4)} · Δ ${Math.abs(headerTotal! - stepTotal).toFixed(4)}
            </span>
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        {items.map((item, i) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="font-mono text-muted-foreground">{item.name}</span>
            <div className="flex items-center gap-3">
              <span className="text-[10px] text-muted-foreground/50 font-mono">
                {item.tokens_in + item.tokens_out} tok
              </span>
              <span className="font-mono font-medium text-foreground w-16 text-right">
                ${item.cost.toFixed(4)}
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className="border-t border-border/30 pt-2 flex items-center justify-between text-sm">
        <span className="font-semibold">Total</span>
        <span className="font-mono font-bold text-success">${stepTotal.toFixed(4)}</span>
      </div>
    </div>
  );
}
