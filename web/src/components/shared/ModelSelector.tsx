import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { UserSettings, Provider } from "@/api/types";
import { PROVIDER_MODELS } from "@/pages/Settings";

export function ModelSelector() {
  const queryClient = useQueryClient();
  const { data: settingsRes } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<UserSettings>("/api/v1/settings"),
  });

  const settings = settingsRes?.data;
  const provider = (settings?.default_provider || "openai") as Provider;
  const model = settings?.default_model || "";

  const availableModels = PROVIDER_MODELS[provider] || [];

  const updateModel = useMutation({
    mutationFn: (newModel: string) =>
      apiRequest("/api/v1/settings", {
        method: "PUT",
        body: JSON.stringify({ ...settings, default_model: newModel }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  const displayLabel = availableModels.find((m) => m.value === model)?.label || model || "Select model";

  return (
    <Select value={model} onValueChange={(v) => updateModel.mutate(v)}>
      <SelectTrigger className="h-8 w-[180px] text-xs rounded-lg bg-muted/40 border-border/40 hover:bg-accent/60 transition-colors">
        <SelectValue placeholder={displayLabel} />
      </SelectTrigger>
      <SelectContent className="glass-strong rounded-xl">
        {availableModels.map((m) => (
          <SelectItem key={m.value} value={m.value} className="text-xs rounded-lg">
            <span>{m.label}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
