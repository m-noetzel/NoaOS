import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { Approval, ApprovalDecision } from "@/api/types";
import { ApprovalCard } from "@/components/shared/ApprovalCard";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Check, X, Clock, CheckCircle2, XCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export default function Approvals() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data: approvalsRes, isLoading } = useQuery({
    queryKey: ["approvals"],
    queryFn: () => apiRequest<Approval[]>("/api/v1/approvals/pending"),
  });

  const { data: historyRes } = useQuery({
    queryKey: ["approvals-history"],
    queryFn: () => apiRequest<Approval[]>("/api/v1/approvals/history"),
  });

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approved" | "denied" }) =>
      apiRequest<{ success: boolean }>(`/api/v1/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision } satisfies ApprovalDecision),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["approvals-history"] });
      toast({ title: "Decision recorded" });
    },
  });

  const approvals = approvalsRes?.data || [];
  const history = historyRes?.data || [];

  const handleBatch = (decision: "approved" | "denied") => {
    selected.forEach((id) => decideMutation.mutate({ id, decision }));
    setSelected(new Set());
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Pending section */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-lg font-semibold">Approvals</h1>
            <p className="text-sm text-muted-foreground">
              {approvals.length} pending {approvals.length === 1 ? "approval" : "approvals"}
            </p>
          </div>
          {selected.size > 0 && (
            <div className="flex gap-2">
              <Button size="sm" onClick={() => handleBatch("approved")} className="gap-1">
                <Check className="h-3.5 w-3.5" /> Approve {selected.size}
              </Button>
              <Button size="sm" variant="outline" onClick={() => handleBatch("denied")} className="gap-1">
                <X className="h-3.5 w-3.5" /> Deny {selected.size}
              </Button>
            </div>
          )}
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : approvals.length === 0 ? (
          <div className="flex items-center gap-2 py-4 px-3 rounded-lg border border-border/50 bg-muted/30">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No pending approvals</p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {approvals.map((approval) => (
              <div key={approval.id} className="relative">
                <label className="absolute top-3 left-3 z-10">
                  <input
                    type="checkbox"
                    checked={selected.has(approval.id)}
                    onChange={() => toggleSelect(approval.id)}
                    className="rounded border-border"
                  />
                </label>
                <div className="pl-6">
                  <ApprovalCard
                    approval={approval}
                    onDecide={(id, decision) => decideMutation.mutate({ id, decision })}
                    disabled={decideMutation.isPending}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* History section */}
      {history.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-widest mb-3">
            History
          </h2>
          <div className="space-y-2">
            {history.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-3 py-2 px-3 rounded-lg border border-border/50 bg-muted/20"
              >
                {item.status === "approved" ? (
                  <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0" />
                ) : (
                  <XCircle className="h-4 w-4 text-destructive flex-shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-medium">
                    {item.tool_name || "Unknown tool"}
                  </span>
                  <span className="text-xs text-muted-foreground ml-2">
                    {item.risk_tier}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground capitalize">
                  {item.status}
                </span>
                {item.decided_at && (
                  <span className="text-[10px] text-muted-foreground/60">
                    {new Date(item.decided_at).toLocaleString()}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
