import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

interface GoogleStatus {
  connected: boolean;
  scopes: string[];
}

export function GoogleSettings() {
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
        "/api/v1/auth/google/authorize"
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
              <span className="text-sm text-muted-foreground">
                Not connected
              </span>
            </div>
            <Button size="sm" onClick={handleConnect} disabled={isConnecting}>
              {isConnecting ? "Connecting…" : "Connect Google"}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
