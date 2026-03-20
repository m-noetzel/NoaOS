import { useState } from "react";
import type { RunEvent } from "@/api/types";
import { ToolCallChip } from "./ToolCallChip";
import { cn, asString, asRecord } from "@/lib/utils";
import { MessageSquare, Brain, Wrench, ClipboardCheck, Shield, CheckCircle2, XCircle, Package, Timer, ChevronRight, ChevronDown } from "lucide-react";

const eventIcons: Record<string, React.ReactNode> = {
  message_received: <MessageSquare className="h-3.5 w-3.5" />,
  planner_step: <Brain className="h-3.5 w-3.5" />,
  token_stream: <MessageSquare className="h-3.5 w-3.5" />,
  tool_called: <Wrench className="h-3.5 w-3.5" />,
  tool_result: <ClipboardCheck className="h-3.5 w-3.5" />,
  approval_requested: <Shield className="h-3.5 w-3.5" />,
  result_ready: <CheckCircle2 className="h-3.5 w-3.5" />,
  error: <XCircle className="h-3.5 w-3.5" />,
  artifact_created: <Package className="h-3.5 w-3.5" />,
};

const eventColors: Record<string, string> = {
  message_received: "text-primary",
  planner_step: "text-info",
  token_stream: "text-muted-foreground",
  tool_called: "text-warning",
  tool_result: "text-success",
  approval_requested: "text-destructive",
  result_ready: "text-success",
  error: "text-destructive",
  artifact_created: "text-primary",
};

function formatDuration(startTime: string, endTime: string): string {
  const ms = new Date(endTime).getTime() - new Date(startTime).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** UX-H5: Expandable detail section for tool call input/output */
function ExpandableData({ label, data }: { label: string; data: unknown }) {
  const [open, setOpen] = useState(false);
  if (data === undefined || data === null) return null;
  const formatted = typeof data === "object" ? JSON.stringify(data, null, 2) : String(data);
  const isLong = formatted.length > 120;

  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] text-muted-foreground/70 hover:text-muted-foreground transition-colors"
      >
        {open ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
        {label}
      </button>
      {open && (
        <div className="mt-1 ml-3 rounded-lg bg-muted/40 border border-border/30 p-2 font-mono text-[10px] text-foreground/80 overflow-auto max-h-48">
          {isLong || typeof data === "object"
            ? <pre className="whitespace-pre-wrap break-all">{formatted}</pre>
            : <span>{formatted}</span>
          }
        </div>
      )}
    </div>
  );
}

function TimelineRow({ event, isLast, duration }: { event: RunEvent; isLast: boolean; duration: string | null }) {
  const stepDuration = event.data.duration_ms as number | undefined;

  return (
    <div
      className={cn(
        "flex gap-3 px-4 py-2.5 border-l-2 ml-3 transition-colors hover:bg-muted/30",
        isLast ? "border-primary" : "border-border/60"
      )}
    >
      <span className={cn("shrink-0 mt-0.5", eventColors[event.type] || "text-muted-foreground")}>
        {eventIcons[event.type] || <MessageSquare className="h-3.5 w-3.5" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-mono font-medium text-foreground">{event.type}</span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
          {duration && (
            <span className="text-[10px] text-muted-foreground/50 font-mono">+{duration}</span>
          )}
          {stepDuration !== undefined && (
            <span className="inline-flex items-center gap-0.5 rounded-full bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
              <Timer className="h-2.5 w-2.5" />
              {stepDuration < 1000 ? `${stepDuration}ms` : `${(stepDuration / 1000).toFixed(1)}s`}
            </span>
          )}
        </div>

        {event.type === "planner_step" && (
          <p className="text-sm text-muted-foreground mt-0.5">
            {asString(event.data.step)}
            {event.data.description && (
              <span className="text-muted-foreground/60"> — {asString(event.data.description)}</span>
            )}
          </p>
        )}

        {event.type === "tool_called" && (
          <div className="mt-1 space-y-1">
            <div className="flex items-center gap-2">
              <ToolCallChip
                toolName={asString(event.data.tool_name) || asString(asRecord(event.data.tool_call).name)}
                args={asRecord(event.data.args) || asRecord(asRecord(event.data.tool_call).args)}
              />
              {event.data.parallel_group && (
                <span className="rounded-full bg-warning/10 text-warning/70 px-1.5 py-0.5 text-[9px] font-mono border border-warning/20">
                  ∥ {asString(event.data.parallel_group)}
                </span>
              )}
            </div>
            {/* UX-H5: Full tool input expandable — args may be top-level or nested in tool_call */}
            <ExpandableData label="Input" data={event.data.args ?? asRecord(event.data.tool_call)?.args} />
          </div>
        )}

        {event.type === "tool_result" && (
          <div className="mt-0.5 space-y-0.5">
            <div className="text-xs text-muted-foreground flex items-center gap-2">
              {event.data.tool_name && (
                <span className="font-mono text-warning/80">{asString(event.data.tool_name)}</span>
              )}
            </div>
            {/* UX-H5: result may be top-level, nested in tool_result, or fallback to full data */}
            <ExpandableData label="Output" data={event.data.result ?? asRecord(event.data.tool_result) ?? event.data.output} />
          </div>
        )}

        {event.type === "result_ready" && (
          <p className="text-sm text-muted-foreground mt-1 truncate">
            {/* CRITICAL 2: backend emits "response", fallback to "response_text" for compat */}
            {asString(event.data.response ?? event.data.response_text).slice(0, 120)}…
          </p>
        )}

        {event.type === "error" && (
          <p className="text-sm text-destructive mt-1">{asString(event.data.error ?? event.data.message)}</p>
        )}

        {event.type === "message_received" && (
          <p className="text-sm text-muted-foreground mt-0.5 truncate">{asString(event.data.message ?? event.data.text)}</p>
        )}
      </div>
    </div>
  );
}

export function EventTimeline({ events }: { events: RunEvent[] }) {
  if (!events.length) {
    return <p className="text-sm text-muted-foreground p-4">No events yet.</p>;
  }

  return (
    <div className="space-y-0">
      {events.map((event, i) => {
        const nextEvent = events[i + 1];
        const duration = nextEvent ? formatDuration(event.created_at, nextEvent.created_at) : null;
        return (
          <TimelineRow key={event.id} event={event} isLast={i === events.length - 1} duration={duration} />
        );
      })}
    </div>
  );
}
