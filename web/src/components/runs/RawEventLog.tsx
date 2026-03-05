import { useState } from "react";
import type { RunEvent } from "@/api/types";
import { cn } from "@/lib/utils";
import { ChevronRight, ChevronDown } from "lucide-react";

const typeColors: Record<string, string> = {
  message_received: "text-primary",
  planner_step: "text-info",
  tool_called: "text-warning",
  tool_result: "text-success",
  result_ready: "text-success",
  error: "text-destructive",
  approval_requested: "text-destructive",
  artifact_created: "text-primary",
  token_stream: "text-muted-foreground",
};

function EventRow({ event }: { event: RunEvent }) {
  const [expanded, setExpanded] = useState(false);
  const hasData = Object.keys(event.data).length > 0;

  return (
    <div className="px-4 py-3 hover:bg-muted/20 transition-colors font-mono text-xs space-y-1.5">
      {/* Header */}
      <button
        className="flex items-center gap-3 w-full text-left"
        onClick={() => hasData && setExpanded(!expanded)}
      >
        {hasData && (
          expanded
            ? <ChevronDown className="h-3 w-3 text-muted-foreground/50 shrink-0" />
            : <ChevronRight className="h-3 w-3 text-muted-foreground/50 shrink-0" />
        )}
        {!hasData && <span className="w-3 shrink-0" />}
        <span className={cn("font-semibold", typeColors[event.type] || "text-foreground")}>
          {event.type}
        </span>
        <span className="text-muted-foreground/50">
          {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
        {event.data.tool_name && (
          <span className="text-warning/70 text-[10px]">{event.data.tool_name as string}</span>
        )}
        {event.data.parallel_group && (
          <span className="rounded-full bg-warning/10 text-warning/70 px-1.5 py-0 text-[9px] border border-warning/20">
            {event.data.parallel_group as string}
          </span>
        )}
        {event.data.duration_ms && (
          <span className="text-muted-foreground/40 text-[10px]">
            {((event.data.duration_ms as number) / 1000).toFixed(1)}s
          </span>
        )}
        <span className="text-muted-foreground/30 ml-auto text-[10px]">{event.id}</span>
      </button>

      {/* Expandable data */}
      {expanded && (
        <div className="pl-6 space-y-0.5 animate-fade-in">
          {Object.entries(event.data).map(([key, value]) => (
            <div key={key} className="flex gap-2">
              <span className="text-muted-foreground/50 shrink-0">{key}:</span>
              <span className="text-foreground/70 break-all">
                {typeof value === "object"
                  ? <pre className="inline whitespace-pre-wrap">{JSON.stringify(value, null, 2)}</pre>
                  : String(value)
                }
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function RawEventLog({ events }: { events: RunEvent[] }) {
  if (!events.length) {
    return <p className="text-sm text-muted-foreground p-4">No events recorded.</p>;
  }

  return (
    <div className="divide-y divide-border/30">
      {events.map((event) => (
        <EventRow key={event.id} event={event} />
      ))}
    </div>
  );
}
