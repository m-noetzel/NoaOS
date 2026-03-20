import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import type { UserSettings } from "@/api/types";
import { useToast } from "@/hooks/use-toast";
import { GeneralSettings } from "@/components/settings/GeneralSettings";
import { GoogleSettings } from "@/components/settings/GoogleSettings";
import { IntelligenceSettings } from "@/components/settings/IntelligenceSettings";
import { PrivacySettings } from "@/components/settings/PrivacySettings";

// Re-export PROVIDER_MODELS so existing imports from @/pages/Settings still work
export { PROVIDER_MODELS } from "@/components/settings/providerModels";

export default function Settings() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  // Refresh Google status if returning from OAuth callback
  useEffect(() => {
    if (searchParams.get("google") === "connected") {
      queryClient.invalidateQueries({ queryKey: ["google-status"] });
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

  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (settings && !initialized) {
      setInitialized(true);
    }
  }, [settings, initialized]);

  return (
    <div className="p-6 space-y-6 max-w-xl">
      <div>
        <h1 className="text-lg font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Configure defaults, limits, and API credentials
        </p>
      </div>

      <GeneralSettings
        settings={settings}
        initialized={initialized}
        onSaved={() => {
          // No-op — GeneralSettings handles its own dirty state
        }}
      />

      <IntelligenceSettings settings={settings} />

      <PrivacySettings settings={settings} />

      <GoogleSettings />
    </div>
  );
}
