import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Approval } from "@/api/types";
import { RiskTierBadge } from "@/components/badges/RiskTierBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Check, X, ChevronDown, ChevronUp, ExternalLink, Wrench } from "lucide-react";

interface ApprovalCardProps {
  approval: Approval;
  onDecide: (id: string, decision: "approved" | "denied") => void;
  disabled?: boolean;
}

export function ApprovalCard({ approval, onDecide, disabled }: ApprovalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  return (
    <Card>
      <CardContent className="pt-4 space-y-2">
        <div className="flex items-center justify-between">
          <RiskTierBadge tier={approval.risk_tier} />
          <button
            className="text-xs text-muted-foreground font-mono hover:text-primary hover:underline inline-flex items-center gap-1 transition-colors"
            onClick={() => navigate(`/runs/${approval.run_id}`)}
          >
            {approval.run_id}
            <ExternalLink className="h-2.5 w-2.5" />
          </button>
        </div>

        <p className="text-sm font-medium">{approval.preview_text}</p>

        {/* Tool info */}
        {approval.tool_name && (
          <div className="flex items-center gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-md bg-warning/10 text-warning border border-warning/20 px-2 py-0.5 text-[11px] font-mono">
              <Wrench className="h-2.5 w-2.5" />{approval.tool_name}
            </span>
            {approval.tool_args && !expanded && (
              <span className="text-[10px] text-muted-foreground/60 font-mono truncate max-w-[150px]">
                {JSON.stringify(approval.tool_args).slice(0, 40)}…
              </span>
            )}
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          {new Date(approval.created_at).toLocaleString()}
        </p>

        {/* Decided info */}
        {approval.decided_at && (
          <p className="text-[10px] text-muted-foreground/60">
            Decided {new Date(approval.decided_at).toLocaleString()}
            {approval.decided_by && <span> by {approval.decided_by}</span>}
          </p>
        )}

        {/* Expandable detail */}
        {approval.tool_args && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
          >
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {expanded ? "Hide details" : "Show details"}
          </button>
        )}

        {expanded && approval.tool_args && (
          <div className="rounded-lg bg-muted/30 p-3 space-y-1.5 animate-fade-in">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Tool Arguments</p>
            <pre className="text-[11px] font-mono text-foreground/80 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(approval.tool_args, null, 2)}
            </pre>
          </div>
        )}
      </CardContent>
      {approval.status === "pending" && (
        <CardFooter className="gap-2">
          <Button
            size="sm"
            onClick={() => onDecide(approval.id, "approved")}
            disabled={disabled}
            className="gap-1"
          >
            <Check className="h-3.5 w-3.5" /> Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onDecide(approval.id, "denied")}
            disabled={disabled}
            className="gap-1"
          >
            <X className="h-3.5 w-3.5" /> Deny
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}
