import { Wrench } from "lucide-react";

export function ToolCallChip({ toolName, args }: { toolName: string; args?: Record<string, unknown> }) {
  return (
    <div className="inline-flex items-center gap-1.5 rounded-md border bg-muted/50 px-2 py-1 text-xs font-mono">
      <Wrench className="h-3 w-3 text-muted-foreground" />
      <span className="font-medium">{toolName}</span>
      {args && Object.keys(args).length > 0 && (
        <span className="text-muted-foreground">
          ({Object.entries(args).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(", ")})
        </span>
      )}
    </div>
  );
}
