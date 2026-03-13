import { useQuery } from "@tanstack/react-query";
import { apiRequest, BASE_URL } from "@/api/client";
import { getAccessToken } from "@/auth/tokens";
import type { Artifact } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, Eye } from "lucide-react";
import { useState } from "react";
import DOMPurify from "dompurify";

/**
 * FE-M3: Downloads an artifact using fetch with Authorization header, then
 * triggers a browser download via a temporary blob URL.  This prevents
 * unauthenticated access to protected files (plain <a href> bypasses auth).
 */
async function downloadArtifact(artifactId: string, filename: string): Promise<void> {
  const token = getAccessToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}/api/v1/artifacts/${artifactId}/download`, {
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    // Append to body so Firefox's download attribute fires reliably,
    // then remove immediately after click.
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    // Revoke in the next animation frame — gives the browser one render
    // cycle (~16ms) to start the download pipeline before cleanup.
    requestAnimationFrame(() => URL.revokeObjectURL(blobUrl));
  }
}

const PAGE_LIMIT = 20;

export default function Artifacts() {
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const { data: artifactsRes, isLoading } = useQuery({
    queryKey: ["artifacts", offset],
    queryFn: () => apiRequest<Artifact[]>(`/api/v1/artifacts?limit=${PAGE_LIMIT}&offset=${offset}`),
  });

  const artifacts = artifactsRes?.data || [];
  const preview = artifacts.find((a) => a.id === previewId);

  const typeColors: Record<string, string> = {
    file: "bg-info/15 text-info border-info/30",
    diff: "bg-warning/15 text-warning border-warning/30",
    export: "bg-success/15 text-success border-success/30",
    preview: "bg-primary/15 text-primary border-primary/30",
  };

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Artifacts</h1>
        <p className="text-sm text-muted-foreground">{artifacts.length} artifacts from runs</p>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {artifacts.map((art) => (
            <Card key={art.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">{art.name}</CardTitle>
                  <Badge variant="outline" className={typeColors[art.type] || ""}>{art.type}</Badge>
                </div>
                <p className="text-xs text-muted-foreground font-mono">Run: {art.run_id}</p>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2">
                  {art.type === "preview" && (
                    <Button size="sm" variant="outline" className="gap-1" onClick={() => setPreviewId(art.id)}>
                      <Eye className="h-3.5 w-3.5" /> Preview
                    </Button>
                  )}
                  {art.type === "file" && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      onClick={() => {
                        downloadArtifact(art.id, art.name).catch((err: unknown) => {
                          console.error("Artifact download failed:", err);
                        });
                      }}
                    >
                      <Download className="h-3.5 w-3.5" /> Download
                    </Button>
                  )}
                  {art.type === "diff" && (
                    <Button size="sm" variant="outline" className="gap-1" onClick={() => setPreviewId(art.id)}>
                      <Eye className="h-3.5 w-3.5" /> View Diff
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {preview && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">{preview.name}</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setPreviewId(null)}>Close</Button>
            </div>
          </CardHeader>
          <CardContent>
            {preview.type === "diff" ? (
              <pre className="text-xs font-mono bg-muted p-3 rounded-md overflow-auto max-h-96 whitespace-pre">
                {preview.content}
              </pre>
            ) : preview.type === "preview" ? (
              <div
                className="prose prose-sm dark:prose-invert max-w-none"
                dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(preview.content) }}
              />
            ) : (
              <pre className="text-xs font-mono bg-muted p-3 rounded-md overflow-auto max-h-96">
                {preview.content}
              </pre>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
