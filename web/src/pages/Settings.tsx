import { useState, useEffect } from "react";
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

  const [model, setModel] = useState(settings?.default_model || "claude-sonnet-4-20250514");
  const [provider, setProvider] = useState(settings?.default_provider || "anthropic");
  const [privacy, setPrivacy] = useState<PrivacyMode>(settings?.default_privacy_mode || "private");
  const [dailyBudget, setDailyBudget] = useState(String(settings?.budget_daily_usd || 10));
  const [monthlyBudget, setMonthlyBudget] = useState(String(settings?.budget_monthly_usd || 200));

  const [ollamaUrl, setOllamaUrl] = useState(settings?.ollama_base_url || "http://private-worker:11434");

  useEffect(() => {
    if (settings) {
      setModel(settings.default_model);
      setProvider(settings.default_provider || "anthropic");
      setPrivacy(settings.default_privacy_mode || "private");
      setDailyBudget(String(settings.budget_daily_usd || 10));
      setMonthlyBudget(String(settings.budget_monthly_usd || 200));
      setOllamaUrl(settings.ollama_base_url || "http://private-worker:11434");
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        default_model: model,
        default_provider: provider,
        default_privacy_mode: privacy,
        budget_daily_usd: parseFloat(dailyBudget),
        budget_monthly_usd: parseFloat(monthlyBudget),
        ollama_base_url: ollamaUrl,
      };
      return apiRequest<UserSettings>("/api/v1/settings", {
        method: "PUT",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast({ title: "Settings saved" });
    },
    onError: (err: Error) => {
      toast({ title: "Failed to save settings", description: err.message, variant: "destructive" });
    },
  });

  return (
    <div className="p-6 space-y-6 max-w-xl">
      <div>
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">Configure defaults, limits, and API credentials</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Defaults</CardTitle>
          <CardDescription>Default model, provider, and privacy mode for new chats</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs">Default Provider</Label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="anthropic">Anthropic</SelectItem>
                <SelectItem value="openai">OpenAI</SelectItem>
                <SelectItem value="google">Google AI</SelectItem>
                <SelectItem value="ollama">Ollama (Local)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Default Model</Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gpt-4.1">GPT-4.1</SelectItem>
                <SelectItem value="gpt-4.1-mini">GPT-4.1 Mini</SelectItem>
                <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                <SelectItem value="claude-sonnet-4-20250514">Claude Sonnet 4</SelectItem>
                <SelectItem value="claude-opus-4-6">Claude Opus 4.6</SelectItem>
                <SelectItem value="gemini-2.0-flash">Gemini 2.0 Flash</SelectItem>
                <SelectItem value="llama-3.1-70b">Llama 3.1 70B (Local)</SelectItem>
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

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">API Credentials</CardTitle>
          <CardDescription>
            API keys are managed via macOS Keychain. Use the terminal to update them:
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <code className="block text-xs bg-muted p-3 rounded-lg font-mono">
            ./tools/keychain_store.sh set ANTHROPIC_API_KEY "sk-ant-..."
          </code>
          <p className="text-xs text-muted-foreground">
            Keys are loaded at startup and never stored on disk or in the browser.
            Restart Noa after changing keys.
          </p>
          <div className="space-y-1.5">
            <Label className="text-xs">Ollama Base URL</Label>
            <Input
              placeholder="http://private-worker:11434"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Button onClick={() => saveMutation.mutate()}>Save Settings</Button>
    </div>
  );
}
