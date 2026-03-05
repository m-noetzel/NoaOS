/**
 * ModelSelector — dropdown for selecting the default AI provider.
 */

import { useSettingsStore } from "../../store/settings";
import type { Settings } from "../../store/settings";

const PROVIDERS: Array<{ value: Settings["default_provider"]; label: string }> =
  [
    { value: "ollama", label: "Ollama (Local)" },
    { value: "anthropic", label: "Anthropic" },
    { value: "openai", label: "OpenAI" },
  ];

export function ModelSelector() {
  const provider = useSettingsStore((s) => s.settings.default_provider);
  const setSettings = useSettingsStore((s) => s.setSettings);

  return (
    <div>
      <label htmlFor="provider-select">Default Provider</label>
      <select
        id="provider-select"
        value={provider}
        onChange={(e) =>
          setSettings({
            default_provider: e.target
              .value as Settings["default_provider"],
          })
        }
      >
        {PROVIDERS.map((p) => (
          <option key={p.value} value={p.value}>
            {p.label}
          </option>
        ))}
      </select>
    </div>
  );
}
