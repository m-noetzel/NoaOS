/**
 * Run state management — Zustand store.
 * Manages run history, events, and real-time updates.
 */

import { create } from "zustand";

export interface RunEvent {
  id: string;
  type:
    | "classification_done"
    | "step_started"
    | "token_stream"
    | "tool_called"
    | "tool_result"
    | "approval_requested"
    | "approval_received"
    | "artifact_created"
    | "result_ready"
    | "error";
  data: Record<string, unknown>;
  timestamp: string;
}

export interface Run {
  id: string;
  status:
    | "pending"
    | "running"
    | "awaiting_approval"
    | "completed"
    | "failed"
    | "cancelled";
  risk_tier: "low" | "medium" | "high";
  privacy_mode: "private" | "external";
  events: RunEvent[];
  created_at: string;
  summary?: string;
}

interface RunState {
  runs: Run[];
  activeRunId: string | null;

  setActiveRun: (runId: string | null) => void;
  addRun: (run: Run) => void;
  updateRunStatus: (runId: string, status: Run["status"]) => void;
  addEvent: (runId: string, event: RunEvent) => void;
  getRun: (runId: string) => Run | undefined;
  getActiveRun: () => Run | undefined;
}

export const useRunStore = create<RunState>((set, get) => ({
  runs: [],
  activeRunId: null,

  setActiveRun(runId: string | null) {
    set({ activeRunId: runId });
  },

  addRun(run: Run) {
    set((state) => ({
      runs: [...state.runs, run],
    }));
  },

  updateRunStatus(runId: string, status: Run["status"]) {
    set((state) => ({
      runs: state.runs.map((r) =>
        r.id === runId ? { ...r, status } : r,
      ),
    }));
  },

  addEvent(runId: string, event: RunEvent) {
    set((state) => ({
      runs: state.runs.map((r) =>
        r.id === runId
          ? { ...r, events: [...r.events, event] }
          : r,
      ),
    }));
  },

  getRun(runId: string) {
    return get().runs.find((r) => r.id === runId);
  },

  getActiveRun() {
    const { runs, activeRunId } = get();
    return runs.find((r) => r.id === activeRunId);
  },
}));
