/**
 * ArtifactViewer — displays a list of artifacts with type icons,
 * metadata panel, and diff viewing capabilities.
 */

import React from "react";
import type { Artifact } from "../../store/artifacts";
import { DiffViewer } from "./DiffViewer";

interface ArtifactViewerProps {
  artifacts: Artifact[];
  selectedArtifactId?: string | null;
  onSelect?: (id: string) => void;
}

const TYPE_ICONS: Record<Artifact["type"], string> = {
  file: "\u{1F4C4}",
  diff: "\u{1F504}",
  export: "\u{1F4E6}",
  preview: "\u{1F441}",
};

const TYPE_LABELS: Record<Artifact["type"], string> = {
  file: "File",
  diff: "Diff",
  export: "Export",
  preview: "Preview",
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleString();
}

export const ArtifactViewer: React.FC<ArtifactViewerProps> = ({
  artifacts,
  selectedArtifactId,
  onSelect,
}) => {
  if (artifacts.length === 0) {
    return (
      <div role="region" aria-label="Artifacts">
        <p>No artifacts</p>
      </div>
    );
  }

  const selected = selectedArtifactId
    ? artifacts.find((a) => a.id === selectedArtifactId)
    : null;

  return (
    <div role="region" aria-label="Artifacts">
      <ul role="list" aria-label="Artifact list">
        {artifacts.map((artifact) => (
          <li key={artifact.id}>
            <button
              onClick={() => onSelect?.(artifact.id)}
              aria-current={artifact.id === selectedArtifactId ? "true" : undefined}
            >
              <span data-testid={`icon-${artifact.type}`} aria-label={TYPE_LABELS[artifact.type]}>
                {TYPE_ICONS[artifact.type]}
              </span>
              <span>{artifact.name}</span>
              <span>{formatBytes(artifact.size_bytes)}</span>
              <span>{artifact.mime_type}</span>
            </button>
          </li>
        ))}
      </ul>

      {selected && (
        <div role="region" aria-label="Artifact metadata">
          <dl>
            <dt>Name</dt>
            <dd>{selected.name}</dd>
            <dt>Size</dt>
            <dd>{formatBytes(selected.size_bytes)}</dd>
            <dt>Type</dt>
            <dd>{selected.mime_type}</dd>
            <dt>Created</dt>
            <dd>{formatTime(selected.created_at)}</dd>
          </dl>

          {selected.type === "export" && (
            <a
              href={`/api/v1/artifacts/${selected.id}/download`}
              download={selected.name}
              role="button"
              aria-label="Download"
            >
              Download
            </a>
          )}

          {selected.type === "diff" && selected.content && (
            <DiffViewer content={selected.content} name={selected.name} />
          )}
        </div>
      )}
    </div>
  );
};
