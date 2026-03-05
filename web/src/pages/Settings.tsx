import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { UserSettings, PrivacyMode } from "@/api/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

export default function Settings() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: settingsRes } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<UserSettings>("/api/v1/settings"),
  });

  const settings = settingsRes?.data;

  const [model, setModel] = useState(settings?.default_model || "claude-3.5-sonnet");
  const [privacy, setPrivacy] = useState<PrivacyMode>(settings?.default_privacy_mode || "private");
  const [dailyBudget, setDailyBudget] = useState(String(settings?.budget_daily_usd || 5));
  const [monthlyBudget, setMonthlyBudget] = useState(String(settings?.budget_monthly_usd || 50));

  const saveMutation = useMutation({
    mutationFn: () =>
      apiRequest<UserSettings>("/api/v1/settings", {
        method: "PUT",
        body: JSON.stringify({
          default_model: model,
          default_privacy_mode: privacy,
          budget_daily_usd: parseFloat(dailyBudget),
          budget_monthly_usd: parseFloat(monthlyBudget),
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast({ title: "Settings saved" });
    },
    onError: (err: Error) => {
      toast({ title: "Failed to save settings", description: err.message, variant: "destructive" });
    },
  });

  const handleSave = () => {
    saveMutation.mutate();
  };

  return (
    <div className="p-6 space-y-6 max-w-xl">
      <div>
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">Configure defaults and limits</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Defaults</CardTitle>
          <CardDescription>Default model and privacy mode for new chats</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs">Default Model</Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="claude-3.5-sonnet">Claude 3.5 Sonnet</SelectItem>
                <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                <SelectItem value="llama-3.1-70b">Llama 3.1 70B</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Default Privacy Mode</Label>
            <Select value={privacy} onValueChange={(v) => setPrivacy(v as PrivacyMode)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="private">Private</SelectItem>
                <SelectItem value="external">External</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Budget Limits</CardTitle>
          <CardDescription>Set spending limits in USD</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs">Daily Budget (USD)</Label>
            <Input type="number" value={dailyBudget} onChange={(e) => setDailyBudget(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Monthly Budget (USD)</Label>
            <Input type="number" value={monthlyBudget} onChange={(e) => setMonthlyBudget(e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Button onClick={handleSave}>Save Settings</Button>
    </div>
  );
}
