import { Shield, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { PrivacyMode, UserSettings } from "@/api/types";

export function PrivacyToggle() {
  const queryClient = useQueryClient();

  const { data: settingsRes } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiRequest<UserSettings>("/api/v1/settings"),
  });

  const mode: PrivacyMode = settingsRes?.data?.default_privacy_mode || "external";

  const toggleMutation = useMutation({
    mutationFn: (newMode: PrivacyMode) =>
      apiRequest("/api/v1/settings", {
        method: "PATCH",
        body: JSON.stringify({ default_privacy_mode: newMode }),
      }),
    onMutate: async (newMode) => {
      // Optimistic update so the icon flips immediately
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const prev = queryClient.getQueryData<{ data: UserSettings }>(["settings"]);
      queryClient.setQueryData(["settings"], (old: { data: UserSettings } | undefined) => {
        if (!old) return old;
        return { ...old, data: { ...old.data, default_privacy_mode: newMode } };
      });
      return { prev };
    },
    onError: (_err, _newMode, context) => {
      if (context?.prev) queryClient.setQueryData(["settings"], context.prev);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const handleToggle = () => {
    const newMode: PrivacyMode = mode === "private" ? "external" : "private";
    toggleMutation.mutate(newMode);
  };

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={handleToggle}
          disabled={toggleMutation.isPending}
        >
          {mode === "private" ? (
            <Shield className="h-4 w-4 text-success" />
          ) : (
            <Globe className="h-4 w-4 text-info" />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        {mode === "private" ? "Private mode" : "External mode"}
      </TooltipContent>
    </Tooltip>
  );
}
