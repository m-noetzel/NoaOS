import { Shield, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useState } from "react";
import type { PrivacyMode } from "@/api/types";

export function PrivacyToggle() {
  const [mode, setMode] = useState<PrivacyMode>("private");

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => setMode((m) => (m === "private" ? "external" : "private"))}
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
