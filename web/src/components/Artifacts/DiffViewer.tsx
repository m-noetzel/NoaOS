/**
 * DiffViewer — renders diff content with syntax highlighting markers.
 * Lines starting with '+' are additions, '-' are removals, '@@' are hunks.
 */

import React from "react";

interface DiffViewerProps {
  content: string;
  name: string;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ content, name }) => {
  const lines = content.split("\n");

  return (
    <div role="region" aria-label={`Diff: ${name}`}>
      <h3>{name}</h3>
      <pre data-testid="diff-content">
        {lines.map((line, index) => {
          let className = "diff-context";
          if (line.startsWith("+")) {
            className = "diff-addition";
          } else if (line.startsWith("-")) {
            className = "diff-removal";
          } else if (line.startsWith("@@")) {
            className = "diff-hunk";
          }
          return (
            <div key={index} className={className} data-diff-type={className}>
              {line}
            </div>
          );
        })}
      </pre>
    </div>
  );
};
