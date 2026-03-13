import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { apiRequest } from "@/api/client";
import type { UserSettings, PrivacyMode } from "@/api/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

// ---------------------------------------------------------------------------
// GoogleAuthSection — GO2
// ---------------------------------------------------------------------------

interface GoogleStatus {
  connected: boolean;
  scopes: string[];
}

function GoogleAuthSection() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isConnecting, setIsConnecting] = useState(false);

  const { data: statusRes, isLoading: statusLoading } = useQuery({
    queryKey: ["google-status"],
    queryFn: () => apiRequest<GoogleStatus>("/api/v1/auth/google/status"),
  });

  const status = statusRes?.data;

  const disconnectMutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/v1/auth/google/disconnect", { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["google-status"] });
      toast({ title: "Google account disconnected" });
    },
    onError: (err: Error) => {
      toast({
        title: "Failed to disconnect",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  const handleConnect = useCallback(async () => {
    setIsConnecting(true);
    try {
      const res = await apiRequest<{ auth_url: string }>(
        "/api/v1/auth/google/authorize",
      );
      const authUrl = res.data?.auth_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        toast({
          title: "Failed to start Google OAuth",
          description: "No auth URL returned",
          variant: "destructive",
        });
        setIsConnecting(false);
      }
    } catch (err) {
      toast({
        title: "Failed to start Google OAuth",
        description: err instanceof Error ? err.message : "Unknown error",
        variant: "destructive",
      });
      setIsConnecting(false);
    }
  }, [toast]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Google Account</CardTitle>
        <CardDescription>
          Connect your Google account to enable Calendar and Gmail tools
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {statusLoading ? (
          <p className="text-sm text-muted-foreground">Checking status…</p>
        ) : status?.connected ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span
                className="inline-block h-2 w-2 rounded-full bg-green-500"
                aria-label="connected"
              />
              <span className="text-sm font-medium">Connected</span>
            </div>
            {status.scopes.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Scopes: {status.scopes.join(", ")}
              </p>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => disconnectMutation.mutate()}
              disabled={disconnectMutation.isPending}
            >
              {disconnectMutation.isPending ? "Disconnecting…" : "Disconnect"}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span
                className="inline-block h-2 w-2 rounded-full bg-muted-foreground"
                aria-label="not connected"
              />
              <span className="text-sm text-muted-foreground">Not connected</span>
            </div>
            <Button
              size="sm"
              onClick={handleConnect}
              disabled={isConnecting}
            >
              {isConnecting ? "Connecting…" : "Connect Google"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// UX-H3: System Prompt section with its own Save button
// ---------------------------------------------------------------------------

interface SystemPromptResponse {
  content: string;
  is_default: boolean;
}

function SystemPromptSection() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);

  const { data: spRes, isLoading } = useQuery({
    queryKey: ["system-prompt"],
    queryFn: () => apiRequest<SystemPromptResponse>("/api/v1/settings/system-prompt"),
  });

  const currentContent = spRes?.data?.content ?? "";
  const isDefault = spRes?.data?.is_default ?? true;
  const value = draft ?? currentContent;

  // Sync draft when query data arrives (only if no local edits yet)
  useEffect(() => {
    if (draft === null && spRes?.data) {
      setDraft(spRes.data.content);
    }
  }, [spRes, draft]);

  const saveMutation = useMutation({
    mutationFn: (content: string) =>
      apiRequest("/api/v1/settings/system-prompt", {
        method: "PUT",
        body: JSON.stringify({ content }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system-prompt"] });
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast({ title: "System prompt saved" });
    },
    onError: (err: Error) => {
      toast({ title: "Failed to save system prompt", description: err.message, variant: "destructive" });
    },
  });

  const isDirty = draft !== null && draft !== currentContent;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">System Prompt</CardTitle>
        <CardDescription>
          Customize how Noa responds. {isDefault && !isDirty && <span className="text-muted-foreground/60">(Using default)</span>}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <>
            <Textarea
              value={value}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Enter a system prompt…"
              className="min-h-[100px] text-sm font-mono resize-y"
              rows={4}
              data-testid="system-prompt-textarea"
            />
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={() => saveMutation.mutate(draft ?? "")}
                disabled={saveMutation.isPending || !isDirty}
                data-testid="system-prompt-save"
              >
                {saveMutation.isPending ? "Saving…" : isDirty ? "Save System Prompt *" : "Save System Prompt"}
              </Button>
              {isDirty && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setDraft(currentContent)}
                >
                  Reset
                </Button>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

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
  const [searchParams, setSearchParams] = useSearchParams();

  // Refresh Google status if returning from OAuth callback
  useEffect(() => {
    if (searchParams.get("google") === "connected") {
      queryClient.invalidateQueries({ queryKey: ["google-status"] });
      // Clean up the query param without a navigation
      const next = new URLSearchParams(searchParams);
      next.delete("google");
      setSearchParams(next, { replace: true });
      toast({ title: "Google account connected" });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const { data: settingsRes } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<UserSettings>("/api/v1/settings"),
  });

  const settings = settingsRes?.data;

  const [model, setModel] = useState("");
  const [provider, setProvider] = useState("");
  const [privacy, setPrivacy] = useState<PrivacyMode>("external");
  const [dailyBudget, setDailyBudget] = useState("10");
  const [monthlyBudget, setMonthlyBudget] = useState("200");
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const [ollamaUrl, setOllamaUrl] = useState("http://private-worker:11434");
  const [initialized, setInitialized] = useState(false);
  // FE-M5: Track unsaved changes to warn before navigation
  const [isDirty, setIsDirty] = useState(false);
  const savedRef = useRef(false);

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
      setPrivacy(settings.default_privacy_mode || "external");
      setDailyBudget(String(settings.budget_daily_usd || 10));
      setMonthlyBudget(String(settings.budget_monthly_usd || 200));
      setOllamaUrl(settings.ollama_base_url || "http://private-worker:11434");
      setInitialized(true);
      setIsDirty(false);
    }
  }, [settings]);

  // FE-M5: Warn on browser unload if there are unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty && !savedRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  // FE-M5: Mark form as dirty on any field change
  const markDirty = () => { setIsDirty(true); savedRef.current = false; };

  // When provider changes, reset model to first valid model for that provider (UI-H2)
  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider);
    markDirty();
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
      savedRef.current = true;
      setIsDirty(false);
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
            <Select value={model} onValueChange={(v) => { setModel(v); markDirty(); }}>
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
            <Select value={privacy} onValueChange={(v) => { setPrivacy(v as PrivacyMode); markDirty(); }}>
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
            <Input id="daily-budget" type="number" min="0" step="0.01" value={dailyBudget} onChange={(e) => { setDailyBudget(e.target.value); markDirty(); }} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="monthly-budget" className="text-xs">Monthly Budget (USD)</Label>
            <Input id="monthly-budget" type="number" min="0" step="0.01" value={monthlyBudget} onChange={(e) => { setMonthlyBudget(e.target.value); markDirty(); }} />
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
              onChange={(e) => { setOllamaUrl(e.target.value); markDirty(); }}
            />
          </div>
        </CardContent>
      </Card>

      {/* UX-H3: System prompt with dedicated Save button */}
      <SystemPromptSection />

      <GoogleAuthSection />

      <Button onClick={handleSave}>
        {isDirty ? "Save Settings *" : "Save Settings"}
      </Button>
    </div>
  );
}
