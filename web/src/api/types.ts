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
export type Provider = "ollama" | "anthropic" | "openai" | "google_ai";
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
  run_id: string;
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
  | "meta";

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
