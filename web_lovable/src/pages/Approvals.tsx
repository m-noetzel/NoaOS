import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { Approval, ApprovalDecision } from "@/api/types";
import { ApprovalCard } from "@/components/shared/ApprovalCard";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Check, X } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export default function Approvals() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data: approvalsRes, isLoading } = useQuery({
    queryKey: ["approvals"],
    queryFn: () => apiRequest<Approval[]>("/api/v1/approvals/pending"),
  });

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approved" | "denied" }) =>
      apiRequest<{ success: boolean }>(`/api/v1/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision } satisfies ApprovalDecision),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      toast({ title: "Decision recorded" });
    },
  });

  const approvals = approvalsRes?.data || [];

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
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
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
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : approvals.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No pending approvals</p>
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
  );
}
