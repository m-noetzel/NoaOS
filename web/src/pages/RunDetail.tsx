import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { Run, RunEvent, Artifact } from "@/api/types";
import { RunStatusBadge } from "@/components/badges/RunStatusBadge";
import { RiskTierBadge } from "@/components/badges/RiskTierBadge";
import { PrivacyModeBadge } from "@/components/badges/PrivacyModeBadge";
import { EventTimeline } from "@/components/shared/EventTimeline";
import { RunGraph } from "@/components/runs/RunGraph";
import { RawEventLog } from "@/components/runs/RawEventLog";
import { RunSummary } from "@/components/runs/RunSummary";
import { CostBreakdown } from "@/components/runs/CostBreakdown";
import { ReplayActions } from "@/components/runs/ReplayActions";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ArrowLeft, Clock, Cpu, DollarSign, Zap, Hash, Wrench, RotateCcw, Activity } from "lucide-react";

export default function RunDetail() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [selectedNodeLabel, setSelectedNodeLabel] = useState<string | null>(null);

  const { data: runRes } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => apiRequest<Run>(`/api/v1/runs/${runId}`),
    enabled: !!runId,
  });

  const { data: eventsRes } = useQuery({
    queryKey: ["runEvents", runId],
    queryFn: async (): Promise<import("@/api/types").ApiResponse<RunEvent[]>> => {
      const res = await apiRequest<{ events: RunEvent[] }>(`/api/v1/runs/${runId}/events/replay`);
      return { ...res, data: res.data?.events ?? [] };
    },
    enabled: !!runId,
  });

  const { data: artifactsRes } = useQuery({
    queryKey: ["runArtifacts", runId],
    queryFn: () => apiRequest<Artifact[]>(`/api/v1/runs/${runId}/artifacts`),
    enabled: !!runId,
  });

  const run = runRes?.data;
  const events = eventsRes?.data || [];
  const artifacts = artifactsRes?.data || [];

  if (!run) {
    return <div className="p-6 text-muted-foreground">Loading run…</div>;
  }

  // Compute canonical cost from steps if available, otherwise use run total
  const stepCostTotal = run.steps?.reduce((s, st) => s + st.cost, 0);
  const canonicalCost = stepCostTotal ?? run.cost_usd;
  const totalTokens = run.tokens_in + run.tokens_out;
  const durationSec = run.duration_ms ? (run.duration_ms / 1000).toFixed(1) : "—";
  const toolCalls = events.filter((e) => e.type === "tool_called" || e.type === "tool_result" || e.type === "approval_requested").length;

  const metrics = [
    { icon: <Cpu className="h-3.5 w-3.5 text-primary" />, label: "Model", value: run.model, sub: run.provider },
    { icon: <Zap className="h-3.5 w-3.5 text-warning" />, label: "Tokens", value: totalTokens.toLocaleString(), sub: `${run.tokens_in.toLocaleString()} in / ${run.tokens_out.toLocaleString()} out` },
    { icon: <DollarSign className="h-3.5 w-3.5 text-success" />, label: "Cost", value: `$${canonicalCost.toFixed(4)}`, sub: "estimated" },
    { icon: <Clock className="h-3.5 w-3.5 text-info" />, label: "Duration", value: `${durationSec}s`, sub: `${run.duration_ms ? run.duration_ms.toLocaleString() : 0}ms` },
    { icon: <Hash className="h-3.5 w-3.5 text-muted-foreground" />, label: "Events", value: String(events.length), sub: "total steps" },
    { icon: <Wrench className="h-3.5 w-3.5 text-warning" />, label: "Tool Calls", value: String(toolCalls), sub: "invocations" },
  ];

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/runs")} className="rounded-lg">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold truncate">Run {run.id}</h1>
            <RunStatusBadge status={run.status} />
          </div>
          <p className="text-xs text-muted-foreground font-mono">
            {new Date(run.created_at).toLocaleString()}
          </p>
        </div>
        <ReplayActions runId={run.id} selectedNodeLabel={selectedNodeLabel} />
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 text-xs"
          onClick={() => navigate(`/traces?traceId=${run.id}`)}
        >
          <Activity className="h-3.5 w-3.5" />
          View Trace
        </Button>
      </div>

      {/* Replay provenance */}
      {run.replay_of && (
        <div className="flex items-center gap-2 rounded-lg bg-info/10 border border-info/30 p-2.5 text-xs text-info">
          <RotateCcw className="h-3.5 w-3.5 shrink-0" />
          <span>
            Replayed from{" "}
            <button
              className="font-mono underline hover:text-info/80"
              onClick={() => navigate(`/runs/${run.replay_of!.original_run_id}`)}
            >
              {run.replay_of.original_run_id}
            </button>
            {run.replay_of.from_node && <span> · node: {run.replay_of.from_node}</span>}
            <span> · mode: {run.replay_of.mode}</span>
          </span>
        </div>
      )}

      {/* Status badges */}
      <div className="flex flex-wrap gap-2">
        <RiskTierBadge tier={run.risk_tier} />
        <PrivacyModeBadge mode={run.privacy_mode} />
      </div>

      {/* Summary + Cost side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RunSummary run={run} events={events} />
        <CostBreakdown events={events} run={run} />
      </div>

      {/* Performance metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {metrics.map((item) => (
          <Card key={item.label} className="glass">
            <CardContent className="pt-3 pb-3">
              <div className="flex items-center gap-1.5 mb-1">
                {item.icon}
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{item.label}</p>
              </div>
              <p className="text-sm font-mono font-semibold">{item.value}</p>
              {item.sub && <p className="text-[10px] text-muted-foreground">{item.sub}</p>}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="graph" className="space-y-4">
        <TabsList className="bg-muted/50">
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="graph">Execution Graph</TabsTrigger>
          <TabsTrigger value="raw">Raw Events</TabsTrigger>
          {artifacts.length > 0 && <TabsTrigger value="artifacts">Artifacts ({artifacts.length})</TabsTrigger>}
        </TabsList>

        <TabsContent value="timeline">
          <Card className="glass">
            <CardHeader className="pb-0">
              <CardTitle className="text-sm">Event Timeline</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <EventTimeline events={events} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="graph">
          <Card className="glass">
            <CardHeader className="pb-0">
              <CardTitle className="text-sm">Execution Graph</CardTitle>
              <p className="text-xs text-muted-foreground">Click nodes to inspect tokens, cost, latency, and replay options</p>
            </CardHeader>
            <CardContent className="p-0">
              <RunGraph events={events} runId={run.id} onSelectNode={setSelectedNodeLabel} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="raw">
          <Card className="glass">
            <CardHeader className="pb-0">
              <CardTitle className="text-sm">Raw Events</CardTitle>
              <p className="text-xs text-muted-foreground">Click events to expand metadata</p>
            </CardHeader>
            <CardContent className="p-0">
              <RawEventLog events={events} />
            </CardContent>
          </Card>
        </TabsContent>

        {artifacts.length > 0 && (
          <TabsContent value="artifacts">
            <Card className="glass">
              <CardHeader>
                <CardTitle className="text-sm">Artifacts</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {artifacts.map((art) => (
                    <div key={art.id} className="flex items-center justify-between rounded-lg border border-border/30 p-3 bg-muted/20">
                      <div>
                        <p className="text-sm font-medium">{art.name}</p>
                        <p className="text-xs text-muted-foreground font-mono">{art.type}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
