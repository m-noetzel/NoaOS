import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import CredentialModal from "@/components/tools/CredentialModal";

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

export default function Tools() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [expandedTool, setExpandedTool] = useState<string | null>(null);
  const [credentialModal, setCredentialModal] = useState<string | null>(null);

  const { data: toolsRes, isLoading, isError } = useQuery({
    queryKey: ["tools"],
    queryFn: () => apiRequest<Tool[]>("/api/v1/tools"),
  });

  const tools = toolsRes?.data || [];

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
      return apiRequest(`/api/v1/tools/${toolName}/health`, { method: "POST" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tools"] });
    },
    onError: (err: Error) => {
      toast({ title: "Health check failed", description: err.message, variant: "destructive" });
    },
  });

  const saveCredentialMutation = useMutation({
    mutationFn: async ({ toolName, apiKey }: { toolName: string; apiKey: string }) => {
      return apiRequest(`/api/v1/tools/${toolName}/credentials`, {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tools"] });
      setCredentialModal(null);
      toast({ title: "Credentials saved" });
    },
    onError: (err: Error) => {
      toast({ title: "Failed to save credentials", description: err.message, variant: "destructive" });
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
        <p className="text-sm text-destructive">Failed to load tools</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Tools</h1>
        <p className="text-sm text-muted-foreground">Registered tool capabilities</p>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : tools.length === 0 ? (
        <p className="text-sm text-muted-foreground">No tools registered</p>
      ) : (
        <div className="space-y-3">
          {tools.map((tool) => {
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

                    {/* Credentials section */}
                    <div className="space-y-2">
                      <h3 className="text-sm font-medium">Credentials</h3>
                      {tool.credentials?.configured ? (
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono">{tool.credentials.masked_value}</span>
                          <button
                            onClick={() => setCredentialModal(tool.name)}
                            className="text-sm px-3 py-1 rounded border hover:bg-muted"
                          >
                            Configure
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-muted-foreground">No credentials found</span>
                          <button
                            onClick={() => setCredentialModal(tool.name)}
                            className="text-sm px-3 py-1 rounded border hover:bg-muted"
                          >
                            Add key
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Functions table */}
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

      {/* Credential Modal */}
      {credentialModal && (
        <CredentialModal
          toolName={credentialModal}
          open={true}
          onClose={() => setCredentialModal(null)}
          onSave={(apiKey) =>
            saveCredentialMutation.mutate({ toolName: credentialModal, apiKey })
          }
        />
      )}
    </div>
  );
}
