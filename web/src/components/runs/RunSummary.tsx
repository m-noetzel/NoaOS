import type { Run, RunEvent } from "@/api/types";
import { Target, CheckCircle2, AlertCircle, Loader2, Clock } from "lucide-react";
import { RunStatusBadge } from "@/components/badges/RunStatusBadge";

const statusIcons: Record<string, { icon: React.ReactNode; color: string }> = {
  completed: { icon: <CheckCircle2 className="h-4 w-4" />, color: "text-success" },
  failed: { icon: <AlertCircle className="h-4 w-4" />, color: "text-destructive" },
  running: { icon: <Loader2 className="h-4 w-4 animate-spin" />, color: "text-warning" },
};

export function RunSummary({ run, events }: { run: Run; events: RunEvent[] }) {
  const messageEvent = events.find((e) => e.type === "message_received");
  const resultEvent = events.find((e) => e.type === "result_ready");
  const goal = (messageEvent?.data.message as string) || (messageEvent?.data.text as string) || "—";
  const result = run.summary || (resultEvent?.data.response as string)?.slice(0, 120) || (resultEvent?.data.response_text as string)?.slice(0, 120) || "—";
  const cfg = statusIcons[run.status] || statusIcons.completed;

  return (
    <div className="rounded-xl border border-border/40 glass p-4 space-y-3">
      <div className="space-y-3">
        <div className="flex items-start gap-2.5">
          <Target className="h-4 w-4 text-primary mt-0.5 shrink-0" />
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-0.5">Goal</p>
            <p className="text-sm text-foreground">{goal}</p>
          </div>
        </div>
        <div className="flex items-start gap-2.5">
          <span className={cfg.color + " mt-0.5 shrink-0"}>{cfg.icon}</span>
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-0.5">Result</p>
            <p className="text-sm text-foreground">{result}</p>
          </div>
        </div>
      </div>

      {/* Status history */}
      {run.status_history && run.status_history.length > 0 && (
        <div className="border-t border-border/30 pt-3 space-y-1.5">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold flex items-center gap-1">
            <Clock className="h-3 w-3" /> Status History
          </p>
          <div className="space-y-1">
            {run.status_history.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-[10px] font-mono text-muted-foreground/60 w-16 shrink-0 text-right">
                  {new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
                <RunStatusBadge status={t.status} />
                {t.reason && (
                  <span className="text-[10px] text-muted-foreground/60 truncate">{t.reason}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
