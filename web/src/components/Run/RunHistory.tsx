/**
 * RunHistory — Recent runs list with status badges.
 * Shows a list of runs with their status, risk tier, and summary.
 */

import type { Run } from "../../store/runs";

interface RunHistoryProps {
  runs: Run[];
  activeRunId: string | null;
  onSelectRun: (runId: string) => void;
}

const STATUS_BADGE: Record<Run["status"], string> = {
  pending: "pending",
  running: "running",
  awaiting_approval: "awaiting-approval",
  completed: "completed",
  failed: "failed",
  cancelled: "cancelled",
};

export function RunHistory({ runs, activeRunId, onSelectRun }: RunHistoryProps) {
  const sortedRuns = [...runs].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <div className="run-history" data-testid="run-history">
      <h2 className="run-history__title">Recent Runs</h2>
      <ul className="run-history__list" aria-label="Recent runs">
        {sortedRuns.map((run) => (
          <li key={run.id} className="run-history__item">
            <button
              className={`run-history__button ${
                run.id === activeRunId ? "run-history__button--active" : ""
              }`}
              onClick={() => onSelectRun(run.id)}
              aria-current={run.id === activeRunId ? "true" : undefined}
              aria-label={`Run ${run.id}`}
            >
              <span
                className={`run-history__badge run-history__badge--${STATUS_BADGE[run.status]}`}
                data-testid={`run-badge-${run.id}`}
              >
                {run.status}
              </span>
              <span className="run-history__summary">
                {run.summary ?? `Run ${run.id}`}
              </span>
              <span className="run-history__date">
                {new Date(run.created_at).toLocaleDateString()}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
