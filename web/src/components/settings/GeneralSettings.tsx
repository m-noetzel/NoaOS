import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { UserSettings, PrivacyMode, PricingModel } from "@/api/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { PROVIDER_MODELS } from "./providerModels";

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
    queryFn: () =>
      apiRequest<SystemPromptResponse>("/api/v1/settings/system-prompt"),
  });

  const currentContent = spRes?.data?.content ?? "";
  const isDefault = spRes?.data?.is_default ?? true;
  const value = draft ?? currentContent;

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
      toast({
        title: "Failed to save system prompt",
        description: err.message,
        variant: "destructive",
      });
    },
  });

  const isDirty = draft !== null && draft !== currentContent;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">System Prompt</CardTitle>
        <CardDescription>
          Customize how Noa responds.{" "}
          {isDefault && !isDirty && (
            <span className="text-muted-foreground/60">(Using default)</span>
          )}
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
                {saveMutation.isPending
                  ? "Saving…"
                  : isDirty
                    ? "Save System Prompt *"
                    : "Save System Prompt"}
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

interface GeneralSettingsProps {
  settings: UserSettings | undefined;
  initialized: boolean;
  onSaved: () => void;
}

export function GeneralSettings({
  settings,
  initialized,
  onSaved,
}: GeneralSettingsProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: pricingRes } = useQuery({
    queryKey: ["pricing"],
    queryFn: () => apiRequest<PricingModel[]>("/api/v1/cost/pricing"),
  });
  const pricingData = pricingRes?.data || [];

  const [model, setModel] = useState("");
  const [provider, setProvider] = useState("");
  const [privacy, setPrivacy] = useState<PrivacyMode>("external");
  const [dailyBudget, setDailyBudget] = useState("10");
  const [monthlyBudget, setMonthlyBudget] = useState("200");
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const [ollamaUrl, setOllamaUrl] = useState("http://private-worker:11434");
  const [approvalsEnabled, setApprovalsEnabled] = useState(true);
  const [maxToolCalls, setMaxToolCalls] = useState("10");
  const [maxRetries, setMaxRetries] = useState("3");
  const [timeoutSeconds, setTimeoutSeconds] = useState("120");
  const [isDirty, setIsDirty] = useState(false);
  const savedRef = useRef(false);

  useEffect(() => {
    if (settings) {
      const newProvider = settings.default_provider || "openai";
      const newModel = settings.default_model;
      setProvider(newProvider);
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
      setApprovalsEnabled(settings.approvals_enabled ?? true);
      setMaxToolCalls(String(settings.max_tool_calls ?? 10));
      setMaxRetries(String(settings.max_retries ?? 3));
      setTimeoutSeconds(String(settings.timeout_seconds ?? 120));
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

  const markDirty = () => {
    setIsDirty(true);
    savedRef.current = false;
  };

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
        approvals_enabled: approvalsEnabled,
        max_tool_calls: parseInt(maxToolCalls, 10),
        max_retries: parseInt(maxRetries, 10),
        timeout_seconds: parseInt(timeoutSeconds, 10),
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
      onSaved();
      toast({ title: "Settings saved" });
    },
    onError: (err: Error) => {
      toast({
        title: "Failed to save settings",
        description: err.message,
        variant: "destructive",
      });
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
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Defaults</CardTitle>
          <CardDescription>
            Default model, provider, and privacy mode for new chats
          </CardDescription>
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
                <SelectItem value="kimi">Kimi (Moonshot AI)</SelectItem>
                <SelectItem value="ollama">Ollama (Local)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Default Model</Label>
            <Select
              value={model}
              onValueChange={(v) => {
                setModel(v);
                markDirty();
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {availableModels.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Default Privacy Mode</Label>
            <Select
              value={privacy}
              onValueChange={(v) => {
                setPrivacy(v as PrivacyMode);
                markDirty();
              }}
            >
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
            <Label htmlFor="daily-budget" className="text-xs">
              Daily Budget (USD)
            </Label>
            <Input
              id="daily-budget"
              type="number"
              min="0"
              step="0.01"
              value={dailyBudget}
              onChange={(e) => {
                setDailyBudget(e.target.value);
                markDirty();
              }}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="monthly-budget" className="text-xs">
              Monthly Budget (USD)
            </Label>
            <Input
              id="monthly-budget"
              type="number"
              min="0"
              step="0.01"
              value={monthlyBudget}
              onChange={(e) => {
                setMonthlyBudget(e.target.value);
                markDirty();
              }}
            />
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
            API keys are managed via macOS Keychain. Use the terminal to update
            them:
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <code className="block text-xs bg-muted p-3 rounded-lg font-mono">
            ./tools/keychain_store.sh set ANTHROPIC_API_KEY &quot;sk-ant-...&quot;
          </code>
          <code className="block text-xs bg-muted p-3 rounded-lg font-mono">
            ./tools/keychain_store.sh set KIMI_API_KEY &quot;sk-...&quot;
          </code>
          <p className="text-xs text-muted-foreground">
            Keys are loaded at startup and never stored on disk or in the
            browser. Restart Noa after changing keys.
          </p>
          <div className="space-y-1.5">
            <Label className="text-xs">Ollama Base URL</Label>
            <Input
              placeholder="http://private-worker:11434"
              value={ollamaUrl}
              onChange={(e) => {
                setOllamaUrl(e.target.value);
                markDirty();
              }}
            />
          </div>
        </CardContent>
      </Card>

      {/* UX-M2: Governance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Governance</CardTitle>
          <CardDescription>
            Control agent approval requirements
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-xs">Require Human Approval</Label>
              <p className="text-xs text-muted-foreground">
                When enabled, high-risk tool calls require your approval before
                executing.
              </p>
            </div>
            <Switch
              data-testid="approvals-toggle"
              checked={approvalsEnabled}
              onCheckedChange={(v) => {
                setApprovalsEnabled(v);
                markDirty();
              }}
            />
          </div>
        </CardContent>
      </Card>

      {/* UX-M4: Agent execution limits */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Agent Limits</CardTitle>
          <CardDescription>
            Control agent execution boundaries
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="max-tool-calls" className="text-xs">
              Max Tool Calls per Task
            </Label>
            <Input
              id="max-tool-calls"
              type="number"
              min="1"
              max="100"
              value={maxToolCalls}
              onChange={(e) => {
                setMaxToolCalls(e.target.value);
                markDirty();
              }}
              data-testid="max-tool-calls"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="max-retries" className="text-xs">
              Max Retries
            </Label>
            <Input
              id="max-retries"
              type="number"
              min="0"
              max="10"
              value={maxRetries}
              onChange={(e) => {
                setMaxRetries(e.target.value);
                markDirty();
              }}
              data-testid="max-retries"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="timeout-seconds" className="text-xs">
              Timeout (seconds)
            </Label>
            <Input
              id="timeout-seconds"
              type="number"
              min="10"
              max="3600"
              value={timeoutSeconds}
              onChange={(e) => {
                setTimeoutSeconds(e.target.value);
                markDirty();
              }}
              data-testid="timeout-seconds"
            />
          </div>
        </CardContent>
      </Card>

      {/* UX-H3: System prompt with dedicated Save button */}
      <SystemPromptSection />

      {/* UX-H8: Pricing reference table */}
      {pricingData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Model Pricing</CardTitle>
            <CardDescription>
              Read-only reference — prices per 1M tokens
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Provider</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">Input (per 1M)</TableHead>
                  <TableHead className="text-right">Output (per 1M)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pricingData.map((p, i) => (
                  <TableRow key={i} className="hover:bg-transparent">
                    <TableCell className="text-xs capitalize">
                      {p.provider}
                    </TableCell>
                    <TableCell className="text-xs font-mono">
                      {p.model}
                    </TableCell>
                    <TableCell className="text-right text-xs font-mono">
                      {p.input_price_per_m === 0
                        ? "Free"
                        : `$${p.input_price_per_m.toFixed(2)}`}
                    </TableCell>
                    <TableCell className="text-right text-xs font-mono">
                      {p.output_price_per_m === 0
                        ? "Free"
                        : `$${p.output_price_per_m.toFixed(2)}`}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Button onClick={handleSave}>
        {isDirty ? "Save Settings *" : "Save Settings"}
      </Button>
    </div>
  );
}
