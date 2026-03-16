import { useState } from "react";
import type { SSEEvent } from "@/api/types";
import { cn, asString, asRecord } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";

interface ExecutionDetailsProps {
  events: SSEEvent[];
}

export function ExecutionDetails({ events }: ExecutionDetailsProps) {
  const [open, setOpen] = useState(false);

  const toolEvents = events.filter(
    (e) => e.event === "tool_called" || e.event === "tool_result"
  );

  if (toolEvents.length === 0) return null;

  // Pair tool_called with tool_result
  const toolPairs: Array<{
    name: string;
    args: Record<string, unknown>;
    result?: string;
    duration?: number;
    status: string;
  }> = [];

  for (const evt of toolEvents) {
    if (evt.event === "tool_called") {
      // Runner sends: payload.tool_call = {name, input/arguments, ...}
      const tc = asRecord(evt.data.tool_call);
      const name = asString(tc.name) || asString(evt.data.tool_name) || "unknown";
      const args = asRecord(tc.input || tc.arguments || evt.data.args);
      toolPairs.push({ name, args, status: "called" });
    } else if (evt.event === "tool_result") {
      // Runner sends: payload.tool_result = {name, result, ...}
      const tr = asRecord(evt.data.tool_result);
      const name = asString(tr.name) || asString(evt.data.tool_name) || "unknown";
      const existing = toolPairs.find(
        (p) => p.name === name && p.status === "called"
      );
      if (existing) {
        existing.result = typeof tr.result === "string"
          ? tr.result
          : JSON.stringify(tr.result ?? evt.data.result, null, 2);
        existing.duration = typeof tr.duration_ms === "number" ? tr.duration_ms
          : typeof evt.data.duration_ms === "number" ? evt.data.duration_ms : undefined;
        existing.status = "completed";
      }
    }
  }

  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] text-muted-foreground/70 hover:text-muted-foreground transition-colors"
      >
        {open ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
        Execution details
      </button>

      {open && (
        <div className="mt-1.5 ml-0.5 space-y-1.5 animate-fade-in">
          {toolPairs.map((tool, i) => (
            <div
              key={i}
              className="rounded-lg bg-muted/40 border border-border/30 px-3 py-2 text-xs space-y-1"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-medium text-foreground">
                  {tool.name}
                </span>
                <span className={cn(
                  "text-[10px] font-medium",
                  tool.status === "completed" ? "text-success" : "text-muted-foreground"
                )}>
                  {tool.status}
                </span>
              </div>
              {Object.keys(tool.args).length > 0 && (
                <div className="text-muted-foreground">
                  {Object.entries(tool.args).map(([k, v]) => (
                    <div key={k}>
                      <span className="text-muted-foreground/60">{k}:</span>{" "}
                      <span className="font-mono">{JSON.stringify(v)}</span>
                    </div>
                  ))}
                </div>
              )}
              {tool.result && (
                <div className="text-muted-foreground/80 whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
                  → {tool.result.length > 500 ? tool.result.slice(0, 500) + "…" : tool.result}
                </div>
              )}
              {tool.duration && (
                <div className="text-muted-foreground/60">
                  Duration: {(tool.duration / 1000).toFixed(1)}s
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
