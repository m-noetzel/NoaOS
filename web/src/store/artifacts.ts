/**
 * Artifact state management — Zustand store.
 * Manages artifact listing, selection, and fetching.
 */

import { create } from "zustand";

export interface Artifact {
  id: string;
  run_id: string;
  type: "file" | "diff" | "export" | "preview";
  name: string;
  mime_type: string;
  size_bytes: number;
  content?: string;
  created_at: string;
}

interface ArtifactState {
  artifacts: Artifact[];
  selectedArtifactId: string | null;

  setArtifacts: (artifacts: Artifact[]) => void;
  addArtifact: (artifact: Artifact) => void;
  selectArtifact: (id: string | null) => void;
  getArtifact: (id: string) => Artifact | undefined;
  getArtifactsByRunId: (runId: string) => Artifact[];
  clearArtifacts: () => void;
}

export const useArtifactStore = create<ArtifactState>((set, get) => ({
  artifacts: [],
  selectedArtifactId: null,

  setArtifacts(artifacts: Artifact[]) {
    set({ artifacts });
  },

  addArtifact(artifact: Artifact) {
    set((state) => ({
      artifacts: [...state.artifacts, artifact],
    }));
  },

  selectArtifact(id: string | null) {
    set({ selectedArtifactId: id });
  },

  getArtifact(id: string) {
    return get().artifacts.find((a) => a.id === id);
  },

  getArtifactsByRunId(runId: string) {
    return get().artifacts.filter((a) => a.run_id === runId);
  },

  clearArtifacts() {
    set({ artifacts: [], selectedArtifactId: null });
  },
}));
