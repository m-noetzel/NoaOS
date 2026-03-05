/**
 * Approval state management — Zustand store.
 * Manages pending approvals, selection state, and decision actions.
 */

import { create } from "zustand";

export interface ApprovalRequest {
  id: string;
  run_id: string;
  risk_tier: "medium" | "high";
  action_type: string;
  preview: { summary: string; details: Record<string, unknown> };
  created_at: string;
}

interface ApprovalState {
  approvals: ApprovalRequest[];
  selectedIds: Set<string>;
  loading: boolean;
  error: string | null;

  setApprovals: (approvals: ApprovalRequest[]) => void;
  removeApproval: (id: string) => void;
  removeApprovals: (ids: string[]) => void;
  toggleSelected: (id: string) => void;
  selectAll: () => void;
  clearSelection: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useApprovalStore = create<ApprovalState>((set, get) => ({
  approvals: [],
  selectedIds: new Set<string>(),
  loading: false,
  error: null,

  setApprovals(approvals: ApprovalRequest[]) {
    set({ approvals });
  },

  removeApproval(id: string) {
    set((state) => ({
      approvals: state.approvals.filter((a) => a.id !== id),
      selectedIds: (() => {
        const next = new Set(state.selectedIds);
        next.delete(id);
        return next;
      })(),
    }));
  },

  removeApprovals(ids: string[]) {
    const idSet = new Set(ids);
    set((state) => ({
      approvals: state.approvals.filter((a) => !idSet.has(a.id)),
      selectedIds: (() => {
        const next = new Set(state.selectedIds);
        ids.forEach((id) => next.delete(id));
        return next;
      })(),
    }));
  },

  toggleSelected(id: string) {
    set((state) => {
      const next = new Set(state.selectedIds);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return { selectedIds: next };
    });
  },

  selectAll() {
    set((state) => ({
      selectedIds: new Set(state.approvals.map((a) => a.id)),
    }));
  },

  clearSelection() {
    set({ selectedIds: new Set() });
  },

  setLoading(loading: boolean) {
    set({ loading });
  },

  setError(error: string | null) {
    set({ error });
  },
}));
