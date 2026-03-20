import { useSearchParams } from "react-router-dom";

export default function TracesPage() {
  const [searchParams] = useSearchParams();
  const traceId = searchParams.get("traceId");
  const langfuseBase = import.meta.env.VITE_LANGFUSE_URL || "http://localhost:3001";

  // Deep-link to specific trace if traceId param is present
  const src = traceId
    ? `${langfuseBase}/trace/${traceId}`
    : langfuseBase;

  return (
    <div className="h-full w-full">
      <iframe
        src={src}
        className="w-full h-full border-0"
        title="Langfuse Traces"
        allow="clipboard-read; clipboard-write"
      />
    </div>
  );
}
