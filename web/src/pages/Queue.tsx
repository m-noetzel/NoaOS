import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { QueueItem } from "@/api/types";
import { PrivacyModeBadge } from "@/components/badges/PrivacyModeBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useNavigate } from "react-router-dom";
import { Eye, X } from "lucide-react";

export default function Queue() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: queueRes, isLoading } = useQuery({
    queryKey: ["queue"],
    queryFn: () => apiRequest<QueueItem[]>("/api/v1/queue"),
  });

  const cancelMutation = useMutation({
    mutationFn: (taskId: string) =>
      apiRequest<void>(`/api/v1/tasks/${taskId}/cancel`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
  });

  const items = queueRes?.data || [];
  const active = items.filter((i) => i.status === "active");
  const queued = items.filter((i) => i.status === "queued");

  const Section = ({ title, items }: { title: string; items: QueueItem[] }) => (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-muted-foreground">{title} ({items.length})</h2>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">Empty</p>
      ) : (
        items.map((item) => (
          <Card key={item.id}>
            <CardContent className="pt-3 pb-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge variant="outline" className="text-xs font-mono">
                  #{item.position}
                </Badge>
                <div>
                  <p className="text-sm font-mono">{item.run_id}</p>
                  {item.estimated_wait > 0 && (
                    <p className="text-xs text-muted-foreground">~{item.estimated_wait}s wait</p>
                  )}
                </div>
                <PrivacyModeBadge mode={item.privacy_mode} />
              </div>
              <div className="flex gap-1">
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => navigate(`/runs/${item.run_id}`)}>
                  <Eye className="h-3.5 w-3.5" />
                </Button>
                {item.status === "queued" && (
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => cancelMutation.mutate(item.id)}>
                    <X className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Queue</h1>
        <p className="text-sm text-muted-foreground">Active and queued runs</p>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : active.length === 0 && queued.length === 0 ? (
        <div className="rounded-lg border border-border/50 glass p-12 text-center">
          <p className="text-sm font-medium">No active tasks</p>
          <p className="text-xs text-muted-foreground mt-1">
            The queue is empty. Running conversations will appear here.
          </p>
        </div>
      ) : (
        <>
          <Section title="Active" items={active} />
          <Section title="Queued" items={queued} />
        </>
      )}
    </div>
  );
}
