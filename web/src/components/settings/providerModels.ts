/** Models grouped by provider (UI-H2) */
export const PROVIDER_MODELS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
    { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
  ],
  openai: [
    { value: "gpt-4.1", label: "GPT-4.1" },
    { value: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
    { value: "gpt-4o", label: "GPT-4o" },
  ],
  google_ai: [
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  ],
  ollama: [
    { value: "llama-3.1-70b", label: "Llama 3.1 70B (Local)" },
  ],
};
