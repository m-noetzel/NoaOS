/**
 * PreviewCard — Dry-run preview display for an approval request.
 * Shows formatted action summary and details.
 */

import type { ApprovalRequest } from "../../store/approvals";

interface PreviewCardProps {
  preview: ApprovalRequest["preview"];
}

export function PreviewCard({ preview }: PreviewCardProps) {
  return (
    <div
      className="preview-card"
      role="region"
      aria-label="Dry-run preview"
    >
      <p className="preview-summary" data-testid="preview-summary">
        {preview.summary}
      </p>
      {Object.keys(preview.details).length > 0 && (
        <dl className="preview-details">
          {Object.entries(preview.details).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
