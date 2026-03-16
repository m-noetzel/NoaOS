import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { ToolScope } from "@/api/types";

interface ToolFunction {
  name: string;
  description: string;
  risk_tier: string;
  enabled: boolean;
}

interface ToolHealth {
  status: string;
  last_checked: string | null;
  error?: string;
}

interface ToolCredentials {
  configured: boolean;
  masked_value: string | null;
}

interface Tool {
  name: string;
  capability: string;
  risk_tier: string;
  enabled: boolean;
  description?: string;
  domain?: string;
  health?: ToolHealth;
  credentials?: ToolCredentials;
  functions?: ToolFunction[];
}

// UX-M8: Filter modes
type FilterMode = "all" | "usable";

export default function Tools() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [expandedTool, setExpandedTool] = useState<string | null>(null);
  // UX-M8: All vs Usable toggle
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  // UX-M9: Search/filter input
  const [searchQuery, setSearchQuery] = useState("");
  // UX-M10: Scope settings panel
  const [showScopes, setShowScopes] = useState(false);

  const { data: toolsRes, isLoading, isError, error } = useQuery({
    queryKey: ["tools"],
    queryFn: () => apiRequest<Tool[]>("/api/v1/tools"),
  });

  // UX-M10: Load scope data
  const { data: scopesRes } = useQuery({
    queryKey: ["tool-scopes"],
    queryFn: () => apiRequest<ToolScope[]>("/api/v1/tools/scopes"),
    enabled: showScopes,
  });

  const allTools = toolsRes?.data || [];

  // UX-M8: Filter by usability (healthy + configured credentials)
  const visibleTools = allTools
    .filter((tool) => {
      if (filterMode === "usable") {
        const isHealthy = tool.health?.status === "healthy";
        const hasCredentials = tool.credentials?.configured !== false;
        return isHealthy && hasCredentials;
      }
      return true;
    })
    // UX-M9: Search filter (name or description, case-insensitive)
    .filter((tool) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        tool.name.toLowerCase().includes(q) ||
        (tool.description || "").toLowerCase().includes(q)
      );
    });

  const toggleToolMutation = useMutation({
    mutationFn: async ({ name, enabled }: { name: string; enabled: boolean }) => {
      if (enabled) {
        return apiRequest(`/api/v1/tools/${name}/enable`, { method: "POST" });
      } else {
        return apiRequest(`/api/v1/tools/${name}`, { method: "DELETE" });
      }
    },
    onSuccess: (_data, { name, enabled }) => {
      queryClient.invalidateQueries({ queryKey: ["tools"] });
      toast({ title: `${name} ${enabled ? "enabled" : "disabled"}` });
    },
    onError: (err: Error, { name }) => {
      toast({ title: `Failed to toggle ${name}`, description: err.message, variant: "destructive" });
    },
  });

  const toggleFunctionMutation = useMutation({
    mutationFn: async ({ toolName, functionName, enabled }: { toolName: string; functionName: string; enabled: boolean }) => {
      if (enabled) {
        return apiRequest(`/api/v1/tools/${toolName}/${functionName}/enable`, { method: "POST" });
      } else {
        return apiRequest(`/api/v1/tools/${toolName}/${functionName}`, { method: "DELETE" });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tools"] });
    },
    onError: (err: Error) => {
      toast({ title: "Failed to toggle function", description: err.message, variant: "destructive" });
    },
  });

  const healthCheckMutation = useMutation({
    mutationFn: async (toolName: string) => {
      return apiRequest<{ status: string; error?: string | null }>(`/api/v1/tools/${toolName}/health`, { method: "POST" });
    },
    onSuccess: (result, toolName) => {
      const health = result?.data;
      if (health) {
        const msg = health.status === "healthy"
          ? `${toolName}: connected`
          : `${toolName}: ${health.error || "unhealthy"}`;
        toast({
          title: health.status === "healthy" ? "Connection OK" : "Connection Failed",
          description: msg,
          variant: health.status === "healthy" ? "default" : "destructive",
        });
      }
      queryClient.invalidateQueries({ queryKey: ["tools"] });
    },
    onError: (err: Error) => {
      toast({ title: "Health check failed", description: err.message, variant: "destructive" });
    },
  });

  // UX-M10: Update scope tool list
  const updateScopeMutation = useMutation({
    mutationFn: async ({ scope, tools }: { scope: string; tools: string[] }) => {
      return apiRequest(`/api/v1/tools/scopes/${scope}`, {
        method: "PATCH",
        body: JSON.stringify({ tools }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tool-scopes"] });
      toast({ title: "Scope updated" });
    },
    onError: (err: Error) => {
      toast({ title: "Failed to update scope", description: err.message, variant: "destructive" });
    },
  });

  const handleToolToggle = (name: string, currentEnabled: boolean) => {
    toggleToolMutation.mutate({ name, enabled: !currentEnabled });
  };

  const handleFunctionToggle = (toolName: string, functionName: string, currentEnabled: boolean) => {
    toggleFunctionMutation.mutate({ toolName, functionName, enabled: !currentEnabled });
  };

  const handleHealthCheck = (toolName: string) => {
    healthCheckMutation.mutate(toolName);
  };

  const handleCardClick = (toolName: string) => {
    setExpandedTool(expandedTool === toolName ? null : toolName);
  };

  if (isError) {
    return (
      <div className="p-6 space-y-4">
        <div>
          <h1 className="text-lg font-semibold">Tools</h1>
          <p className="text-sm text-muted-foreground">Registered tool capabilities</p>
        </div>
        <p className="text-sm text-destructive">Failed to load tools{error instanceof Error ? `: ${error.message}` : ""}</p>
      </div>
    );
  }

  const scopes = scopesRes?.data || [];

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Tools</h1>
        <p className="text-sm text-muted-foreground">Registered tool capabilities</p>
      </div>

      {/* UX-M8 + UX-M9: Filter bar */}
      <div className="flex items-center gap-3">
        {/* UX-M9: Search input */}
        <Input
          data-testid="tools-search"
          placeholder="Search tools..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-xs h-8 text-sm"
        />

        {/* UX-M8: All / Usable toggle */}
        <div className="flex items-center gap-1 rounded-lg border p-1">
          <button
            data-testid="filter-all"
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              filterMode === "all"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setFilterMode("all")}
          >
            All Tools
          </button>
          <button
            data-testid="filter-usable"
            className={`px-3 py-1 text-xs rounded-md transition-colors ${
              filterMode === "usable"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setFilterMode("usable")}
          >
            Usable Only
          </button>
        </div>

        {/* UX-M10: Scope settings toggle */}
        <Button
          variant="outline"
          size="sm"
          className="ml-auto h-8 text-xs"
          onClick={() => setShowScopes(!showScopes)}
          data-testid="scopes-toggle"
        >
          {showScopes ? "Hide" : "Show"} Scope Settings
        </Button>
      </div>

      {/* UX-M10: Tool scope settings panel */}
      {showScopes && (
        <div className="rounded-lg border p-4 space-y-4" data-testid="scopes-panel">
          <h2 className="text-sm font-semibold">Tool Scopes</h2>
          <p className="text-xs text-muted-foreground">
            Control which tools are available in each task context.
            Changes take effect on the next task run.
          </p>
          {scopes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Loading scopes...</p>
          ) : (
            <div className="space-y-4">
              {scopes.map((scope) => (
                <div key={scope.name} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium capitalize">{scope.name.replace("_", " ")}</span>
                    {scope.is_custom && (
                      <Badge variant="outline" className="text-xs">Custom</Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {scope.tools.map((tool) => (
                      <div
                        key={tool}
                        className="flex items-center gap-1 rounded-md border bg-muted/50 px-2 py-1"
                      >
                        <span className="text-xs font-mono">{tool}</span>
                        <button
                          className="text-muted-foreground hover:text-destructive text-xs ml-1"
                          onClick={() => {
                            const newTools = scope.tools.filter((t) => t !== tool);
                            updateScopeMutation.mutate({ scope: scope.name, tools: newTools });
                          }}
                          aria-label={`Remove ${tool} from ${scope.name}`}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : visibleTools.length === 0 ? (
        <p className="text-sm text-muted-foreground" data-testid="tools-empty">
          {allTools.length === 0
            ? "No tools registered"
            : filterMode === "usable"
              ? "No usable tools found. Configure credentials and run a health check to enable tools."
              : "No tools match your search."}
        </p>
      ) : (
        <div className="space-y-3">
          {visibleTools.map((tool) => {
            const isExpanded = expandedTool === tool.name;
            const healthStatus = tool.health?.status || "unknown";

            return (
              <div
                key={tool.name}
                data-tool-card
                className="rounded-lg border border-border/50 overflow-hidden"
              >
                {/* Header row */}
                <div
                  data-tool-header
                  className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/50"
                  onClick={() => handleCardClick(tool.name)}
                >
                  <div className="flex items-center gap-3">
                    {/* Status dot */}
                    <span
                      className={`inline-block h-3 w-3 rounded-full ${
                        healthStatus === "healthy"
                          ? "bg-green-500"
                          : healthStatus === "unhealthy"
                            ? "bg-red-500"
                            : "bg-gray-400"
                      }`}
                      aria-label={`Status: ${healthStatus}`}
                    />
                    <span className="font-mono text-sm font-medium">{tool.name}</span>
                    <Badge variant="outline">{tool.domain || "unknown"}</Badge>
                  </div>
                  <div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
                    <Switch
                      checked={tool.enabled}
                      onCheckedChange={() => handleToolToggle(tool.name, tool.enabled)}
                      disabled={toggleToolMutation.isPending}
                    />
                  </div>
                </div>

                {/* Expanded section */}
                {isExpanded && (
                  <div className="border-t p-4 space-y-4">
                    {/* Health section */}
                    <div className="space-y-2">
                      <h3 className="text-sm font-medium">Health</h3>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-sm ${
                            healthStatus === "healthy"
                              ? "text-green-600"
                              : healthStatus === "unhealthy"
                                ? "text-red-600"
                                : "text-gray-500"
                          }`}
                        >
                          {healthStatus === "healthy"
                            ? "Healthy"
                            : healthStatus === "unhealthy"
                              ? "Unhealthy"
                              : "Unconfigured"}
                        </span>
                        {tool.health?.last_checked && (
                          <span className="text-xs text-muted-foreground">
                            Last checked: {new Date(tool.health.last_checked).toLocaleString()}
                          </span>
                        )}
                      </div>
                      {tool.health?.error && (
                        <p className="text-sm text-red-600">{tool.health.error}</p>
                      )}
                      <button
                        onClick={() => handleHealthCheck(tool.name)}
                        className="text-sm px-3 py-1 rounded border hover:bg-muted"
                        disabled={healthCheckMutation.isPending}
                      >
                        {healthCheckMutation.isPending ? "Checking..." : "Test Connection"}
                      </button>
                    </div>

                    {/* Credentials section — read-only status, keys via Keychain */}
                    <div className="space-y-2">
                      <h3 className="text-sm font-medium">Credentials</h3>
                      {tool.credentials?.configured ? (
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-muted-foreground">{tool.credentials.masked_value}</span>
                          <span className="text-xs text-green-600">via Keychain</span>
                        </div>
                      ) : (
                        <div className="text-sm text-muted-foreground">
                          Not configured — set via <code className="text-xs">keychain_store.sh</code>
                        </div>
                      )}
                    </div>

                    {/* Functions table — L10: per-function enable/disable */}
                    {tool.functions && tool.functions.length > 0 && (
                      <div className="space-y-2">
                        <h3 className="text-sm font-medium">Functions</h3>
                        <div className="space-y-1">
                          {tool.functions.map((fn) => (
                            <div
                              key={fn.name}
                              data-function-row
                              className="flex items-center justify-between py-2 px-3 rounded hover:bg-muted/50"
                            >
                              <div className="flex items-center gap-3">
                                <span className="text-sm font-mono">{fn.name}</span>
                                <span className="text-xs text-muted-foreground">{fn.description}</span>
                                <Badge
                                  variant="outline"
                                  className={
                                    fn.risk_tier === "high"
                                      ? "border-red-500 text-red-600"
                                      : fn.risk_tier === "medium"
                                        ? "border-yellow-500 text-yellow-600"
                                        : "border-green-500 text-green-600"
                                  }
                                >
                                  {fn.risk_tier}
                                </Badge>
                              </div>
                              <Switch
                                checked={fn.enabled}
                                onCheckedChange={() =>
                                  handleFunctionToggle(tool.name, fn.name, fn.enabled)
                                }
                                disabled={toggleFunctionMutation.isPending}
                                aria-label={`${fn.enabled ? "Disable" : "Enable"} ${fn.name}`}
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
