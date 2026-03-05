/**
 * QueueItem — Renders a single task in the queue list.
 * Shows status badge, priority, position, and action buttons.
 */

import React from "react";
import type { QueueTask } from "../../store/queue";

const STATUS_COLORS: Record<QueueTask["status"], string> = {
  running: "blue",
  queued: "gray",
  completed: "green",
  failed: "red",
  cancelled: "gray",
};

interface QueueItemProps {
  task: QueueTask;
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
}

export const QueueItem: React.FC<QueueItemProps> = ({
  task,
  onCancel,
  onRetry,
}) => {
  const badgeColor = STATUS_COLORS[task.status];

  return (
    <div data-testid={`queue-item-${task.id}`} className="queue-item">
      <div className="queue-item-header">
        <span className="queue-item-id">{task.id}</span>
        <span
          data-testid={`status-badge-${task.id}`}
          className={`status-badge status-${badgeColor}`}
          style={{ color: badgeColor }}
        >
          {task.status}
        </span>
      </div>

      <div className="queue-item-details">
        <span className="queue-item-priority">Priority: {task.priority}</span>
        {task.status === "queued" && task.position != null && (
          <span data-testid={`queue-position-${task.id}`} className="queue-position">
            Position: {task.position}
          </span>
        )}
      </div>

      <div className="queue-item-actions">
        {task.status === "queued" && (
          <button
            data-testid={`cancel-btn-${task.id}`}
            onClick={() => onCancel(task.id)}
          >
            Cancel
          </button>
        )}
        {task.status === "failed" && (
          <button
            data-testid={`retry-btn-${task.id}`}
            onClick={() => onRetry(task.id)}
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
};
