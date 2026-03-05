/**
 * EventCard — Individual event display with expand/collapse.
 * Shows event type indicator, timestamp, and expandable details.
 */

import { useState } from "react";
import type { RunEvent } from "../../store/runs";

/** Maps event types to display labels and CSS class suffixes. */
const EVENT_CONFIG: Record<
  RunEvent["type"],
  { label: string; className: string }
> = {
  classification_done: { label: "Classification", className: "classification" },
  step_started: { label: "Step Started", className: "step" },
  token_stream: { label: "Token Stream", className: "stream" },
  tool_called: { label: "Tool Called", className: "tool-called" },
  tool_result: { label: "Tool Result", className: "tool-result" },
  approval_requested: { label: "Approval Requested", className: "approval" },
  approval_received: { label: "Approval Received", className: "approval" },
  artifact_created: { label: "Artifact Created", className: "artifact" },
  result_ready: { label: "Result Ready", className: "result" },
  error: { label: "Error", className: "error" },
};

interface EventCardProps {
  event: RunEvent;
}

export function EventCard({ event }: EventCardProps) {
  const [expanded, setExpanded] = useState(false);
  const config = EVENT_CONFIG[event.type];

  const formattedTime = new Date(event.timestamp).toLocaleTimeString();

  return (
    <div
      className={`event-card event-card--${config.className}`}
      data-testid={`event-card-${event.id}`}
    >
      <button
        className="event-card__header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-label={`${config.label} event details`}
      >
        <span
          className={`event-card__indicator event-card__indicator--${config.className}`}
          data-testid={`event-indicator-${event.type}`}
        >
          {config.label}
        </span>
        <span className="event-card__time">{formattedTime}</span>
      </button>

      {expanded && (
        <div className="event-card__details" role="region" aria-label="Event details">
          <pre className="event-card__data">
            {JSON.stringify(event.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
