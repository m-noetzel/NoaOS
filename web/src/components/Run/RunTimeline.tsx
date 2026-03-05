/**
 * RunTimeline — Timeline component showing ordered run events.
 * Displays events chronologically with type indicators.
 */

import type { Run } from "../../store/runs";
import { EventCard } from "./EventCard";

interface RunTimelineProps {
  run: Run;
}

const STATUS_LABELS: Record<Run["status"], string> = {
  pending: "Pending",
  running: "Running",
  awaiting_approval: "Awaiting Approval",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function RunTimeline({ run }: RunTimelineProps) {
  const sortedEvents = [...run.events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  );

  return (
    <div className="run-timeline" data-testid="run-timeline">
      <div className="run-timeline__meta" aria-label="Run metadata">
        <span className="run-timeline__status" data-testid="run-status">
          {STATUS_LABELS[run.status]}
        </span>
        <span className="run-timeline__risk" data-testid="run-risk-tier">
          Risk: {run.risk_tier}
        </span>
        <span className="run-timeline__privacy" data-testid="run-privacy-mode">
          {run.privacy_mode}
        </span>
      </div>

      <ol className="run-timeline__events" aria-label="Run events">
        {sortedEvents.map((event) => (
          <li key={event.id} className="run-timeline__event-item">
            <EventCard event={event} />
          </li>
        ))}
      </ol>
    </div>
  );
}
