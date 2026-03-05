/**
 * Settings & usage state management — Zustand store.
 * Manages user settings, provider selection, and cost/usage tracking.
 */

import { create } from "zustand";

export interface UsageData {
  daily: { used: number; limit: number; cost_usd: number };
  monthly: { used: number; limit: number; cost_usd: number };
  messages: Array<{
    model: string;
    prompt_tokens: number;
    completion_tokens: number;
    cost_usd: number;
  }>;
}

export interface Settings {
  default_provider: "ollama" | "anthropic" | "openai";
  privacy_mode: "private" | "external";
  daily_token_cap: number;
  monthly_token_cap: number;
}

interface SettingsState {
  settings: Settings;
  usage: UsageData;
  loading: boolean;
  error: string | null;

  setSettings: (settings: Partial<Settings>) => void;
  setUsage: (usage: UsageData) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

const defaultSettings: Settings = {
  default_provider: "ollama",
  privacy_mode: "private",
  daily_token_cap: 100000,
  monthly_token_cap: 3000000,
};

const defaultUsage: UsageData = {
  daily: { used: 0, limit: 100000, cost_usd: 0 },
  monthly: { used: 0, limit: 3000000, cost_usd: 0 },
  messages: [],
};

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: { ...defaultSettings },
  usage: { ...defaultUsage },
  loading: false,
  error: null,

  setSettings(partial: Partial<Settings>) {
    set((state) => ({
      settings: { ...state.settings, ...partial },
    }));
  },

  setUsage(usage: UsageData) {
    set({ usage });
  },

  setLoading(loading: boolean) {
    set({ loading });
  },

  setError(error: string | null) {
    set({ error });
  },
}));
