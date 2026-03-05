import { useState } from "react";
import { ChatView } from "./components/Chat/ChatView";
import { RunTimeline } from "./components/Run/RunTimeline";
import { RunHistory } from "./components/Run/RunHistory";
import { ApprovalPanel } from "./components/Approval/ApprovalPanel";
import { TaskQueue } from "./components/Queue/TaskQueue";
import { MemoryAudit } from "./components/Memory/MemoryAudit";
import { CostDashboard } from "./components/Cost/CostDashboard";
import { SettingsPanel } from "./components/Settings/SettingsPanel";
import { ArtifactViewer } from "./components/Artifacts/ArtifactViewer";
import { useRunStore } from "./store/runs";

type View =
  | "chat"
  | "runs"
  | "approvals"
  | "queue"
  | "memory"
  | "costs"
  | "settings"
  | "artifacts";

const NAV_ITEMS: { key: View; label: string }[] = [
  { key: "chat", label: "Chat" },
  { key: "runs", label: "Runs" },
  { key: "approvals", label: "Approvals" },
  { key: "queue", label: "Queue" },
  { key: "memory", label: "Memory" },
  { key: "costs", label: "Costs" },
  { key: "settings", label: "Settings" },
  { key: "artifacts", label: "Artifacts" },
];

export function App() {
  const [view, setView] = useState<View>("chat");
  const activeRun = useRunStore((s) => s.getActiveRun());
  const runs = useRunStore((s) => s.runs);
  const setActiveRun = useRunStore((s) => s.setActiveRun);

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "system-ui, sans-serif" }}>
      {/* Sidebar */}
      <nav
        style={{
          width: 200,
          background: "#1a1a2e",
          color: "#fff",
          padding: "1rem 0",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, padding: "0 1rem", margin: "0 0 1rem" }}>
          Noa
        </h1>
        {NAV_ITEMS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setView(key)}
            style={{
              background: view === key ? "rgba(255,255,255,0.15)" : "transparent",
              color: "#fff",
              border: "none",
              padding: "0.6rem 1rem",
              textAlign: "left",
              cursor: "pointer",
              fontSize: "0.9rem",
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* Main content */}
      <main style={{ flex: 1, overflow: "auto", padding: "1rem" }}>
        {view === "chat" && <ChatView />}
        {view === "runs" && (
          <div style={{ display: "flex", gap: "1rem" }}>
            <div style={{ width: 300 }}>
              <RunHistory
                runs={runs}
                activeRunId={activeRun?.id ?? null}
                onSelectRun={setActiveRun}
              />
            </div>
            <div style={{ flex: 1 }}>
              {activeRun ? (
                <RunTimeline run={activeRun} />
              ) : (
                <p style={{ color: "#888" }}>Select a run to view its timeline.</p>
              )}
            </div>
          </div>
        )}
        {view === "approvals" && <ApprovalPanel />}
        {view === "queue" && <TaskQueue />}
        {view === "memory" && <MemoryAudit />}
        {view === "costs" && <CostDashboard />}
        {view === "settings" && <SettingsPanel />}
        {view === "artifacts" && <ArtifactViewer />}
      </main>
    </div>
  );
}
