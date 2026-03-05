/**
 * SettingsPanel — admin settings for provider, privacy mode, and budgets.
 */

import { useSettingsStore } from "../../store/settings";
import { ModelSelector } from "./ModelSelector";

export function SettingsPanel() {
  const settings = useSettingsStore((s) => s.settings);
  const setSettings = useSettingsStore((s) => s.setSettings);

  return (
    <div aria-label="Settings Panel">
      <h2>Settings</h2>

      <ModelSelector />

      <div>
        <label htmlFor="privacy-mode">Privacy Mode</label>
        <select
          id="privacy-mode"
          value={settings.privacy_mode}
          onChange={(e) =>
            setSettings({
              privacy_mode: e.target.value as "private" | "external",
            })
          }
        >
          <option value="private">Private</option>
          <option value="external">External</option>
        </select>
      </div>

      <div>
        <label htmlFor="daily-cap">Daily Token Cap</label>
        <input
          id="daily-cap"
          type="number"
          value={settings.daily_token_cap}
          onChange={(e) =>
            setSettings({ daily_token_cap: Number(e.target.value) })
          }
        />
      </div>

      <div>
        <label htmlFor="monthly-cap">Monthly Token Cap</label>
        <input
          id="monthly-cap"
          type="number"
          value={settings.monthly_token_cap}
          onChange={(e) =>
            setSettings({ monthly_token_cap: Number(e.target.value) })
          }
        />
      </div>
    </div>
  );
}
