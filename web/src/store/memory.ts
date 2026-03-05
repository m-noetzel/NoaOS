/**
 * Memory state management — Zustand store.
 * Manages stored facts, filtering, and CRUD operations.
 */

import { create } from "zustand";

export type FactCategory =
  | "preference"
  | "habit"
  | "project_context"
  | "personal_info";

export type FactStatus = "approved" | "pending" | "rejected";

export interface Fact {
  id: string;
  fact: string;
  category: FactCategory;
  status: FactStatus;
  auto_extracted: boolean;
  created_at: string;
  source_thread_id?: string;
}

export const FACT_CATEGORIES: FactCategory[] = [
  "preference",
  "habit",
  "project_context",
  "personal_info",
];

interface MemoryState {
  facts: Fact[];
  filterCategory: FactCategory | null;
  loading: boolean;
  error: string | null;
  editingFactId: string | null;
  editingContent: string;

  setFacts: (facts: Fact[]) => void;
  addFact: (fact: Fact) => void;
  removeFact: (id: string) => void;
  updateFact: (id: string, updates: Partial<Fact>) => void;
  setFilterCategory: (category: FactCategory | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  startEditing: (factId: string, content: string) => void;
  setEditingContent: (content: string) => void;
  cancelEditing: () => void;

  // Computed helpers
  filteredFacts: () => Fact[];
  stats: () => { total: number; byCategory: Record<FactCategory, number> };
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  facts: [],
  filterCategory: null,
  loading: false,
  error: null,
  editingFactId: null,
  editingContent: "",

  setFacts(facts: Fact[]) {
    set({ facts });
  },

  addFact(fact: Fact) {
    set((state) => ({ facts: [...state.facts, fact] }));
  },

  removeFact(id: string) {
    set((state) => ({
      facts: state.facts.filter((f) => f.id !== id),
    }));
  },

  updateFact(id: string, updates: Partial<Fact>) {
    set((state) => ({
      facts: state.facts.map((f) => (f.id === id ? { ...f, ...updates } : f)),
    }));
  },

  setFilterCategory(category: FactCategory | null) {
    set({ filterCategory: category });
  },

  setLoading(loading: boolean) {
    set({ loading });
  },

  setError(error: string | null) {
    set({ error });
  },

  startEditing(factId: string, content: string) {
    set({ editingFactId: factId, editingContent: content });
  },

  setEditingContent(content: string) {
    set({ editingContent: content });
  },

  cancelEditing() {
    set({ editingFactId: null, editingContent: "" });
  },

  filteredFacts() {
    const { facts, filterCategory } = get();
    if (!filterCategory) return facts;
    return facts.filter((f) => f.category === filterCategory);
  },

  stats() {
    const { facts } = get();
    const byCategory: Record<FactCategory, number> = {
      preference: 0,
      habit: 0,
      project_context: 0,
      personal_info: 0,
    };
    for (const fact of facts) {
      byCategory[fact.category]++;
    }
    return { total: facts.length, byCategory };
  },
}));
