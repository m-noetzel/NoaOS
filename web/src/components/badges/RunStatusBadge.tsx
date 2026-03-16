import type { RunStatus } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Loader2, Clock, ShieldAlert } from "lucide-react";

const statusConfig: Record<string, { label: string; className: string; icon?: React.ReactNode }> = {
  queued: { label: "Queued", className: "bg-muted text-muted-foreground", icon: <Clock className="h-3 w-3" /> },
  pending: { label: "Pending", className: "bg-muted text-muted-foreground", icon: <Clock className="h-3 w-3" /> },
  running: { label: "Running", className: "bg-info/15 text-info border-info/30", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  waiting_for_approval: { label: "Awaiting Approval", className: "bg-warning/15 text-warning border-warning/30", icon: <ShieldAlert className="h-3 w-3" /> },
  awaiting_approval: { label: "Awaiting Approval", className: "bg-warning/15 text-warning border-warning/30", icon: <ShieldAlert className="h-3 w-3" /> },
  completed: { label: "Completed", className: "bg-success/15 text-success border-success/30" },
  failed: { label: "Failed", className: "bg-destructive/15 text-destructive border-destructive/30" },
  cancelled: { label: "Cancelled", className: "bg-muted text-muted-foreground" },
};

const fallbackConfig = { label: "Unknown", className: "bg-muted text-muted-foreground" };

export function RunStatusBadge({ status }: { status: RunStatus | string }) {
  const config = statusConfig[status] || fallbackConfig;
  return (
    <Badge variant="outline" className={cn("text-xs font-medium gap-1", config.className)}>
      {config.icon}
      {config.label}
    </Badge>
  );
}
