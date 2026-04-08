import { Lock, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PrivacyMode } from "@/api/types";

interface DomainBadgeProps {
  domain: PrivacyMode;
  className?: string;
}

export function DomainBadge({ domain, className }: DomainBadgeProps) {
  if (domain === "private") {
    return (
      <span
        data-testid="domain-badge-private"
        className={cn(
          "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium",
          "bg-purple-900/60 text-purple-200 border border-purple-700/40",
          className
        )}
      >
        <Lock className="h-2.5 w-2.5" aria-hidden="true" />
        Private
      </span>
    );
  }

  return (
    <span
      data-testid="domain-badge-external"
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium",
        "bg-blue-900/60 text-blue-200 border border-blue-700/40",
        className
      )}
    >
      <Globe className="h-2.5 w-2.5" aria-hidden="true" />
      External
    </span>
  );
}
