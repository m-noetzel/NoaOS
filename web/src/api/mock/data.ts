import type {
  Thread, Run, Approval, QueueItem, MemoryFact,
  Artifact, CostRecord, CostSummary, RunEvent, Message, RunStep, StatusTransition,
} from "../types";

export const mockThreads: Thread[] = [
  { id: "t1", title: "Research AI safety papers", created_at: "2026-03-05T10:00:00Z", updated_at: "2026-03-05T10:30:00Z", message_count: 4 },
  { id: "t2", title: "Draft quarterly report", created_at: "2026-03-04T14:00:00Z", updated_at: "2026-03-04T15:00:00Z", message_count: 8 },
  { id: "t3", title: "Code review: auth module", created_at: "2026-03-03T09:00:00Z", updated_at: "2026-03-03T09:45:00Z", message_count: 3 },
];

export const mockMessages: Message[] = [
  { id: "m1", thread_id: "t1", role: "user", content: "Find recent papers on AI alignment published in 2026", created_at: "2026-03-05T10:00:00Z", run_id: "r1" },
  { id: "m2", thread_id: "t1", role: "assistant", content: "I found several recent papers on AI alignment. Here are the key ones:\n\n1. **Constitutional AI v2** — Anthropic, Jan 2026\n2. **Scalable Oversight** — DeepMind, Feb 2026\n3. **Reward Modeling at Scale** — OpenAI, Mar 2026\n\nWould you like me to summarize any of these?", created_at: "2026-03-05T10:01:00Z", run_id: "r1" },
  { id: "m3", thread_id: "t1", role: "user", content: "Summarize the first one", created_at: "2026-03-05T10:05:00Z", run_id: "r2" },
  { id: "m4", thread_id: "t1", role: "assistant", content: "**Constitutional AI v2** proposes an improved framework for training AI systems using a set of principles (a \"constitution\") to guide self-improvement...", created_at: "2026-03-05T10:06:00Z", run_id: "r2" },
];

// Step-level cost breakdown for r1
const r1Steps: RunStep[] = [
  { step_id: "s1", name: "Planner", tokens_in: 80, tokens_out: 120, cost: 0.0002 + 0.0018, duration_ms: 1200 },
  { step_id: "s2", name: "web_search", tokens_in: 120, tokens_out: 30, cost: 0.0004 + 0.0005, duration_ms: 2100 },
  { step_id: "s3", name: "arxiv_search", tokens_in: 90, tokens_out: 45, cost: 0.0003 + 0.0007, duration_ms: 3200 },
  { step_id: "s4", name: "google_scholar", tokens_in: 60, tokens_out: 25, cost: 0.0002 + 0.0004, duration_ms: 2800 },
  { step_id: "s5", name: "paper_extractor", tokens_in: 400, tokens_out: 550, cost: 0.0012 + 0.0083, duration_ms: 6500 },
  { step_id: "s6", name: "Final response", tokens_in: 800, tokens_out: 2700, cost: 0.0024 + 0.0405, duration_ms: 4300 },
];

const r1StatusHistory: StatusTransition[] = [
  { status: "queued", timestamp: "2026-03-05T10:00:28Z" },
  { status: "running", timestamp: "2026-03-05T10:00:30Z" },
  { status: "completed", timestamp: "2026-03-05T10:01:00Z" },
];

const r1CostTotal = r1Steps.reduce((s, st) => s + st.cost, 0);

