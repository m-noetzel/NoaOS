import { useSearchParams } from "react-router-dom";
import { ExternalLink } from "lucide-react";

export default function TracesPage() {
  const [searchParams] = useSearchParams();
  const traceId = searchParams.get("traceId");
  const langfuseBase =
    import.meta.env.VITE_LANGFUSE_URL || "http://localhost:3001";

  const traceUrl = traceId
    ? `${langfuseBase}/trace/${traceId}`
    : langfuseBase;

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Langfuse Traces</h1>
        <p className="text-muted-foreground max-w-md">
          LLM observability dashboard — view traces, generations, token usage,
          and evaluation scores for all runs.
        </p>
      </div>
      <a
        href={traceUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 transition-colors"
      >
        Open Langfuse
        <ExternalLink className="h-4 w-4" />
      </a>
      {traceId && (
        <p className="text-xs text-muted-foreground">
          Trace: <code className="font-mono">{traceId}</code>
        </p>
      )}
    </div>
  );
}
