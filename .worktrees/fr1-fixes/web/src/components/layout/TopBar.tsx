import { useState, useEffect } from "react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { PrivacyToggle } from "@/components/shared/PrivacyToggle";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { isUsingMocks } from "@/api/client";

export function TopBar() {
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return (
    <header className="flex h-12 items-center justify-between border-b border-border/50 px-3 gap-3 glass">
      <div className="flex items-center gap-2">
        <SidebarTrigger className="hover:bg-accent/60 transition-colors" />
        {isUsingMocks() && (
          <Badge variant="outline" className="text-[10px] font-mono text-warning border-warning/20 bg-warning/5 px-2 py-0.5">
            MOCK
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-2">
        <PrivacyToggle />
        <ThemeToggle />
        {isOnline ? (
          <div
            className="flex items-center gap-1.5 ml-1 px-2 py-1 rounded-full bg-success/8 border border-success/15"
            data-testid="online-indicator"
            aria-label="Online"
          >
            <div className="h-1.5 w-1.5 rounded-full bg-success animate-glow-pulse" />
            <span className="text-[10px] font-medium text-success">Online</span>
          </div>
        ) : (
          <div
            className="flex items-center gap-1.5 ml-1 px-2 py-1 rounded-full bg-destructive/8 border border-destructive/15"
            data-testid="offline-indicator"
            aria-label="Offline"
          >
            <div className="h-1.5 w-1.5 rounded-full bg-destructive" />
            <span className="text-[10px] font-medium text-destructive">Offline</span>
          </div>
        )}
      </div>
    </header>
  );
}
