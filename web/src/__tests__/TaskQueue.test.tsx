/**
 * TaskQueue test suite — verifies queue visualization,
 * ordering, status badges, actions, and empty state.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../test/mocks/server";
import { useQueueStore, type QueueTask } from "../store/queue";
import { TaskQueue } from "../components/Queue/TaskQueue";

const API_BASE = "http://localhost:8000/api/v1";

function makeMeta() {
  return {
    request_id: "req-t",
    trace_id: "trace-t",
    timestamp: new Date().toISOString(),
  };
}

const SAMPLE_TASKS: QueueTask[] = [
  {
    id: "task-1",
    status: "running",
    priority: "high",
    metadata: { type: "fetch" },
    created_at: "2026-03-05T10:00:00Z",
  },
  {
    id: "task-2",
    status: "queued",
    priority: "normal",
    position: 2,
    metadata: { type: "process" },
    created_at: "2026-03-05T10:01:00Z",
  },
  {
    id: "task-3",
    status: "completed",
    priority: "critical",
    metadata: { type: "send" },
    created_at: "2026-03-05T09:50:00Z",
  },
  {
    id: "task-4",
    status: "failed",
    priority: "background",
    metadata: { type: "cleanup" },
    created_at: "2026-03-05T10:02:00Z",
  },
];

beforeEach(() => {
  // Reset zustand store state between tests
  useQueueStore.setState({ tasks: [], loading: false, error: null });
});

describe("TaskQueue", () => {
  it("renders queue items with status and priority", () => {
    useQueueStore.setState({ tasks: SAMPLE_TASKS });
    render(<TaskQueue />);

    for (const task of SAMPLE_TASKS) {
      const item = screen.getByTestId(`queue-item-${task.id}`);
      expect(item).toBeInTheDocument();
      expect(within(item).getByText(task.status)).toBeInTheDocument();
      expect(
        within(item).getByText(`Priority: ${task.priority}`),
      ).toBeInTheDocument();
    }
  });

  it("items ordered by priority tier (critical > high > normal > background)", () => {
    useQueueStore.setState({ tasks: SAMPLE_TASKS });
    render(<TaskQueue />);

    const items = screen.getAllByTestId(/^queue-item-/);
    const ids = items.map((el) =>
      el.getAttribute("data-testid")!.replace("queue-item-", ""),
    );

    // critical=task-3, high=task-1, normal=task-2, background=task-4
    expect(ids).toEqual(["task-3", "task-1", "task-2", "task-4"]);
  });

  it("cancel button cancels a queued task", async () => {
    server.use(
      http.post(`${API_BASE}/tasks/task-2/cancel`, () => {
        return HttpResponse.json({ data: { success: true }, meta: makeMeta() });
      }),
    );

    useQueueStore.setState({ tasks: SAMPLE_TASKS });
    render(<TaskQueue />);

    const cancelBtn = screen.getByTestId("cancel-btn-task-2");
    await userEvent.click(cancelBtn);

    // Store should update status to cancelled
    const updated = useQueueStore.getState().tasks.find((t) => t.id === "task-2");
    expect(updated?.status).toBe("cancelled");
  });

  it("retry button retries a failed task", async () => {
    server.use(
      http.post(`${API_BASE}/tasks/task-4/retry`, () => {
        return HttpResponse.json({ data: { success: true }, meta: makeMeta() });
      }),
    );

    useQueueStore.setState({ tasks: SAMPLE_TASKS });
    render(<TaskQueue />);

    const retryBtn = screen.getByTestId("retry-btn-task-4");
    await userEvent.click(retryBtn);

    // Store should update status to queued
    const updated = useQueueStore.getState().tasks.find((t) => t.id === "task-4");
    expect(updated?.status).toBe("queued");
  });

  it("status badges show correct colors (running=blue, queued=gray, completed=green, failed=red)", () => {
    useQueueStore.setState({ tasks: SAMPLE_TASKS });
    render(<TaskQueue />);

    const expectedColors: Record<string, string> = {
      "task-1": "blue",   // running
      "task-2": "gray",   // queued
      "task-3": "green",  // completed
      "task-4": "red",    // failed
    };

    for (const [taskId, color] of Object.entries(expectedColors)) {
      const badge = screen.getByTestId(`status-badge-${taskId}`);
      expect(badge.style.color).toBe(color);
    }
  });

  it("empty queue shows 'No tasks' message", () => {
    useQueueStore.setState({ tasks: [] });
    render(<TaskQueue />);

    expect(screen.getByTestId("empty-queue-message")).toHaveTextContent(
      "No tasks",
    );
  });

  it("queue position displayed for queued tasks", () => {
    useQueueStore.setState({ tasks: SAMPLE_TASKS });
    render(<TaskQueue />);

    // task-2 is queued with position 2
    const posEl = screen.getByTestId("queue-position-task-2");
    expect(posEl).toHaveTextContent("Position: 2");

    // task-1 is running — should not show position
    expect(screen.queryByTestId("queue-position-task-1")).toBeNull();
  });
});
