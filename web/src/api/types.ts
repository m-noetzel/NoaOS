// ============================================================
// Noa API Types
// TODO: Replace with auto-generated types from OpenAPI spec
// ============================================================

// --- Envelope (matches backend Envelope schema §25.3) ---

export interface ApiError {
  code: string;
  message: string;
  details?: unknown[];
}

export interface ApiResponse<T> {
  ok: boolean;
  data: T;
  error: ApiError | null;
  trace_id: string;
}

// --- Auth ---

export interface LoginRequest {
  email: string;
  password: string;
  device_id: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
  device_id: string;
}

// --- Enums ---

export type RunStatus = "queued" | "pending" | "running" | "waiting_for_approval" | "completed" | "failed" | "cancelled";
export type RiskTier = "low" | "medium" | "high" | "critical";
export type PrivacyMode = "private" | "external";
export type Provider = "ollama" | "anthropic" | "openai" | "google_ai" | "kimi";
export type ReplayMode = "tool_only" | "downstream" | "full";

// --- Pricing ---

export interface PricingModel {
  provider: Provider;
  model: string;
  input_price_per_m: number;  // USD per 1M input tokens
  output_price_per_m: number; // USD per 1M output tokens
}

// --- Status History ---

export interface StatusTransition {
  status: RunStatus;
  timestamp: string;
  reason?: string;
}

// --- Domain Models ---

export interface Thread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  domain?: PrivacyMode;
}

export interface Message {
  id: string;
  thread_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  run_id?: string;
}

export interface RunStep {
  step_id: string;
  name: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  duration_ms: number;
}

export interface ReplayInfo {
  original_run_id: string;
  from_node?: string;
  mode: ReplayMode;
}

export interface Run {
  id: string;
  thread_id: string;
  status: RunStatus;
  summary: string;
  risk_tier: RiskTier;
  privacy_mode: PrivacyMode;
  model: string;
  provider: Provider;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  created_at: string;
  updated_at: string;
  duration_ms?: number;
  status_history?: StatusTransition[];
  steps?: RunStep[];
  replay_of?: ReplayInfo;
}

export interface RunEvent {
  id: string;
  run_id: string;
  type: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface Approval {
  id: string;
  run_id: string;
  node_id?: string;
  risk_tier: RiskTier;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  preview_text: string;
  status: "pending" | "approved" | "denied";
  created_at: string;
  decided_at?: string;
  decided_by?: string;
}

export interface ApprovalDecision {
  decision: "approved" | "denied";
}

export interface QueueItem {
  id: string;
  run_id: string;
  status: "queued" | "active";
  privacy_mode: PrivacyMode;
  position: number;
  estimated_wait: number;
  created_at: string;
}

export interface MemoryFact {
  id: string;
  fact: string;
  category: string;
  source_thread_id: string;
  auto_extracted: boolean;
  status: "pending" | "approved";
  created_at: string;
}

export interface Artifact {
  id: string;
  run_id: string;
  type: "file" | "diff" | "export" | "preview";
  name: string;
  content: string;
  mime_type?: string;
  created_at: string;
}

export interface CostRecord {
  run_id: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  provider: Provider;
  model: string;
  created_at: string;
}

export interface CostSummary {
  period: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  budget_limit_usd?: number;
}

// FB1: User feedback ratings
export interface RatingRequest {
  run_id: string;
  rating: 1 | -1;
}

export interface RatingResponse {
  run_id: string;
  rating: 1 | -1;
}

export interface RatingSummary {
  positive: number;
  negative: number;
  total: number;
  score: number;
  period: string;
}

// EV2: Analytics eval trends
export interface EvalTrendItem {
  key: string;
  avg_score: number;
  count: number;
}

export interface DivergenceAlert {
  dimension: string;
  eval_avg: number;
  user_avg: number;
  divergence: number;
}

export interface EvalTrends {
  period: string;
  group_by: string;
  data: EvalTrendItem[];
  overall_avg: number;
  divergence_alerts: DivergenceAlert[];
}

export interface WorstDimension {
  dimension: string;
  avg_score: number;
  count: number;
}

export interface WorstDimensions {
  period: string;
  worst: WorstDimension[];
}

// MC1: Per-node model configuration
export interface NodeModelsConfig {
  classifier?: string;
  planner?: string;
  agent?: string;
  evaluator?: string;
}

export interface UserSettings {
  default_model: string;
  default_provider: string;
  default_privacy_mode: PrivacyMode;
  budget_daily_usd: number;
  budget_monthly_usd: number;
  system_prompt: string | null;
  temperature: number | null;
  max_tokens: number | null;
  anthropic_api_key: string | null;
  openai_api_key: string | null;
  google_client_id: string | null;
  google_client_secret: string | null;
  notion_token: string | null;
  tavily_api_key: string | null;
  ollama_base_url: string | null;
  // UX-M2: Governance
  approvals_enabled?: boolean;
  // UX-M4: Agent limits
  max_tool_calls?: number;
  max_retries?: number;
  timeout_seconds?: number;
  // MC1: Per-node model configuration
  node_models?: NodeModelsConfig | null;
  // PC1: User-configurable private keywords
  private_keywords?: string[] | null;
}

// UX-M10: Tool scope
export interface ToolScope {
  name: string;
  tools: string[];
  is_custom: boolean;
}

// --- Audit ---

export interface AuditEntry {
  id: string;
  timestamp: string;
  user_id: string;
  session_id: string;
  device_id: string;
  trace_id: string;
  domain: string;
  model_provider: string;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: string;
  tool_name: string | null;
  tool_args: Record<string, unknown> | null;
  tool_result_summary: string | null;
  side_effects: Record<string, unknown> | null;
  privacy_classification: string;
  classification_confidence: number;
  classification_reasoning: string | null;
  previous_entry_hash: string | null;
}

export interface AuditEntriesResponse {
  entries: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditVerifyResponse {
  valid: boolean;
  entries_checked: number;
  broken_at_entry_id: string | null;
  error?: string;
}

// --- SSE Events ---

// SSE event types — spec §22.2 + extended for UI
export type SSEEventType =
  // Spec-mandated (§22.2)
  | "message_received"
  | "classification_done"
  | "step_started"
  | "token_stream"
  | "tool_called"
  | "tool_result"
  | "approval_requested"
  | "approval_received"
  | "artifact_created"
  | "result_ready"
  | "error"
  // Extended for UI state
  | "planner_step"
  | "run_started"
  | "run_completed"
  | "run_failed"
  | "run_cancelled"
  | "meta"
  // UX-H10: Tool execution lifecycle events from agent
  | "tool_start"
  | "tool_end"
  | "step"
  // OV8: ask_user interrupt
  | "ask_user";

export interface SSEEvent {
  event: SSEEventType;
  data: Record<string, unknown>;
}

// --- Chat Request ---

export interface ChatRequest {
  message: string;
  thread_id?: string;
  privacy_mode: PrivacyMode;
  model: string;
  provider: Provider;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
}

// --- Replay Request ---

export interface ReplayRequest {
  from_node?: string;
  mode: ReplayMode;
}
