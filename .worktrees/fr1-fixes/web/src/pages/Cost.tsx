import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { CostRecord, CostSummary } from "@/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ["hsl(225, 60%, 55%)", "hsl(142, 60%, 40%)", "hsl(38, 80%, 50%)", "hsl(0, 72%, 51%)"];
const PAGE_LIMIT = 20;

export default function Cost() {
  const [offset, setOffset] = useState(0);

  const { data: summaryRes, isLoading: summaryLoading } = useQuery({
    queryKey: ["costSummary"],
    queryFn: () => apiRequest<CostSummary[]>("/api/v1/cost/summary"),
  });

  const { data: recordsRes, isLoading: recordsLoading } = useQuery({
    queryKey: ["costRecords", offset],
    queryFn: () => apiRequest<CostRecord[]>(`/api/v1/cost/records?limit=${PAGE_LIMIT}&offset=${offset}`),
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

  if (summaries.length === 0 && records.length === 0) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-lg font-semibold">Cost Dashboard</h1>
          <p className="text-sm text-muted-foreground">Token usage and cost tracking</p>
        </div>
        <p className="text-sm text-muted-foreground">No cost data</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Cost Dashboard</h1>
        <p className="text-sm text-muted-foreground">Token usage and cost tracking</p>
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
              {s.budget_limit_usd && (
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

        {/* By provider */}
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
      </div>
    </div>
  );
}
