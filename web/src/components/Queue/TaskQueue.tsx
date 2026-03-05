/**
 * TaskQueue — Panel showing all tasks in the queue,
 * ordered by priority tier with status indicators and actions.
 */

import React from "react";
import { useQueueStore } from "../../store/queue";
import { QueueItem } from "./QueueItem";

export const TaskQueue: React.FC = () => {
  const sortedTasks = useQueueStore((state) => state.sortedTasks());
  const cancelTask = useQueueStore((state) => state.cancelTask);
  const retryTask = useQueueStore((state) => state.retryTask);

  if (sortedTasks.length === 0) {
    return (
      <div data-testid="task-queue" className="task-queue">
        <h2>Task Queue</h2>
        <p data-testid="empty-queue-message">No tasks</p>
      </div>
    );
  }

  return (
    <div data-testid="task-queue" className="task-queue">
      <h2>Task Queue</h2>
      <div className="queue-list">
        {sortedTasks.map((task) => (
          <QueueItem
            key={task.id}
            task={task}
            onCancel={cancelTask}
            onRetry={retryTask}
          />
        ))}
      </div>
    </div>
  );
};