export const mockRuns: Run[] = [
  {
    id: "r1", thread_id: "t1", status: "completed",
    summary: "Searched the web and analyzed 3 papers",
    risk_tier: "low", privacy_mode: "external",
    model: "claude-3.5-sonnet", provider: "anthropic",
    tokens_in: r1Steps.reduce((s, st) => s + st.tokens_in, 0),
    tokens_out: r1Steps.reduce((s, st) => s + st.tokens_out, 0),
    cost_usd: r1CostTotal,
    created_at: "2026-03-05T10:00:30Z", updated_at: "2026-03-05T10:01:00Z",
    duration_ms: 30000,
    steps: r1Steps,
    status_history: r1StatusHistory,
  },
  {
    id: "r2", thread_id: "t1", status: "completed",
    summary: "Summarized Constitutional AI v2 paper",
    risk_tier: "low", privacy_mode: "external",
    model: "claude-3.5-sonnet", provider: "anthropic",
    tokens_in: 800, tokens_out: 2100, cost_usd: 0.012,
    created_at: "2026-03-05T10:05:30Z", updated_at: "2026-03-05T10:06:00Z",
    duration_ms: 30000,
    status_history: [
      { status: "queued", timestamp: "2026-03-05T10:05:28Z" },
      { status: "running", timestamp: "2026-03-05T10:05:30Z" },
      { status: "completed", timestamp: "2026-03-05T10:06:00Z" },
    ],
  },
  {
    id: "r3", thread_id: "t2", status: "running",
    summary: "Generate quarterly financial charts",
    risk_tier: "medium", privacy_mode: "private",
    model: "gpt-4o", provider: "openai",
    tokens_in: 2400, tokens_out: 0, cost_usd: 0.024,
    created_at: "2026-03-04T14:30:00Z", updated_at: "2026-03-04T14:30:00Z",
    duration_ms: 0,
    status_history: [
      { status: "queued", timestamp: "2026-03-04T14:29:55Z" },
      { status: "running", timestamp: "2026-03-04T14:30:00Z" },
    ],
  },
  {
    id: "r4", thread_id: "t2", status: "failed",
    summary: "Export report to PDF",
    risk_tier: "high", privacy_mode: "private",
    model: "gpt-4o", provider: "openai",
    tokens_in: 500, tokens_out: 100, cost_usd: 0.006,
    created_at: "2026-03-04T14:45:00Z", updated_at: "2026-03-04T14:46:00Z",
    duration_ms: 60000,
    status_history: [
      { status: "queued", timestamp: "2026-03-04T14:44:55Z" },
      { status: "running", timestamp: "2026-03-04T14:45:00Z" },
      { status: "waiting_for_approval", timestamp: "2026-03-04T14:45:20Z", reason: "High-risk tool execution" },
      { status: "running", timestamp: "2026-03-04T14:45:35Z" },
      { status: "failed", timestamp: "2026-03-04T14:46:00Z", reason: "PDF generation service unavailable" },
    ],
  },
  {
    id: "r5", thread_id: "t3", status: "queued",
    summary: "Analyze auth module code",
    risk_tier: "low", privacy_mode: "private",
    model: "llama-3.1-70b", provider: "ollama",
    tokens_in: 0, tokens_out: 0, cost_usd: 0,
    created_at: "2026-03-03T09:00:00Z", updated_at: "2026-03-03T09:00:00Z",
    duration_ms: 0,
    status_history: [
      { status: "queued", timestamp: "2026-03-03T09:00:00Z" },
    ],
  },
];

