import { useState } from "react";
import { apiRequest } from "@/api/client";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { SSEEventType } from "@/api/types";
import type { Message } from "@/api/types";
import type { PendingApproval } from "@/hooks/useChatSSE";

interface ApprovalCardProps {
  pendingApproval: PendingApproval;
  activeThreadRef: React.MutableRefObject<string | null>;
  onApproved: (optimisticMsg: Message) => void;
  onDenied: () => void;
  onSetStreaming: (value: boolean) => void;
  onAddStreamEvent: (event: { event: SSEEventType; data: Record<string, unknown> }) => void;
  onInvalidateQueries: () => void;
}

export function ApprovalCard({
  pendingApproval,
  activeThreadRef,
  onApproved,
  onDenied,
  onSetStreaming,
  onAddStreamEvent,
  onInvalidateQueries,
}: ApprovalCardProps) {
  const { toast } = useToast();
  const [isProcessing, setIsProcessing] = useState(false);

  const handleApprove = async () => {
    if (isProcessing) return;
    const aid = pendingApproval.approval_id;
    const toolLabel = `${pendingApproval.tool}.${pendingApproval.function}`;

    if (!aid) {
      toast({
        title: "Approval error",
        description: "No approval ID — please dismiss and try again.",
        variant: "destructive",
      });
      return;
    }

    setIsProcessing(true);
    onSetStreaming(true);
    onAddStreamEvent({
      event: "step_started" as SSEEventType,
      data: { step: `Executing ${toolLabel} (approved)` },
    });

    try {
      const res = await apiRequest<{
        approval_id: string;
        decision: string;
        tool_result?: Record<string, unknown>;
      }>(`/api/v1/approvals/${aid}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision: "approved" }),
      });
      const toolResult = res.data?.tool_result;
      onAddStreamEvent({
        event: "tool_end" as SSEEventType,
        data: {
          tool_name: toolLabel,
          result: toolResult ?? { status: "executed" },
        },
      });
      const resultSummary = toolResult?.error
        ? `Tool execution failed: ${toolResult.error}`
        : `${toolLabel} executed successfully.`;
      onApproved({
        id: `optimistic-approval-${Date.now()}`,
        thread_id: activeThreadRef.current || "",
        role: "assistant",
        content: resultSummary,
        created_at: new Date().toISOString(),
      });
      onInvalidateQueries();
      toast({ title: "Approved & Executed", description: resultSummary });
    } catch (err) {
      toast({
        title: "Execution failed",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
      setIsProcessing(false);
    }
    onSetStreaming(false);
  };

  const handleDeny = async () => {
    const aid = pendingApproval.approval_id;
    onDenied();
    if (aid) {
      try {
        await apiRequest(`/api/v1/approvals/${aid}/decide`, {
          method: "POST",
          body: JSON.stringify({ decision: "denied" }),
        });
        onInvalidateQueries();
      } catch { /* ignore */ }
    }
    toast({ title: "Denied", description: "Action was denied" });
  };

  return (
    <div className="animate-fade-in mx-auto max-w-md">
      <div className="rounded-xl border-2 border-amber-500/50 bg-amber-500/10 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-amber-500 text-lg">&#9888;</span>
          <span className="font-semibold text-sm">Approval Required</span>
          <span className="ml-auto text-[10px] uppercase tracking-wider font-medium text-amber-600 bg-amber-500/20 px-2 py-0.5 rounded-full">
            {pendingApproval.risk_tier} risk
          </span>
        </div>
        <div className="text-sm text-muted-foreground">
          Noa wants to execute{" "}
          <span className="font-mono font-medium text-foreground">
            {pendingApproval.tool}.{pendingApproval.function}
          </span>
        </div>
        {Object.keys(pendingApproval.args).length > 0 && (
          <div className="text-xs bg-background/50 rounded-lg p-2 space-y-0.5 font-mono max-h-32 overflow-y-auto">
            {Object.entries(pendingApproval.args).map(([k, v]) => (
              <div key={k}>
                <span className="text-muted-foreground">{k}:</span>{" "}
                <span className="text-foreground">
                  {typeof v === "string" ? v : JSON.stringify(v)}
                </span>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            className="flex-1 bg-green-600 hover:bg-green-700 text-white"
            onClick={handleApprove}
            disabled={isProcessing}
          >
            {isProcessing ? "Executing…" : "Approve"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1 border-destructive/50 text-destructive hover:bg-destructive/10"
            onClick={handleDeny}
            disabled={isProcessing}
          >
            Deny
          </Button>
        </div>
      </div>
    </div>
  );
}
