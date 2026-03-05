/**
 * Cost Dashboard — displays per-message cost breakdown and budget progress bars.
 */

import { useSettingsStore } from "../../store/settings";

function ProgressBar({
  label,
  used,
  limit,
  costUsd,
}: {
  label: string;
  used: number;
  limit: number;
  costUsd: number;
}) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const exceeded = pct >= 100;
  const warning = pct >= 80 && !exceeded;

  return (
    <div role="group" aria-label={`${label} budget`}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span>
          {label}: {used.toLocaleString()} / {limit.toLocaleString()} tokens
        </span>
        <span>${costUsd.toFixed(4)}</span>
      </div>
      <div
        role="progressbar"
        aria-label={`${label} usage`}
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        style={{
          width: "100%",
          height: "20px",
          backgroundColor: "#e0e0e0",
          borderRadius: "4px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            backgroundColor: exceeded
              ? "#d32f2f"
              : warning
                ? "#f9a825"
                : "#388e3c",
            transition: "width 0.3s ease",
          }}
        />
      </div>
      {warning && (
        <p role="alert" style={{ color: "#f9a825" }}>
          Warning: Daily usage exceeds 80% of budget
        </p>
      )}
      {exceeded && (
        <p role="alert" style={{ color: "#d32f2f" }}>
          Budget limit reached
        </p>
      )}
    </div>
  );
}

export function CostDashboard() {
  const usage = useSettingsStore((s) => s.usage);

  return (
    <div aria-label="Cost Dashboard">
      <h2>Cost Dashboard</h2>

      <section aria-label="Budget Overview">
        <ProgressBar
          label="Daily"
          used={usage.daily.used}
          limit={usage.daily.limit}
          costUsd={usage.daily.cost_usd}
        />
        <ProgressBar
          label="Monthly"
          used={usage.monthly.used}
          limit={usage.monthly.limit}
          costUsd={usage.monthly.cost_usd}
        />
      </section>

      <section aria-label="Message Breakdown">
        <h3>Per-Message Breakdown</h3>
        {usage.messages.length === 0 ? (
          <p>No messages yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Prompt Tokens</th>
                <th>Completion Tokens</th>
                <th>Cost (USD)</th>
              </tr>
            </thead>
            <tbody>
              {usage.messages.map((msg, idx) => (
                <tr key={idx}>
                  <td>{msg.model}</td>
                  <td>{msg.prompt_tokens}</td>
                  <td>{msg.completion_tokens}</td>
                  <td>${msg.cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
