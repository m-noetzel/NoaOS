/**
 * Queue state management — Zustand store.
 * Manages task queue items, ordering, and API interactions.
 */

import { create } from "zustand";
import { apiClient } from "../api/client";

export interface QueueTask {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  priority: "critical" | "high" | "normal" | "background";
  position?: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

const PRIORITY_ORDER: Record<QueueTask["priority"], number> = {
  critical: 0,
  high: 1,
  normal: 2,
  background: 3,
};

interface QueueState {
  tasks: QueueTask[];
  loading: boolean;
  error: string | null;

  setTasks: (tasks: QueueTask[]) => void;
  fetchTasks: () => Promise<void>;
  cancelTask: (id: string) => Promise<void>;
  retryTask: (id: string) => Promise<void>;
  sortedTasks: () => QueueTask[];
}

export const useQueueStore = create<QueueState>((set, get) => ({
  tasks: [],
  loading: false,
  error: null,

  setTasks(tasks: QueueTask[]) {
    set({ tasks });
  },

  async fetchTasks() {
    set({ loading: true, error: null });
    try {
      const res = await apiClient.get<QueueTask[]>("/tasks");
      set({ tasks: res.data, loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to fetch tasks",
        loading: false,
      });
    }
  },

  async cancelTask(id: string) {
    try {
      await apiClient.post(`/tasks/${id}/cancel`);
      set((state) => ({
        tasks: state.tasks.map((t) =>
          t.id === id ? { ...t, status: "cancelled" as const } : t,
        ),
      }));
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to cancel task",
      });
    }
  },

  async retryTask(id: string) {
    try {
      await apiClient.post(`/tasks/${id}/retry`);
      set((state) => ({
        tasks: state.tasks.map((t) =>
          t.id === id ? { ...t, status: "queued" as const } : t,
        ),
      }));
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to retry task",
      });
    }
  },

  sortedTasks() {
    const tasks = [...get().tasks];
    tasks.sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);
    return tasks;
  },
}));