export const mockRunEvents: RunEvent[] = [
  // Run r1
  { id: "e1", run_id: "r1", type: "message_received", data: { text: "Find recent papers on AI alignment published in 2026" }, created_at: "2026-03-05T10:00:30Z" },
  {
    id: "e2", run_id: "r1", type: "planner_step",
    data: {
      step: "Planning request",
      description: "Analyzing user intent and determining execution plan",
      strategy_summary: "Search multiple academic sources in parallel, extract paper content, then synthesize findings.",
      selected_tools: ["web_search", "arxiv_search", "google_scholar", "paper_extractor"],
      parallel_groups: [{ group_id: "search", tools: ["web_search", "arxiv_search", "google_scholar"] }],
      tokens_in: 80, tokens_out: 120, duration_ms: 1200,
    },
    created_at: "2026-03-05T10:00:31Z",
  },
  { id: "e3", run_id: "r1", type: "tool_called", data: { tool_name: "web_search", args: { query: "AI alignment papers 2026" }, parallel_group: "search" }, created_at: "2026-03-05T10:00:33Z" },
  { id: "e3b", run_id: "r1", type: "tool_called", data: { tool_name: "arxiv_search", args: { query: "AI alignment 2026", max_results: 10 }, parallel_group: "search" }, created_at: "2026-03-05T10:00:33Z" },
  { id: "e3c", run_id: "r1", type: "tool_called", data: { tool_name: "google_scholar", args: { query: "AI alignment safety 2026", num_results: 5 }, parallel_group: "search" }, created_at: "2026-03-05T10:00:33Z" },
  { id: "e5", run_id: "r1", type: "tool_result", data: { tool_name: "web_search", result: "Found 12 results across multiple sources", tokens_in: 120, tokens_out: 30, duration_ms: 2100, parallel_group: "search" }, created_at: "2026-03-05T10:00:35Z" },
  { id: "e5b", run_id: "r1", type: "tool_result", data: { tool_name: "arxiv_search", result: "Found 8 matching preprints", tokens_in: 90, tokens_out: 45, duration_ms: 3200, parallel_group: "search" }, created_at: "2026-03-05T10:00:36Z" },
  { id: "e5c", run_id: "r1", type: "tool_result", data: { tool_name: "google_scholar", result: "Found 5 cited papers", tokens_in: 60, tokens_out: 25, duration_ms: 2800, parallel_group: "search" }, created_at: "2026-03-05T10:00:36Z" },
  { id: "e7", run_id: "r1", type: "tool_called", data: { tool_name: "paper_extractor", args: { urls: ["https://arxiv.org/abs/2026.01234", "https://arxiv.org/abs/2026.05678", "https://arxiv.org/abs/2026.09012"] } }, created_at: "2026-03-05T10:00:45Z" },
  { id: "e8", run_id: "r1", type: "tool_result", data: { tool_name: "paper_extractor", result: "Extracted 3 papers successfully", tokens_in: 400, tokens_out: 550, duration_ms: 6500 }, created_at: "2026-03-05T10:00:52Z" },
  { id: "e9", run_id: "r1", type: "planner_step", data: { step: "Writing response", description: "Composing summary of findings", tokens_in: 50, tokens_out: 30, duration_ms: 800 }, created_at: "2026-03-05T10:00:53Z" },
  { id: "e10", run_id: "r1", type: "result_ready", data: { response_text: "I found several recent papers on AI alignment...", tokens_in: 800, tokens_out: 2700, duration_ms: 4300 }, created_at: "2026-03-05T10:01:00Z" },

  // Run r2
  { id: "e11", run_id: "r2", type: "message_received", data: { text: "Summarize the first one" }, created_at: "2026-03-05T10:05:30Z" },
  {
    id: "e12", run_id: "r2", type: "planner_step",
    data: {
      step: "Planning request",
      description: "Identifying target paper for summarization",
      strategy_summary: "Retrieve cached paper content and generate structured summary.",
      selected_tools: [],
      parallel_groups: [],
      tokens_in: 60, tokens_out: 80, duration_ms: 900,
    },
    created_at: "2026-03-05T10:05:31Z",
  },
  { id: "e13", run_id: "r2", type: "planner_step", data: { step: "Reading paper", description: "Processing Constitutional AI v2 full text", tokens_in: 400, tokens_out: 50, duration_ms: 2000 }, created_at: "2026-03-05T10:05:33Z" },
  { id: "e14", run_id: "r2", type: "planner_step", data: { step: "Writing response", description: "Generating structured summary", tokens_in: 200, tokens_out: 1800, duration_ms: 4500 }, created_at: "2026-03-05T10:05:50Z" },
  { id: "e15", run_id: "r2", type: "result_ready", data: { response_text: "Constitutional AI v2 proposes an improved framework...", tokens_in: 140, tokens_out: 170, duration_ms: 2100 }, created_at: "2026-03-05T10:06:00Z" },
];

export const mockApprovals: Approval[] = [
  {
    id: "a1", run_id: "r3", node_id: "n1",
    risk_tier: "high",
    tool_name: "db_migrate",
    tool_args: { migration: "add_role_column", target: "production" },
    preview_text: "Execute database migration on production server",
    status: "pending", created_at: "2026-03-05T11:00:00Z",
  },
  {
    id: "a2", run_id: "r4", node_id: "n2",
    risk_tier: "critical",
    tool_name: "send_email",
    tool_args: { to: "all-company@acme.com", subject: "Q1 2026 Report", template: "quarterly_report" },
    preview_text: "Send email to all-company distribution list",
    status: "pending", created_at: "2026-03-05T11:15:00Z",
  },
  {
    id: "a3", run_id: "r1", node_id: "n3",
    risk_tier: "medium",
    tool_name: "external_api",
    tool_args: { endpoint: "https://api.service.com/data", method: "GET" },
    preview_text: "Access external API with user credentials",
    status: "approved", created_at: "2026-03-05T09:00:00Z",
    decided_at: "2026-03-05T09:01:00Z", decided_by: "admin@acme.com",
  },
];

