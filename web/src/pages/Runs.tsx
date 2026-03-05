import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { Run } from "@/api/types";
import { RunStatusBadge } from "@/components/badges/RunStatusBadge";
import { RiskTierBadge } from "@/components/badges/RiskTierBadge";
import { PrivacyModeBadge } from "@/components/badges/PrivacyModeBadge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useNavigate } from "react-router-dom";
import { Clock, Zap } from "lucide-react";

export default function Runs() {
  const navigate = useNavigate();
  const { data: runsRes, isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: () => apiRequest<Run[]>("/api/v1/runs"),
  });

  const runs = runsRes?.data || [];

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Runs</h1>
        <p className="text-sm text-muted-foreground">Execution history across all threads</p>
      </div>

      <div className="rounded-lg border border-border/50 glass overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[150px]">Created</TableHead>
              <TableHead>Summary</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Risk</TableHead>
              <TableHead>Model</TableHead>
              <TableHead className="text-right">
                <span className="inline-flex items-center gap-1"><Zap className="h-3 w-3" /> Tokens</span>
              </TableHead>
              <TableHead className="text-right">Cost</TableHead>
              <TableHead className="text-right">
                <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" /> Duration</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">Loading…</TableCell>
              </TableRow>
            ) : runs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground py-8">No runs found</TableCell>
              </TableRow>
            ) : (
              runs.map((run) => (
                <TableRow
                  key={run.id}
                  className="cursor-pointer hover:bg-accent/30 transition-colors"
                  onClick={() => navigate(`/runs/${run.id}`)}
                >
                  <TableCell className="text-xs font-mono text-muted-foreground">
                    {new Date(run.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </TableCell>
                  <TableCell className="text-sm max-w-[250px] truncate">{run.summary}</TableCell>
                  <TableCell><RunStatusBadge status={run.status} /></TableCell>
                  <TableCell><RiskTierBadge tier={run.risk_tier} /></TableCell>
                  <TableCell>
                    <div>
                      <span className="text-xs font-mono">{run.model}</span>
                      <span className="text-[10px] text-muted-foreground ml-1">({run.provider})</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-xs font-mono">
                    {(run.tokens_in + run.tokens_out).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right text-xs font-mono">
                    ${run.cost_usd.toFixed(4)}
                  </TableCell>
                  <TableCell className="text-right text-xs font-mono text-muted-foreground">
                    {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
