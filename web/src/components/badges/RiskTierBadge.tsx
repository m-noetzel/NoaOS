import type { RiskTier } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const tierConfig: Record<RiskTier, { label: string; className: string }> = {
  low: { label: "Low", className: "bg-success/15 text-success border-success/30" },
  medium: { label: "Medium", className: "bg-warning/15 text-warning border-warning/30" },
  high: { label: "High", className: "bg-destructive/15 text-destructive border-destructive/30" },
  critical: { label: "Critical", className: "bg-destructive text-destructive-foreground" },
};

const fallbackConfig = { label: "Unknown", className: "bg-muted text-muted-foreground" };

export function RiskTierBadge({ tier }: { tier: RiskTier | string }) {
  const config = tierConfig[tier as RiskTier] || fallbackConfig;
  return (
    <Badge variant="outline" className={cn("text-xs font-medium", config.className)}>
      {config.label}
    </Badge>
  );
}
