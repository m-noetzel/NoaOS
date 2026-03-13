import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

interface JSONViewerProps {
  data: unknown;
  maxLines?: number;
  className?: string;
}

export function JSONViewer({ data, maxLines = 10, className }: JSONViewerProps) {
  const [expanded, setExpanded] = useState(false);
  const formatted = JSON.stringify(data, null, 2);
  const lines = formatted.split("\n");
  const isLong = lines.length > maxLines;
  const display = expanded ? formatted : lines.slice(0, maxLines).join("\n") + (isLong ? "\n..." : "");

  const copy = () => navigator.clipboard.writeText(formatted);

  return (
    <div className={cn("relative rounded-md border bg-muted/30", className)}>
      <div className="absolute right-2 top-2 flex gap-1">
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={copy}>
          <Copy className="h-3 w-3" />
        </Button>
      </div>
      <pre className="p-3 text-xs font-mono overflow-auto max-h-96 text-foreground">
        {display}
      </pre>
      {isLong && (
        <Button
          variant="ghost"
          size="sm"
          className="w-full text-xs h-7 rounded-t-none"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <ChevronDown className="h-3 w-3 mr-1" /> : <ChevronRight className="h-3 w-3 mr-1" />}
          {expanded ? "Collapse" : `Show all ${lines.length} lines`}
        </Button>
      )}
    </div>
  );
}
