import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "@/api/client";
import type { CostRecord, CostSummary } from "@/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ["hsl(225, 60%, 55%)", "hsl(142, 60%, 40%)", "hsl(38, 80%, 50%)", "hsl(0, 72%, 51%)"];
const PAGE_LIMIT = 20;

type TimeRange = "today" | "week" | "month" | "all";

function getTimeRangeStart(range: TimeRange): string | null {
  if (range === "all") return null;
  const now = new Date();
  let start: Date;
  if (range === "today") {
    start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  } else if (range === "week") {
    const day = now.getDay();
    const diff = day === 0 ? 6 : day - 1; // Monday as week start
    start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - diff);
  } else {
    start = new Date(now.getFullYear(), now.getMonth(), 1);
  }
  return start.toISOString();
}

export default function Cost() {
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [timeRange, setTimeRange] = useState<TimeRange>("month");

  const { data: summaryRes, isLoading: summaryLoading } = useQuery({
    queryKey: ["costSummary"],
    queryFn: () => apiRequest<CostSummary[]>("/api/v1/cost/summary"),
  });

  const since = getTimeRangeStart(timeRange);
  const recordsUrl = since
    ? `/api/v1/cost/records?limit=${PAGE_LIMIT}&offset=${offset}&since=${encodeURIComponent(since)}`
    : `/api/v1/cost/records?limit=${PAGE_LIMIT}&offset=${offset}`;

  const { data: recordsRes, isLoading: recordsLoading } = useQuery({
    queryKey: ["costRecords", offset, timeRange],
    queryFn: () => apiRequest<CostRecord[]>(recordsUrl),
  });

  const isLoading = summaryLoading || recordsLoading;
  const summaries = summaryRes?.data || [];
  const records = recordsRes?.data || [];

  // Group costs by provider
  const byProvider = records.reduce<Record<string, number>>((acc, r) => {
    acc[r.provider] = (acc[r.provider] || 0) + r.cost_usd;
    return acc;
  }, {});

  const pieData = Object.entries(byProvider).map(([name, value]) => ({ name, value: +value.toFixed(4) }));

  // Group by model for bar chart
  const byModel = records.reduce<Record<string, { tokens: number; cost: number }>>((acc, r) => {
    if (!acc[r.model]) acc[r.model] = { tokens: 0, cost: 0 };
    acc[r.model].tokens += r.tokens_in + r.tokens_out;
    acc[r.model].cost += r.cost_usd;
    return acc;
  }, {});

  const barData = Object.entries(byModel).map(([model, data]) => ({ model, ...data }));

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-lg font-semibold">Cost Dashboard</h1>
          <p className="text-sm text-muted-foreground">Token usage and cost tracking</p>
        </div>
        <div className="space-y-4">
          <div className="animate-pulse h-24 bg-muted rounded-lg" role="status" />
          <div className="animate-pulse h-24 bg-muted rounded-lg" />
          <div className="animate-pulse h-24 bg-muted rounded-lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Cost Dashboard</h1>
          <p className="text-sm text-muted-foreground">Token usage and cost tracking</p>
        </div>
        <Select value={timeRange} onValueChange={(v) => { setTimeRange(v as TimeRange); setOffset(0); }}>
          <SelectTrigger className="w-[140px] h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="today">Today</SelectItem>
            <SelectItem value="week">This Week</SelectItem>
            <SelectItem value="month">This Month</SelectItem>
            <SelectItem value="all">All Time</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {summaries.map((s) => (
          <Card key={s.period}>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground uppercase tracking-wider">
                {s.period}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-2xl font-semibold font-mono">${s.cost_usd.toFixed(2)}</p>
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span>In: {s.tokens_in.toLocaleString()}</span>
                <span>Out: {s.tokens_out.toLocaleString()}</span>
              </div>
              {s.budget_limit_usd != null && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Budget</span>
                    <span className="font-mono">${s.budget_limit_usd.toFixed(2)}</span>
                  </div>
                  <Progress value={(s.cost_usd / s.budget_limit_usd) * 100} className="h-1.5" />
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By model */}
        {barData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Cost by Model</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={barData}>
                  <XAxis dataKey="model" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="cost" fill="hsl(225, 60%, 55%)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* By provider */}
        {pieData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Cost by Provider</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-center">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label>
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Cost Records table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Cost Records</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Date</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Tokens In</TableHead>
                <TableHead className="text-right">Tokens Out</TableHead>
                <TableHead className="text-right">Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    No cost data for this period
                  </TableCell>
                </TableRow>
              ) : (
                records.map((r) => (
                  <TableRow
                    key={r.run_id ?? r.created_at}
                    className={r.run_id ? "cursor-pointer hover:bg-accent/30 transition-colors" : ""}
                    onClick={r.run_id ? () => navigate(`/runs/${r.run_id}`) : undefined}
                    data-testid={r.run_id ? `cost-record-run-${r.run_id}` : undefined}
                  >
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {new Date(r.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </TableCell>
                    <TableCell className="text-xs">{r.provider}</TableCell>
                    <TableCell className="text-xs font-mono">{r.model}</TableCell>
                    <TableCell className="text-right text-xs font-mono">{r.tokens_in.toLocaleString()}</TableCell>
                    <TableCell className="text-right text-xs font-mono">{r.tokens_out.toLocaleString()}</TableCell>
                    <TableCell className="text-right text-xs font-mono">
                      {r.cost_usd === 0 ? "—" : `$${r.cost_usd.toFixed(4)}`}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          {/* Pagination */}
          {records.length > 0 && (
            <div className="flex justify-between items-center px-4 py-2 border-t text-xs text-muted-foreground">
              <button
                className="hover:text-foreground disabled:opacity-40"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_LIMIT))}
              >
                Previous
              </button>
              <span>Showing {offset + 1}–{offset + records.length}</span>
              <button
                className="hover:text-foreground disabled:opacity-40"
                disabled={records.length < PAGE_LIMIT}
                onClick={() => setOffset(offset + PAGE_LIMIT)}
              >
                Next
              </button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