export const mockQueue: QueueItem[] = [
  { id: "q1", run_id: "r3", status: "active", privacy_mode: "private", position: 0, estimated_wait: 0, created_at: "2026-03-05T11:00:00Z" },
  { id: "q2", run_id: "r5", status: "queued", privacy_mode: "private", position: 1, estimated_wait: 30, created_at: "2026-03-05T11:01:00Z" },
  { id: "q3", run_id: "r4", status: "queued", privacy_mode: "external", position: 2, estimated_wait: 60, created_at: "2026-03-05T11:02:00Z" },
];

export const mockFacts: MemoryFact[] = [
  { id: "f1", fact: "User prefers concise summaries over detailed explanations", category: "preference", source_thread_id: "t1", auto_extracted: true, status: "pending", created_at: "2026-03-05T10:30:00Z" },
  { id: "f2", fact: "User works on AI safety research", category: "context", source_thread_id: "t1", auto_extracted: true, status: "pending", created_at: "2026-03-05T10:31:00Z" },
  { id: "f3", fact: "User's company fiscal year ends in March", category: "organization", source_thread_id: "t2", auto_extracted: false, status: "approved", created_at: "2026-03-04T15:00:00Z" },
  { id: "f4", fact: "Preferred code review format: inline comments with severity levels", category: "preference", source_thread_id: "t3", auto_extracted: true, status: "approved", created_at: "2026-03-03T10:00:00Z" },
];

export const mockArtifacts: Artifact[] = [
  { id: "art1", run_id: "r1", type: "file", name: "ai_safety_papers.md", content: "# AI Safety Papers 2026\n\n1. Constitutional AI v2\n2. Scalable Oversight\n3. Reward Modeling at Scale", created_at: "2026-03-05T10:01:00Z" },
  { id: "art2", run_id: "r3", type: "diff", name: "schema_migration.sql", content: "--- a/schema.sql\n+++ b/schema.sql\n@@ -1,3 +1,5 @@\n CREATE TABLE users (\n   id UUID PRIMARY KEY,\n+  role TEXT NOT NULL DEFAULT 'user',\n+  updated_at TIMESTAMP DEFAULT NOW(),\n   name TEXT\n );", created_at: "2026-03-04T14:35:00Z" },
  { id: "art3", run_id: "r2", type: "preview", name: "summary_preview.html", content: "<h2>Constitutional AI v2</h2><p>An improved framework for training AI systems...</p>", created_at: "2026-03-05T10:06:00Z" },
];

export const mockCostRecords: CostRecord[] = [
  { run_id: "r1", tokens_in: 1550, tokens_out: 3470, cost_usd: r1CostTotal, provider: "anthropic", model: "claude-3.5-sonnet", created_at: "2026-03-05T10:01:00Z" },
  { run_id: "r2", tokens_in: 800, tokens_out: 2100, cost_usd: 0.012, provider: "anthropic", model: "claude-3.5-sonnet", created_at: "2026-03-05T10:06:00Z" },
  { run_id: "r3", tokens_in: 2400, tokens_out: 0, cost_usd: 0.024, provider: "openai", model: "gpt-4o", created_at: "2026-03-04T14:30:00Z" },
  { run_id: "r4", tokens_in: 500, tokens_out: 100, cost_usd: 0.006, provider: "openai", model: "gpt-4o", created_at: "2026-03-04T14:46:00Z" },
];

export const mockCostSummary: CostSummary[] = [
  { period: "session", tokens_in: 4900, tokens_out: 5600, cost_usd: 0.06 },
  { period: "daily", tokens_in: 4900, tokens_out: 5600, cost_usd: 0.06, budget_limit_usd: 5.0 },
  { period: "monthly", tokens_in: 45000, tokens_out: 62000, cost_usd: 0.54, budget_limit_usd: 50.0 },
];
