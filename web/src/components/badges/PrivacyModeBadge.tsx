import type { PrivacyMode } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Shield, Globe } from "lucide-react";

export function PrivacyModeBadge({ mode }: { mode: PrivacyMode }) {
  return (
    <Badge variant="outline" className="text-xs gap-1">
      {mode === "private" ? <Shield className="h-3 w-3" /> : <Globe className="h-3 w-3" />}
      {mode === "private" ? "Private" : "External"}
    </Badge>
  );
}
