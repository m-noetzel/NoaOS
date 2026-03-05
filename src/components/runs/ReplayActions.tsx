import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { RotateCcw, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import type { ReplayMode } from "@/api/types";

interface ReplayActionsProps {
  runId: string;
  selectedNodeLabel?: string | null;
}

function replayLabel(mode: ReplayMode): string {
  switch (mode) {
    case "full": return "Full replay";
    case "downstream": return "Replay downstream";
    case "tool_only": return "Replay tool only";
  }
}

export function ReplayActions({ runId }: ReplayActionsProps) {
  const handleReplay = (mode: ReplayMode, fromNode?: string) => {
    const label = fromNode ? `${replayLabel(mode)} from "${fromNode}"` : replayLabel(mode);
    toast.info(`${label} queued`, {
      description: `POST /runs/${runId}/replay${fromNode ? `?from_node=${fromNode}&mode=${mode}` : `?mode=${mode}`}`,
    });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5 border-border/50">
          <RotateCcw className="h-3 w-3" />
          Replay
          <ChevronDown className="h-3 w-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuItem onClick={() => handleReplay("full")} className="text-xs gap-2">
          <RotateCcw className="h-3 w-3" /> Replay full run
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// Replay from a specific node — used inside the inspection panel
export function NodeReplayActions({ runId, nodeId, nodeLabel }: { runId: string; nodeId: string; nodeLabel: string }) {
  const handleReplay = (mode: ReplayMode) => {
    toast.info(`${replayLabel(mode)} from "${nodeLabel}" queued`, {
      description: `POST /runs/${runId}/replay?from_node=${nodeId}&mode=${mode}`,
    });
  };

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Replay</p>
      <div className="flex flex-wrap gap-1.5">
        <Button
          variant="outline" size="sm"
          className="h-6 text-[11px] gap-1 border-warning/30 text-warning hover:bg-warning/10"
          onClick={() => handleReplay("tool_only")}
        >
          <RotateCcw className="h-2.5 w-2.5" /> Tool only
        </Button>
        <Button
          variant="outline" size="sm"
          className="h-6 text-[11px] gap-1 border-info/30 text-info hover:bg-info/10"
          onClick={() => handleReplay("downstream")}
        >
          <RotateCcw className="h-2.5 w-2.5" /> Downstream
        </Button>
        <Button
          variant="outline" size="sm"
          className="h-6 text-[11px] gap-1 border-border/50 text-muted-foreground hover:bg-muted/50"
          onClick={() => handleReplay("full")}
        >
          <RotateCcw className="h-2.5 w-2.5" /> Full run
        </Button>
      </div>
    </div>
  );
}
