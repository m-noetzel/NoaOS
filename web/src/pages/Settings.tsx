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

/** Models grouped by provider (UI-H2) */
export const PROVIDER_MODELS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
    { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
  ],
  openai: [
    { value: "gpt-4.1", label: "GPT-4.1" },
    { value: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
    { value: "gpt-4o", label: "GPT-4o" },
  ],
  google_ai: [
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  ],
  ollama: [
    { value: "llama-3.1-70b", label: "Llama 3.1 70B (Local)" },
  ],
};

export default function Settings() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: settingsRes } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<UserSettings>("/api/v1/settings"),
  });

  const settings = settingsRes?.data;

  const [model, setModel] = useState("");
  const [provider, setProvider] = useState("");
  const [privacy, setPrivacy] = useState<PrivacyMode>("private");
  const [dailyBudget, setDailyBudget] = useState("10");
  const [monthlyBudget, setMonthlyBudget] = useState("200");
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const [ollamaUrl, setOllamaUrl] = useState("http://private-worker:11434");
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (settings) {
      const newProvider = settings.default_provider || "anthropic";
      const newModel = settings.default_model;
      setProvider(newProvider);
      // Validate that the model belongs to the provider
      const models = PROVIDER_MODELS[newProvider];
      if (models && models.some((m) => m.value === newModel)) {
        setModel(newModel);
      } else if (models && models.length > 0) {
        setModel(models[0].value);
      }
      setPrivacy(settings.default_privacy_mode || "private");
      setDailyBudget(String(settings.budget_daily_usd || 10));
      setMonthlyBudget(String(settings.budget_monthly_usd || 200));
      setOllamaUrl(settings.ollama_base_url || "http://private-worker:11434");
      setInitialized(true);
    }
  }, [settings]);

  // When provider changes, reset model to first valid model for that provider (UI-H2)
  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    const models = PROVIDER_MODELS[newProvider];
    if (models && models.length > 0) {
      const currentModelValid = models.some((m) => m.value === model);
      if (!currentModelValid) {
        setModel(models[0].value);
      }
    }
  };

  // Budget validation (UI-H3)
  const validateBudgets = (): boolean => {
    const daily = parseFloat(dailyBudget);
    const monthly = parseFloat(monthlyBudget);

    if (isNaN(daily) || isNaN(monthly)) {
      setBudgetError("Budget values must be valid numbers");
      return false;
    }
    if (daily < 0 || monthly < 0) {
      setBudgetError("Budget values must not be negative");
      return false;
    }
    if (daily > monthly) {
      setBudgetError("Daily budget must not exceed monthly budget");
      return false;
    }
    setBudgetError(null);
    return true;
  };

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

  const handleSave = () => {
    if (!validateBudgets()) return;
    saveMutation.mutate();
  };

  const availableModels = PROVIDER_MODELS[provider] || [];

  if (!initialized) {
    return (
      <div className="p-6 space-y-6 max-w-xl">
        <div>
          <h1 className="text-lg font-semibold">Settings</h1>
          <p className="text-sm text-muted-foreground">Loading settings...</p>
        </div>
      </div>
    );
  }

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
            <Select value={provider} onValueChange={handleProviderChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="anthropic">Anthropic</SelectItem>
                <SelectItem value="openai">OpenAI</SelectItem>
                <SelectItem value="google_ai">Google AI</SelectItem>
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
                {availableModels.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
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
            <Label htmlFor="daily-budget" className="text-xs">Daily Budget (USD)</Label>
            <Input id="daily-budget" type="number" min="0" step="0.01" value={dailyBudget} onChange={(e) => setDailyBudget(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="monthly-budget" className="text-xs">Monthly Budget (USD)</Label>
            <Input id="monthly-budget" type="number" min="0" step="0.01" value={monthlyBudget} onChange={(e) => setMonthlyBudget(e.target.value)} />
          </div>
          {budgetError && (
            <p className="text-sm text-destructive">{budgetError}</p>
          )}
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

      <Button onClick={handleSave}>Save Settings</Button>
    </div>
  );
}
