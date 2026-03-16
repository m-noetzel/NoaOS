import { useState } from "react";
import type { SSEEvent, RunStatus } from "@/api/types";
import { cn, asString, asRecord } from "@/lib/utils";
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, XCircle, Search, Brain, Wrench, FileText } from "lucide-react";
import { RunStatusBadge } from "@/components/badges/RunStatusBadge";

/** Maps raw SSE events into human-readable activity labels */
function activityLabel(event: SSEEvent): string | null {
  switch (event.event) {
    case "planner_step":
      return asString(event.data.step) || "Planning next step";
    // UX-H10: tool_start / tool_end lifecycle events
    case "tool_start": {
      const name = asString(event.data.tool_name) || asString(event.data.name) || "tool";
      return `Starting: ${name}`;
    }
    case "tool_end": {
      const name = asString(event.data.tool_name) || asString(event.data.name) || "tool";
      return `Finished: ${name}`;
    }
    // UX-H10: generic step events
    case "step": {
      const label = asString(event.data.label) || asString(event.data.step) || asString(event.data.name);
      return label ? `Step: ${label}` : "Executing step";
    }
    case "tool_called": {
      const tc = asRecord(event.data.tool_call);
      const name = asString(tc.name) || asString(event.data.tool_name) || "tool";
      return `Calling: ${name}`;
    }
    case "tool_result": {
      const tr = asRecord(event.data.tool_result);
      const name = asString(tr.name) || asString(event.data.tool_name) || "tool";
      return `Result from: ${name}`;
    }
    case "approval_requested":
      return `Approval needed: ${asString(event.data.tool)}.${asString(event.data.function)}`;
    case "classification_done": {
      const model = asString(event.data.model);
      return model ? `Using ${model}` : "Classified request";
    }
    case "step_started":
      return `Running ${asString(event.data.step) || "agent"}`;
    case "message_received":
      return "Processing message";
    case "result_ready":
      return "Finishing up";
    default:
      return null;
  }
}

function activityIcon(event: SSEEvent) {
  switch (event.event) {
    case "planner_step": {
      const step = asString(event.data.step).toLowerCase();
      if (step.includes("search")) return <Search className="h-3 w-3" />;
      if (step.includes("pars") || step.includes("read")) return <FileText className="h-3 w-3" />;
      return <Brain className="h-3 w-3" />;
    }
    case "tool_start":
    case "tool_called":
      return <Wrench className="h-3 w-3" />;
    case "tool_end":
    case "tool_result":
      return <CheckCircle2 className="h-3 w-3" />;
    case "step":
    case "step_started":
      return <Brain className="h-3 w-3" />;
    default:
      return <Brain className="h-3 w-3" />;
  }
}

interface ActivityStreamProps {
  events: SSEEvent[];
  isStreaming: boolean;
  runId?: string;
  runStatus?: RunStatus;
  runSummary?: string;
}

export function ActivityStream({ events, isStreaming, runId, runStatus, runSummary }: ActivityStreamProps) {
  const [collapsed, setCollapsed] = useState(false);

  const activities = events
    .map((e) => ({ label: activityLabel(e), icon: activityIcon(e), event: e }))
    .filter((a) => a.label !== null);

  if (activities.length === 0 && !isStreaming) return null;

  const latestActivity = activities[activities.length - 1];
  const isComplete = !isStreaming && runStatus && runStatus !== "running" && runStatus !== "pending";

  // Collapsed summary view (after completion, user manually collapsed)
  if (isComplete && collapsed) {
    return (
      <div className="flex items-start gap-3 animate-fade-in py-1">
        <div className="flex-shrink-0 h-6 w-6 rounded-lg bg-success/15 text-success flex items-center justify-center mt-0.5">
          <CheckCircle2 className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground">
              ✓ {runSummary || "Task completed"}
            </span>
          </div>
          <button
            onClick={() => setCollapsed(false)}
            className="flex items-center gap-1 text-[10px] text-muted-foreground/60 hover:text-muted-foreground mt-0.5 transition-colors"
          >
            <ChevronRight className="h-2.5 w-2.5" />
            Execution details
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in py-1">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5">
        {isStreaming ? (
          <Loader2 className="h-3 w-3 text-primary animate-spin" />
        ) : runStatus === "failed" ? (
          <XCircle className="h-3 w-3 text-destructive" />
        ) : (
          <CheckCircle2 className="h-3 w-3 text-success" />
        )}
        <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-widest">
          {isStreaming ? "Executing" : "Execution complete"}
        </span>
        {runStatus && <RunStatusBadge status={runStatus} />}
      </div>

      {/* Activity items */}
      <div className="ml-1.5 border-l border-border/50 space-y-0">
        {activities.map((activity, i) => {
          const isCurrent = isStreaming && i === activities.length - 1;
          return (
            <div
              key={i}
              className={cn(
                "flex items-center gap-2 pl-3 py-0.5 text-xs transition-all",
                isCurrent ? "text-foreground" : "text-muted-foreground/70"
              )}
            >
              <span className={cn(isCurrent && "text-primary animate-pulse")}>{activity.icon}</span>
              <span>{activity.label}</span>
              {isCurrent && isStreaming && (
                <span className="inline-block w-1 h-1 rounded-full bg-primary animate-pulse" />
              )}
            </div>
          );
        })}
      </div>

      {/* Collapse button when open after completion */}
      {isComplete && !collapsed && (
        <button
          onClick={() => setCollapsed(true)}
          className="flex items-center gap-1 text-[10px] text-muted-foreground/60 hover:text-muted-foreground mt-1 ml-1.5 transition-colors"
        >
          <ChevronDown className="h-2.5 w-2.5" />
          Collapse
        </button>
      )}
    </div>
  );
}
