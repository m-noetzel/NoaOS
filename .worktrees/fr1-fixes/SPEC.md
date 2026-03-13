# SPEC.md
## Noa — Personal Agent for Decision & Execution
### Version: 5.0
### Date: 2026-03-04

---

# 1. Purpose

Noa is a **secure, dual-domain personal AI agent** running on local hardware. Noa owns the decision layer — it interprets intent, routes tasks, enforces policy, and orchestrates execution across two strictly isolated domains:

- A **Private Domain** (sealed enclave, no external network calls, local-only AI processing)
- An **External Domain** (uses remote LLM APIs, tool integrations, coding execution)

Both domains run entirely on local hardware. Nothing runs in the cloud. "External" refers only to the LLM API providers (Anthropic, OpenAI) that are called over HTTPS — all orchestration, execution, and data storage remain local.

The system starts on a **single machine** with container-based domain isolation (Phase 1) and is designed to scale to a **dual-machine setup** with physical domain isolation (Phase 2) without architectural changes.

Noa operates through:

- A **LangGraph-based Orchestrator** as the control plane
- A web-based chat interface (primary), a mobile client (PWA → native iOS), and a CLI
- Strict cost, security, and policy enforcement

The system must provide:

- Local private data management using only local models
- Controlled coding, reasoning, and tool workflows using remote LLM APIs
- Integration with external productivity services (Calendar, Email, Notion)
- Persistent short-term and long-term agent memory
- Explicit data boundary enforcement with enforceable contracts
- Auditable, policy-driven execution
- Deterministic cost control
- A unified Run/Event model for real-time task tracking across all clients

---

# 2. Execution Model: Governed Agentic Execution

**Noa is not an autonomous agent. It is a governed execution engine in which all side-effecting behavior is bounded by deterministic orchestration and policy enforcement.**

This is the foundational invariant of the entire system. Every other section in this spec depends on it.

## 2.1 Deterministic Outer Shell

The orchestration layer is deterministic and predefined. The LLM does not control it.

- **Workflow topology is fixed**: The LangGraph state machine defines the node sequence (router → agent → tools → responder). The LLM cannot add, remove, or reorder nodes.
- **Tool allowlists are static per workflow**: The set of tools available to any given step is defined at graph compile time. The LLM cannot invoke tools not in its allowlist.
- **Approval checkpoints are explicit**: Every side-effecting action passes through a risk-tier check. The LLM cannot skip or defer approval gates.
- **Privacy routing is enforced before execution**: Domain classification and network enforcement happen before the LLM sees the task. The LLM cannot change its own routing.
- **Cost and iteration limits are fixed**: Token caps, retry limits, and tool call budgets are enforced by the orchestrator, not requested by the LLM.

## 2.2 Bounded Inner Autonomy

Within a single orchestrated step, the LLM has bounded cognitive freedom:

**The LLM may:**

- Reason about the user's intent
- Generate arguments for tool calls
- Synthesize structured outputs (answers, summaries, code)
- Choose parameters for an allowed tool (e.g., which calendar date to query)
- Decide *which* allowed tool to call (from the step's allowlist)

**The LLM may NOT:**

- Invent new workflow stages or nodes
- Bypass or defer approval checkpoints
- Escalate model tier outside policy (e.g., request Claude Opus when policy says Haiku)
- Change domain routing (private ↔ external)
- Execute tools not in the current step's allowlist
- Modify its own system prompt or tool definitions
- Persist state outside the checkpointer (no side-channel memory)

## 2.3 Why This Matters

Without this invariant:

| If the LLM could... | Then... |
|---|---|
| Control execution order | Auditability breaks — log replay becomes non-deterministic |
| Skip approval gates | Policy enforcement weakens — risk tiers become advisory |
| Choose its own model tier | Cost control becomes probabilistic — caps can be circumvented |
| Override privacy routing | Privacy model fails — private data could reach external APIs |
| Add workflow stages | Attack surface expands — prompt injection gains execution authority |

This separation ensures:

- **Auditability**: Every execution path is reproducible from the graph definition + state
- **Policy compliance**: Side effects are always gated by the approval framework
- **Privacy enforcement**: Domain routing is a system-level decision, not an LLM decision
- **Predictable cost**: Token budgets are enforced by the orchestrator, not negotiated by the model
- **Reproducible execution paths**: Same input state → same graph traversal → same policy checks

## 2.4 Shell Execution Invariant

**Shell execution is permitted only within the external coding container. It must be sandboxed, workspace-scoped, resource-capped, and fully isolated from all private-domain storage. No shell execution is allowed in the private domain.**

This is a hard rule, not a guideline. The architecture's strongest guarantees — domain separation, no internet egress from private domain, deterministic orchestration, and explicit policy enforcement — all break if unrestricted shell access exists outside the coding sandbox.

| Constraint | Enforcement |
|---|---|
| **Location** | External coding container only. Never in the private domain. |
| **Workspace scope** | All shell commands run inside a chroot/namespace rooted at the coding workspace. No access to paths outside the workspace. |
| **Resource caps** | CPU time limit per command (default: 5 min). Memory limit per command (default: 4 GB). Max concurrent shells: 2. |
| **Network** | Inherits external container egress rules (allowlisted domains only). |
| **Filesystem** | Read-write only within workspace. Read-only root. No access to Noa API config, secrets, or audit logs. |
| **Private domain isolation** | No mount, no network route, no RPC path from the coding shell to the private domain container or any private-domain volume. |
| **Audit** | Every shell command and its exit code are logged in the audit trail. |

---

# 3. Agent Identity

**Noa** is the user-facing agent. All interactions — web UI, mobile, CLI, or API — are mediated through Noa. Noa is not a wrapper around a single model; it is the orchestration identity that decides *which* model, *which* domain, and *which* policy applies to every request.

**Target user:** The owner-operator — a single technical user who runs Noa on their own hardware for personal productivity, coding assistance, and private data management. The system is designed with multi-user extensibility in mind (see Section 33).

Key principles:

- Noa **decides**, workers **execute**
- Noa never exposes internal routing to the user
- Noa presents a single coherent agent persona regardless of which backend fulfilled the task
- Noa owns the conversation state, task history, and approval context

---

# 4. Deployment Model

Noa uses a **phased deployment model** that separates logical architecture from physical infrastructure. The domain boundary is defined by contracts (Section 9), not by hardware. This allows the system to start on a single machine and scale to physical isolation without architectural changes.

## 4.1 Deployment Phases

| Phase | Infrastructure | Domain Isolation | Status |
|---|---|---|---|
| **Phase 1** | Single Mac (Apple Silicon, 64 GB+ RAM) | Container-based (Docker networks + volumes) | **Active** |
| **Phase 2** | Mac (control plane) + dedicated Mac (private enclave) | Physical (separate machines, mTLS over LAN) | Future |

### Phase 1: Single Machine (Active)

All services run as Docker containers on one Mac:

- **Control Plane**: Noa API (FastAPI), LangGraph Orchestrator, Postgres, Web UI
- **External Domain**: External worker container (LLM API calls, tool integrations, coding)
- **Private Domain**: Private worker container (Ollama, private memory, RAG)

Domain isolation is enforced via:
- Separate Docker networks (`noa-internal` for private, `noa-external` for external)
- Separate Docker volumes (private data volumes never mounted by external containers)
- The Noa API container bridges both networks and enforces the RPC contract
- The private container's Docker network has `internal: true` (no internet egress)

### Phase 2: Dual Machine (Future)

| Machine | Role | Specs | Always On? |
|---|---|---|---|
| **Mac Mini** | Control plane + external domain + coding | Standard config | Yes |
| **MacBook Pro** | Private domain (sealed enclave) | Apple M4, 64 GB RAM | On-demand |

The upgrade from Phase 1 to Phase 2 requires:
1. Move the private container to the MacBook Pro
2. Replace Docker network communication with mTLS over LAN
3. Enable Wake-on-LAN for on-demand activation
4. Apply pf firewall rules on the MacBook Pro (block all internet egress)
5. No changes to the RPC contract, API, or client code

## 4.2 Upgrade Path Invariant

**The RPC contract (Section 9) is the architectural boundary.** Whether that boundary is a Docker network or a physical LAN cable is a deployment detail. The contract, the API, and the client code do not change between phases.

## 4.3 Phase 1 Machine Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | Apple M-series | Apple M4 or later |
| RAM | 32 GB | 64 GB |
| Storage | 256 GB SSD | 512 GB+ NVMe |
| Network | LAN (for VPN access) | LAN + WireGuard |

RAM allocation (64 GB recommended):
- Ollama (private domain): up to 32 GB
- Postgres: 2 GB
- External worker: 4 GB
- Noa API + Orchestrator: 2 GB
- macOS + Docker overhead: 16 GB
- Coding workspace I/O: remaining

---

# 5. Authentication & Session Management

All access to Noa must be authenticated. Unauthenticated requests are rejected.

## 5.1 Access Channels

| Channel | Auth Method |
|---|---|
| Web UI (local network) | Session token via login (username + password or passkey) |
| Mobile App (PWA / native) | Same as Web UI (PWA) or OAuth2 device flow + biometric unlock (native) |
| CLI | API key stored in local keychain |
| API (programmatic) | Bearer token with scoped permissions |

## 5.2 Session Rules

- Sessions expire after a configurable idle timeout (default: 30 minutes)
- Each session is bound to a single device ID
- Concurrent sessions are allowed but logged
- Session tokens are JWTs signed with a local secret, never sent to external services
- Token refresh uses rotating refresh tokens (old token invalidated on use)
- Session state is stored in Postgres

## 5.3 Authentication Flow

```
Client → POST /api/v1/auth/login (credentials)
       ← 200 { access_token (15min), refresh_token (7d) }

Client → POST /api/v1/chat (Bearer access_token)
       ← SSE stream

Client → POST /api/v1/auth/refresh (refresh_token)
       ← 200 { new access_token, new refresh_token }
```

## 5.4 Revocation

- Logout invalidates all tokens for that session
- Admin can revoke all sessions for a device
- Compromised API keys can be rotated without affecting other sessions

---

# 6. Core Design Principles

## 6.1 Separation of Concerns

| Component | Domain | Responsibility |
|---|---|---|
| Noa (LangGraph Orchestrator) | Control Plane | Decision authority, routing, policy enforcement |
| External Worker | External | Remote LLM API calls, tool integrations, coding |
| Private Worker | Private | Local-only AI, private data, memory, RAG |
| Tool Integrations | External | Calendar, Email, Notion, Web Search |
| Memory & RAG | Private | Long-term memory, RAG, embeddings |
| Coding Worker | External | Git repos, test execution, diff generation |
| Policy Engine | Control Plane | Authorization + routing rules |
| Web UI | Control Plane | Chat interface, settings, monitoring |
| Mobile Client | Client | Chat, approvals, task monitoring, voice (native) |

Remote LLM APIs are **tools** that Noa invokes. They are not orchestrators.

---

## 6.2 Dual-Domain Architecture

### Domain A: Private (Sealed Enclave)

**Hard requirements:**

- No external network calls (no LLM API calls, no internet egress, no tool API calls)
- All inference via Ollama (local model runtime)
- Private data never leaves the private domain except as structured RPC responses
- Communication only with the control plane via the RPC contract
- Zero coding repos, zero build tools, zero test runners

Capabilities:

- Long-term memory storage and retrieval
- Local semantic search over stored facts
- RAG: document ingestion, embedding, and retrieval
- Planning & summarization over private data
- Local note processing

### Domain B: External (Remote LLM APIs + Coding)

**Supported LLM providers:**

- Anthropic (Claude)
- OpenAI (GPT-4o)
- User-selectable per request or via default setting

Allowed:

- HTTPS calls to LLM API providers (Anthropic, OpenAI)
- HTTPS calls to tool APIs (Google, Notion, Tavily)
- Git operations and coding workspace access
- Test execution and build commands
- Generating patches and diffs

Not allowed:

- Access to private data (except via RPC responses)
- Unrestricted filesystem access
- Arbitrary internet egress (allowlisted domains only)

---

# 7. System Architecture

## 7.1 High-Level Overview (Phase 1 — Single Machine)

```
User (Web UI / PWA on iPhone / CLI)
       ↓ HTTPS (LAN or VPN)
┌──────────────────────────────────────────────────┐
│               Host Machine (Mac)                  │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │  Docker Compose                             │  │
│  │                                             │  │
│  │  ┌───────────────────────────────────────┐  │  │
│  │  │ noa-api (FastAPI)                     │  │  │
│  │  │   ├── LangGraph Orchestrator          │  │  │
│  │  │   ├── Router Node                     │  │  │
│  │  │   ├── Agent Node (external LLM call)  │  │  │
│  │  │   ├── Tool Node (Calendar, Gmail...)  │  │  │
│  │  │   └── Responder Node (cost, format)   │  │  │
│  │  │ Networks: noa-internal + noa-external  │  │  │
│  │  └────────┬──────────────┬───────────────┘  │  │
│  │           │              │                   │  │
│  │     noa-internal    noa-external             │  │
│  │      (no inet)      (allowlisted)            │  │
│  │           │              │                   │  │
│  │  ┌────────┴────┐  ┌─────┴──────────────┐   │  │
│  │  │ private     │  │ external-worker    │   │  │
│  │  │ worker      │  │  + coding worker   │   │  │
│  │  │ (Ollama)    │  │                    │──►│Internet
│  │  │ Memory, RAG │  │  LLM APIs, tools   │   │  │
│  │  │ NO internet │  │                    │   │  │
│  │  └─────────────┘  └────────────────────┘   │  │
│  │                                             │  │
│  │  ┌─────────────┐                            │  │
│  │  │ Postgres    │  Canonical data store      │  │
│  │  │ (Docker)    │                            │  │
│  │  └─────────────┘                            │  │
│  └─────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

## 7.2 High-Level Overview (Phase 2 — Dual Machine)

```
User (Web UI / iOS App / CLI)
       ↓ HTTPS (LAN or VPN)
┌──────────────────────────────────────────────┐
│              Mac Mini (always on)              │
│                                                │
│  Noa API (FastAPI) → LangGraph Orchestrator    │
│       ├── Router Node                          │
│       ├── Agent Node (external LLM call)       │
│       ├── Tool Node (Calendar, Gmail, etc.)    │
│       ├── Coding Worker (repos, tests, diffs)  │
│       └── Responder Node (cost, format)        │
│                                                │
│  External Container (Docker)                   │
│       └── LLM API calls + tool execution       │
│                                                │
│  Postgres                                      │
│                                                │
│  Coding Workspace                              │
│       └── Git repos + build/test sandbox       │
└──────────────────┬─────────────────────────────┘
                   │ mTLS over LAN
┌──────────────────┴─────────────────────────────┐
│          MacBook Pro M4 64GB (on-demand)        │
│                                                 │
│  Private Container (Docker)                     │
│       ├── Ollama (local LLM runtime)            │
│       ├── Private data store (memory, embeds)   │
│       └── RAG document store                    │
│                                                 │
│  NO repos. NO internet. NO tool APIs.           │
└─────────────────────────────────────────────────┘
```

## 7.3 Allowed Network Flows

### Phase 1 (Single Machine)

| From | To | Allowed | Protocol |
|---|---|---|---|
| Web UI / Mobile | Noa API | Yes | HTTPS (LAN or VPN) |
| Noa API | Private Worker | Yes | HTTP over Docker internal network |
| Noa API | External Worker | Yes | HTTP over Docker external network |
| External Worker | Internet (allowlisted APIs) | Yes | HTTPS only |
| External Worker | Private Worker | **No** | Separate Docker networks, no route |
| Private Worker | Internet | **No** | Docker network `internal: true` |
| Private Worker | External Worker | **No** | Separate Docker networks, no route |

### Phase 2 (Dual Machine)

| From | To | Allowed | Protocol |
|---|---|---|---|
| Web UI / Mobile | Noa API (Mac Mini) | Yes | HTTPS (LAN or VPN) |
| Noa API (Mac Mini) | Private Container (MacBook Pro) | Yes | mTLS over LAN |
| Noa API (Mac Mini) | External Container (Mac Mini) | Yes | HTTP over Docker network |
| External Container | Internet (allowlisted APIs) | Yes | HTTPS only, DNS monitored |
| External Container | MacBook Pro | **No** | Blocked — separate network |
| Private Container | Internet | **No** | Blocked by pf (IPv4 + IPv6) |
| Private Container | External Container | **No** | Separate machines, no route |

---

# 8. Container Architecture

## 8.1 Private Container

### Must:

- Run Ollama as the local LLM runtime
- Be on the `noa-internal` Docker network only (Phase 1) or bind only to the mTLS listener (Phase 2)
- Have all internet egress blocked (Docker `internal: true` in Phase 1, pf firewall in Phase 2)
- Use a dedicated encrypted volume for all persistent private data
- Store long-term memory, embeddings, and RAG documents

### May:

- Use up to 32 GB RAM for Ollama (Phase 1) or 48 GB (Phase 2, dedicated machine)
- Use Apple Silicon GPU acceleration for local inference

### Must NOT:

- Reach any external IP address (IPv4 or IPv6)
- Resolve external DNS names
- Mount any filesystem from the external domain
- Store or access coding repositories
- Run build tools, test runners, or package managers
- **Execute shell commands of any kind** — no `/bin/sh`, no `exec`, no subprocess spawning (enforced via seccomp profile and read-only root filesystem)

### Local Model Supply Chain

- Only approved models may be loaded (pinned by name + SHA256 hash)
- Models are pulled once, verified, then the container runs air-gapped
- Model manifest is version-controlled alongside this spec
- No automatic model updates — all changes require explicit approval
- Verified model files are bind-mounted read-only into the container

### Container Hardening

- Read-only root filesystem (`--read-only`)
- All capabilities dropped (`--cap-drop=ALL`), only add back what Ollama requires
- No privileged mode
- Seccomp profile applied (default Docker profile minimum)
- No `--pid=host`, no `--network=host`
- Dedicated non-root user inside container

---

## 8.2 External Container

### Must:

- Have HTTPS egress to allowlisted domains only
- Be sandboxed (Docker with hardened config)
- Have limited filesystem mounts (coding workspace only)
- Enforce workspace root path — all file operations scoped to workspace
- Produce structured outputs (JSON)
- DNS queries logged for audit

### Must NOT:

- Mount any volume from the private domain
- Modify system files outside workspace
- Access secrets beyond scoped, short-lived credentials
- Communicate with the private container directly
- Access Noa API configuration, audit logs, or secrets directories from shell

### Shell Sandbox (Coding Worker)

Shell execution is permitted here — and **only** here — subject to:

- All commands run inside a namespace/chroot rooted at the coding workspace
- CPU time limit per command: 5 minutes (configurable)
- Memory limit per command: 4 GB (configurable)
- Max concurrent shells: 2
- No access to paths outside the workspace (enforced by mount namespace)
- Every command and exit code logged in the audit trail
- Inherits external container network rules (allowlisted egress only)

### Container Hardening

- Read-only root filesystem, dropped caps, non-root user
- Egress allowlist: `api.anthropic.com`, `api.openai.com`, `*.googleapis.com`, `api.notion.com`, `api.tavily.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`
- All other egress blocked via Docker network policy
- Coding workspace is the only writable volume

---

## 8.3 Inter-Domain Communication

The private and external domains never share volumes or Docker networks. All coordination goes through the Noa API via the Private Worker RPC contract (Section 9):

### Phase 1 (Single Machine)

```
Private Container ←── HTTP over Docker internal network ──→ Noa API ──→ External Container
```

- Noa API dispatches tasks to the private container via HTTP calls on the `noa-internal` Docker network
- Private container returns structured results — never raw private data
- Docker network isolation ensures no direct private ↔ external communication

### Phase 2 (Dual Machine)

```
MacBook Pro (Private) ←── mTLS over LAN ──→ Mac Mini (Noa API) ──→ External Container
```

- Noa API dispatches tasks to the MacBook Pro via mTLS HTTP calls conforming to the RPC contract
- mTLS with pre-provisioned client certificates (rotated annually)
- Discovery: Static IP or mDNS (`.local` hostname)
- Time sync: both machines use the same NTP source to prevent certificate validation failures
- If the MacBook Pro is unreachable, private tasks queue (see Section 17)

**In both phases**, task payloads are validated by the Policy Engine before dispatch, and the RPC contract is identical.

---

# 9. Private Worker RPC Contract

This is the enforceable boundary between the private domain and the control plane. Every field that crosses this boundary is specified here. **No other data may traverse this boundary.**

This contract is deployment-agnostic: it applies identically whether the boundary is a Docker network (Phase 1) or a physical LAN with mTLS (Phase 2).

## 9.1 Request Schema (Control Plane → Private Domain)

```json
{
  "request_id": "uuid",
  "idempotency_key": "uuid",
  "task_type": "remember | recall | rag_query | rag_ingest | summarize | search",
  "payload": {
    "query": "string (max 4096 chars)",
    "fact": "string (max 2048 chars, for remember only)",
    "document_id": "uuid (for rag_query only)",
    "n_results": "integer (max 20, for recall/search)",
    "options": {
      "model": "string (Ollama model name)",
      "max_tokens": "integer (max 4096)",
      "temperature": "float (0.0-1.0)"
    }
  },
  "timeout_ms": 30000
}
```

### Hard Limits (Request)

- `query` max: 4096 characters
- `fact` max: 2048 characters
- `n_results` max: 20
- `max_tokens` max: 4096
- `payload` total max: 16 KB
- No binary attachments in requests — document ingestion uses a separate `rag_ingest` task type with a document reference, not inline content

## 9.2 Response Schema (Private Domain → Control Plane)

```json
{
  "request_id": "uuid",
  "status": "success | error | timeout",
  "result": {
    "answer": "string (max 8192 chars)",
    "facts": [{"id": "uuid", "fact": "string (max 2048 chars)", "category": "string", "confidence": 0.95}],
    "doc_ids": ["uuid"],
    "metadata": {
      "model_used": "string",
      "tokens_in": 0,
      "tokens_out": 0,
      "processing_ms": 0
    }
  },
  "error": {
    "code": "string",
    "message": "string (max 512 chars)"
  }
}
```

### Hard Limits (Response)

- `answer` max: 8192 characters
- `facts` array max: 20 items
- `fact` text max: 2048 characters per item
- `error.message` max: 512 characters
- Response total max: 64 KB
- No binary data in responses

## 9.3 Redaction / DLP Rules

Before any response leaves the private domain:

- **PII scan**: Responses are scanned for common PII patterns (email addresses, phone numbers, SSNs, credit card numbers). Matches are redacted with `[REDACTED]` and a warning flag is set.
- **Sensitivity label**: Every response includes a `sensitivity_label` field (`none | low | medium | high`) based on content analysis. The control plane logs this but never stores `high`-sensitivity raw content.
- **No passthrough**: The private worker never echoes back the original query or raw document text. Only processed results (answers, summaries, fact extractions).

## 9.4 Contract Violations

- Any response exceeding size limits is rejected by the Noa API and logged as a contract violation
- Any response containing unexpected fields is stripped to the schema and logged
- 3 contract violations in 24 hours triggers an alert to the user

---

# 10. Storage & Persistence

## 10.1 Canonical Data Store: Postgres

Noa uses **PostgreSQL** as the canonical data store for all control-plane data. Postgres runs as a Docker container alongside the other services.

### Why Postgres (not SQLite)

- Multi-user extensibility: Row-level security, concurrent writes, user-scoped queries
- JSONB for flexible event/metadata storage
- Full-text search for conversations and audit logs
- Advisory locks for task queue coordination
- Alembic migrations for schema evolution from day one
- Avoids costly SQLite → Postgres migration later

### Control Plane Data (Postgres)

| Data Type | Table/Schema | Retention | Contains Private Content? |
|---|---|---|---|
| Conversations & messages | `conversations`, `messages` | Until user deletes thread | **Summaries only** — no raw private data |
| Runs & events | `runs`, `run_events` | Indefinite | Tool names + args, results truncated |
| Approvals | `approvals` | Indefinite | Preview summaries only |
| Audit log | `audit_log` | 90 days (configurable) | Tool names + args only, results truncated |
| Task queue | `task_queue` | Transient | No |
| Sessions & auth state | `sessions` | Session lifetime | No |
| Cost/usage summaries | `usage_stats` | Indefinite | No |
| Artifacts metadata | `artifacts` | Until user deletes | File references only, not content |
| LLM prompts & responses (external) | `audit_log` | 90 days | No (external domain only) |

### Private Domain Data (NOT in control-plane Postgres)

| Data Type | Stored In | Location | Retention |
|---|---|---|---|
| Long-term memory (facts) | Private domain storage | Docker volume (Phase 1) / encrypted APFS (Phase 2) | Until user deletes |
| Embeddings | Private domain storage | Docker volume (Phase 1) / encrypted APFS (Phase 2) | Until user deletes |
| RAG documents & chunks | Private domain storage | Docker volume (Phase 1) / encrypted APFS (Phase 2) | Until user deletes |
| Private LLM prompts/responses | **Not persisted** | — | — |

## 10.2 Invariant: No Raw Private Content on Control Plane

**Rule**: The control plane must never store raw private-domain content (full memory facts, raw RAG document text, unredacted private worker responses).

What *is* allowed on the control plane from private responses:

- Processed answers (capped at 8192 chars, redacted per DLP rules)
- Fact IDs and categories (not full fact text — only if needed for UI display, fetched live from private domain)
- Metadata (token counts, processing time, sensitivity labels)

## 10.3 Canary Token Tests

To verify this invariant:

- **Canary insertion**: During testing, inject known canary strings (e.g., `CANARY_PRIVATE_12345`) into private memory
- **Canary scan**: Automated weekly scan of all control-plane storage (Postgres, log files, temp directories) for any canary string
- **Alert**: If a canary is found on the control plane → critical alert, investigation, and contract review
- **CI integration**: Canary scan runs as part of the deployment test suite (Section 34)

## 10.4 Schema Migrations

- All schema changes use **Alembic** with version-controlled migration files
- Migrations run automatically on deployment (with safety checks)
- Rollback procedures documented for every migration
- No manual SQL against production Postgres

## 10.5 Backup Strategy

- Postgres: automated daily backups (pg_dump) to encrypted local storage
- Private domain data: separate backup to encrypted volume
- Backup verification: weekly restore test to ensure backup integrity

---

# 11. Secrets Lifecycle

## 11.1 Secret Categories

| Secret | Scope | Stored In |
|---|---|---|
| Anthropic API key | External container | macOS Keychain |
| OpenAI API key | External container | macOS Keychain |
| Google OAuth2 credentials | External container | macOS Keychain |
| Google OAuth2 refresh token | External container | Postgres (encrypted column) |
| Notion integration token | External container | macOS Keychain |
| Tavily API key | External container | macOS Keychain |
| JWT signing secret | Noa API | macOS Keychain |
| Postgres credentials | Noa API + Postgres | macOS Keychain |
| Private domain encryption key | Private container | macOS Keychain |
| mTLS client certificate | Inter-machine auth (Phase 2 only) | macOS Keychain |
| mTLS CA certificate | Inter-machine auth (Phase 2 only) | macOS Keychain |

## 11.2 Provisioning Rules

- Secrets are injected into containers at startup via environment variables or tmpfs-mounted files
- Secrets are never written to disk inside containers
- Secrets are never logged, even at debug level
- Secrets are never included in task payloads between domains
- mTLS certificates are pre-provisioned during initial setup (Phase 2)

## 11.3 Rotation

- API keys: rotated on a configurable schedule (default: 90 days) or on suspected compromise
- OAuth2 tokens: refresh tokens rotate automatically on each use
- JWT signing secret: rotated on admin action; all sessions invalidated on rotation
- Postgres credentials: rotated on admin action
- mTLS certificates (Phase 2): rotated annually or on suspected compromise; rotation procedure:
  1. Generate new cert on both machines
  2. Both machines temporarily accept old + new cert (grace period: 24 hours)
  3. After grace period, old cert is revoked
  4. Revocation logged as high-tier audit event
- Rotation is logged as a high-tier audit event

## 11.4 Compromise Response

If a secret is suspected compromised:

1. Immediately revoke the secret at the provider
2. Generate new secret and update the relevant keychain
3. Restart affected container to pick up new secret
4. Audit logs reviewed for unauthorized usage during exposure window

---

# 12. MVP Tool Definitions

Noa ships with the following tools for the MVP. Additional tools are added post-review.

## 12.1 Google Calendar

- **Auth**: Google OAuth2 (scopes: `calendar.readonly`, `calendar.events`)
- **Privacy**: `external` — requires Google API access
- **Domain**: External
- **Functions**:
  - `list_events(start_date, end_date)` → list of events with title, time, attendees
  - `create_event(title, start, end, description?, attendees?)` → created event ID
  - `update_event(event_id, changes)` → updated event
- **Risk tier**: Medium (create/update), Low (list)

## 12.2 Gmail

- **Auth**: Google OAuth2 (scopes: `gmail.readonly`, `gmail.send`, `gmail.compose`)
- **Privacy**: `external`
- **Domain**: External
- **Functions**:
  - `search_emails(query, max_results?)` → list of email summaries
  - `read_email(email_id)` → full email content
  - `send_email(to, subject, body)` → sent confirmation
  - `draft_email(to, subject, body)` → draft ID
- **Risk tier**: Medium (send), Low (search/read), Low (draft)

## 12.3 Notion

- **Auth**: Notion integration token
- **Privacy**: `external`
- **Domain**: External
- **Functions**:
  - `search_pages(query)` → list of matching pages with titles and IDs
  - `read_page(page_id)` → page content as markdown
  - `create_page(parent_id, title, content)` → created page ID
  - `update_page(page_id, content)` → updated page
- **Risk tier**: Medium (create/update), Low (search/read)

## 12.4 Web Search

- **Provider**: Tavily API (optimized for LLM agents, returns clean text)
- **Privacy**: `external`
- **Domain**: External
- **Functions**:
  - `web_search(query, max_results?)` → list of results with title, URL, content snippet
- **Risk tier**: Low

## 12.5 Memory

- **Privacy**: `private` — all data stays in the private domain
- **Domain**: Private (accessed via RPC contract)
- **Functions**:
  - `remember(fact)` → stores a fact with embedding for later retrieval
  - `recall(query, n_results?)` → semantic search over stored facts
- **Risk tier**: Low
- **Details**: See Section 13 (Memory Architecture)

**Total: 5 tools, 14 functions.**

---

# 13. Memory Architecture

Noa maintains two layers of memory.

## 13.1 Short-Term Memory (Conversation)

- **Implementation**: LangGraph checkpointer (`AsyncPostgresSaver`)
- **Stored in**: Control-plane Postgres
- **Scope**: Per conversation thread
- **Behavior**: Each `thread_id` maintains its full message history. Noa can reference earlier messages in the same thread. Threads are listed, resumable, and deletable.
- **Privacy**: Private-domain responses are stored as processed answers only (per RPC contract limits). Raw private data is not persisted in conversation state.

## 13.2 Long-Term Memory (Facts & Preferences)

- **Implementation**: Storage with vector embeddings for semantic retrieval
- **Stored in**: Private domain (Docker volume in Phase 1, encrypted APFS in Phase 2)
- **Scope**: Global across all threads
- **Behavior**:
  - Noa can explicitly store facts via the `remember` tool
  - Noa can retrieve facts via the `recall` tool (semantic search)

### Auto-Extraction Guardrails

Noa may optionally auto-extract notable facts after conversation turns. This feature requires the following safeguards:

- **Off by default** — user must explicitly enable auto-extraction in settings
- **Review queue** — auto-extracted facts are held in a pending state, visible in a **Memory Audit UI** in the web interface
- **User approval** — pending facts require explicit approval before entering long-term memory. User can approve, edit, or discard each fact.
- **Categories** — each extracted fact is tagged with a category (preference, habit, project context, personal info) so the user can filter and bulk-manage
- **Purge** — user can delete any fact at any time, with immediate removal from both the database and the embedding index
- **Transparency** — the Memory Audit UI shows: total facts stored, facts per category, storage size, and last extraction timestamp

### Schema

```json
{
  "id": "uuid",
  "fact": "User prefers dark mode in all apps",
  "category": "preference",
  "embedding": [0.012, -0.034, ...],
  "created_at": "2026-02-24T10:00:00Z",
  "source_thread_id": "thread-abc",
  "status": "approved | pending | rejected",
  "auto_extracted": true
}
```

- **Privacy**: Stored in private domain only. Embeddings generated by Ollama (local). Facts never leave the private domain except as truncated, redacted RPC responses.

## 13.3 RAG (Retrieval-Augmented Generation)

- **Purpose**: Noa can ingest personal documents (PDF, text, markdown) and answer questions about them
- **Implementation**: Documents are chunked, embedded locally (Ollama), and stored in the private domain storage
- **Retrieval**: The agent decides when to search the knowledge base vs. use tools vs. answer from context
- **Privacy**: `private` — all document processing and retrieval happens in the private domain. Only processed answers cross the RPC boundary.

---

# 14. Multi-Model Routing

## 14.1 Supported Providers

| Provider | Model Examples | Domain | Use Case |
|---|---|---|---|
| Ollama (local) | llama3.1, mistral, qwen3 | Private | Memory, RAG, summarization, private search |
| Anthropic | claude-sonnet, claude-opus | External | Complex reasoning, coding, multi-step tasks |
| OpenAI | gpt-4o, gpt-4o-mini | External | General tasks, alternative to Anthropic |

## 14.2 Routing Rules

The router node classifies each request and selects a provider:

1. If `privacy_mode: private` → **Ollama** (mandatory, no exceptions)
2. If user explicitly selects a provider in the UI → **that provider** (unless it conflicts with privacy mode)
3. If private domain is unavailable and task is private → **queue and wait** (never fallback to external)
4. Otherwise → use the configured default provider (default: external)

## 14.3 Router Characteristics

> **Note on determinism**: The orchestration graph (node sequencing, edge conditions, policy checks) is deterministic — given the same state, the same path executes. However, the privacy *classification* step uses content analysis (keyword matching + LLM-based assessment), which is inherently **probabilistic**. This is a deliberate trade-off. Network-level isolation is the hard backstop — even a misclassified task cannot leak private data because the private container has no internet egress.

### Fail-Safe Path for Ambiguous Classification

When the router's classification confidence is below threshold (default: 0.7):

1. **Force private** if private domain is available (fail-safe direction — treat ambiguity as sensitive)
2. **Require user confirmation** if private domain is unavailable: "I'm not sure if this involves private data. Route to external model or wait for the private domain?"
3. **Log** every low-confidence classification for the QA review loop

### Router Evaluation Metrics

To monitor classification quality:

- **False positive rate**: Tasks classified as `private` that could safely be `external` (causes unnecessary latency with local model)
- **False negative rate**: Tasks classified as `external` that should be `private` (mitigated by network isolation, but represents a policy violation)
- **Target**: < 5% false negative rate. False positives are acceptable (fail-safe direction).
- **Measurement**: Periodic manual review of classification log samples (weekly during early operation, monthly once stable)
- **Drift detection**: If the false negative rate increases by >2% between review periods, alert the user and suggest re-calibration

## 14.4 User Controls

- Default provider is configurable in settings
- Per-message override via model selector in the UI
- Per-message privacy mode toggle (`private` / `external`)
- Temperature, top-p, and max tokens are adjustable per provider
- Token usage and estimated cost are displayed per message and per session

---

# 15. Coding Task Contract

Every coding task Noa dispatches runs in the external domain and must follow this schema:

```json
{
  "repo": "string",
  "base_commit": "sha",
  "objective": "string",
  "constraints": {
    "language": "string",
    "style": "string",
    "performance": "string"
  },
  "acceptance_criteria": ["list"],
  "test_command": "string",
  "risk_tier": "low|medium|high",
  "max_iterations": 3
}
```

### Required Output From Coding Worker

- Git diff / patch
- Test output (raw logs + exit code)
- Lint/typecheck results
- Dependency diff (if applicable)
- Structured JSON summary:

```json
{
  "status": "success|failure",
  "files_modified": [],
  "tests_passed": true,
  "summary": "short description"
}
```

---

# 16. Output Validation & Sandboxed Review

All outputs from workers are validated before Noa acts on them.

## 16.1 Validation Pipeline

```
Worker Response
       ↓
  Schema Validation (JSON structure matches expected output)
       ↓
  Size Limit Check (per RPC contract / coding contract)
       ↓
  Content Filtering (no prompt injection markers, no exfiltration URLs)
       ↓
  Diff Review (for coding tasks: no unauthorized file modifications)
       ↓
  Policy Check (action within approved risk tier)
       ↓
  Noa accepts or rejects
```

## 16.2 Coding Output Checks

- Diff must only touch files within the scoped workspace
- No new dependencies added without explicit mention in the objective
- No modifications to CI/CD config, Dockerfiles, or security-sensitive files unless the task explicitly requires it
- Test command must have been executed and exit code captured

## 16.3 Tool Output Checks

- Tool responses must be valid JSON matching the tool's return schema
- Email send confirmations are logged before reporting success to the user
- Calendar events are validated (no events in the past, no unreasonable durations)
- Notion page content is sanitized before display

## 16.4 Prompt Injection Defense

- System prompts are never included in tool outputs shown to the user
- If a tool response contains instructions addressed to the LLM (e.g., "ignore previous instructions"), the response is flagged and logged
- Noa's system prompt includes explicit instructions to ignore injected instructions from tool outputs

---

# 17. Private Domain Availability & Queue Mechanics

## 17.1 Availability Model

### Phase 1 (Single Machine)

The private container runs on the same machine as everything else. It is always available when the host machine is running. No wake mechanism needed.

- **Health check**: Noa API polls the private container's health endpoint every 30 seconds
- **Failure**: If the private container doesn't respond, Noa attempts a container restart. If restart fails, private tasks enter the durable queue.

### Phase 2 (Dual Machine)

The MacBook Pro may be in sleep mode or off:

- **Primary**: Wake-on-LAN (WoL) magic packet over LAN
- **Fallback**: SSH wake (if MacBook Pro is in light sleep with SSH enabled)
- **Health check**: After sending wake signal, Mac Mini polls the MacBook Pro's mTLS endpoint every 2 seconds for up to 60 seconds
- **Failure**: If MacBook Pro doesn't respond within 60 seconds, task enters the durable queue

## 17.2 Durable Queue

Private tasks that cannot be dispatched immediately are held in a durable queue in the control-plane Postgres:

```json
{
  "queue_id": "uuid",
  "request_id": "uuid",
  "idempotency_key": "uuid",
  "task_type": "remember | recall | rag_query | ...",
  "payload": { "..." },
  "queued_at": "2026-02-24T10:00:00Z",
  "timeout_at": "2026-02-24T10:05:00Z",
  "status": "queued | dispatched | completed | failed | cancelled",
  "retry_count": 0,
  "max_retries": 3
}
```

### Queue Rules

- **Storage**: Postgres (survives API restart, supports concurrent access)
- **Idempotency**: Duplicate `idempotency_key` within 24 hours is rejected (prevents duplicate processing on retries)
- **Timeout**: Configurable per task type (default: 5 minutes). After timeout, task fails with `private_domain_unavailable` error.
- **Retry schedule**: On transient failure (network timeout, container restart): retry at 5s, 15s, 45s (exponential backoff)
- **Max queue depth**: 50 tasks. Beyond this, new private tasks are rejected immediately with a user notification.
- **User visibility**: Queued tasks are visible in all clients (web + mobile) with status, position, and ETA
- **Cancellation**: User can cancel any queued task from any client

## 17.3 User Notifications

- When a private task is queued: "Private domain is starting up. Your request is queued (position #N)."
- When queue timeout expires: "Private domain is unavailable. Switch to external mode or try again later?"
- When private domain comes online and queue drains: "Private domain is back. Processing N queued tasks."

---

# 18. Privacy Routing Rules

All tasks Noa processes are tagged with a privacy mode:

```json
{
  "privacy_mode": "private | external"
}
```

### Routing Logic

- `private` → Private domain only (Ollama, local data)
- `external` → External domain (remote LLM APIs, tool integrations, coding)

Private-tagged content must never leave the private domain except as RPC responses conforming to Section 9.

### Hard Enforcement

- Policy engine blocks invalid routing before any LLM call
- Network-level isolation blocks accidental egress from the private domain (Docker `internal: true` in Phase 1, pf firewall in Phase 2)
- RPC contract limits prevent unbounded data leakage even on the return path
- Logs record all routing decisions with the classification reasoning and confidence score
- Even if the router misclassifies, the private container physically cannot reach the internet

### Classification

The router node classifies privacy mode based on:

- Explicit user toggle (override — always respected)
- Content analysis: mentions of personal data, private notes, memory → `private`
- Tool requirements: Calendar, Gmail, Notion, Web Search → `external`
- Low confidence (< 0.7) → force `private` or ask user (see Section 14.3)
- Default: **`external`** (configurable)

### Default Mode Trade-off

The default is `external` by conscious design choice. This optimizes for usability (most tasks benefit from stronger models) at the cost of a higher-risk default. The risk is acceptable because:

1. Network isolation is the hard backstop — the private container cannot reach the internet regardless of classification
2. RPC contract limits bound what crosses the domain boundary
3. The user can override to `private` per-message or change the default in settings
4. Memory, RAG, and local data are always routed to `private` by tool requirement, not by classification

---

# 19. Tool Governance

## 19.1 Idempotency

Tools that perform write actions must be idempotent to prevent duplicate side effects on retries:

| Tool | Action | Idempotency Strategy |
|---|---|---|
| Gmail | `send_email` | De-duplicate by `idempotency_key` — if the same key is seen within 1 hour, return the previous result without re-sending |
| Gmail | `draft_email` | Idempotent by design (creates or updates draft) |
| Calendar | `create_event` | De-duplicate by `idempotency_key` — check for event with same title + time window (±5 min) before creating |
| Calendar | `update_event` | Idempotent by design (PUT semantics on event_id) |
| Notion | `create_page` | De-duplicate by `idempotency_key` — check for page with same title under same parent before creating |
| Notion | `update_page` | Idempotent by design (PUT semantics on page_id) |
| Memory | `remember` | De-duplicate by exact fact text match |

## 19.2 Dry-Run Previews

For Medium-risk tool actions, Noa generates a **preview** before execution:

```
User: "Schedule a meeting with Alex tomorrow at 2pm"
Noa: I'll create this event:
  Meeting with Alex
  2025-02-25, 14:00 – 15:00
  Attendees: alex@example.com

  [Confirm] [Edit] [Cancel]
```

- All `create` and `send` actions show a preview before execution
- Preview includes a diff-like summary of what will change
- User must confirm (or action is discarded)
- For High-risk actions: preview + mobile approval required

## 19.3 Rate Limits & Abuse Controls

| Scope | Limit | Action on Exceed |
|---|---|---|
| Global API | 60 req/min per session | HTTP 429, queue overflow |
| `send_email` | 10/hour | Block + notify user |
| `create_event` | 20/hour | Block + notify user |
| `create_page` (Notion) | 20/hour | Block + notify user |
| `web_search` | 30/hour | Block + notify user |
| Failed auth attempts | 5 in 10 min | Lock session for 30 min + notify user |
| Contract violations (Section 9.4) | 3 in 24 hours | Alert user + pause private worker |

---

# 20. Network Enforcement Specification

## 20.1 Phase 1: Docker Network Isolation

```yaml
# docker-compose.yml excerpt
networks:
  noa-internal:
    driver: bridge
    internal: true   # NO internet access — private domain
  noa-external:
    driver: bridge
    internal: false  # internet access allowed — external domain

services:
  private-worker:
    networks:
      - noa-internal
    # Cannot reach internet — internal: true blocks all egress

  external-worker:
    networks:
      - noa-external
    # egress controlled by iptables rules on the bridge

  noa-api:
    networks:
      - noa-internal
      - noa-external
    ports:
      - "127.0.0.1:8000:8000"  # LAN only, not 0.0.0.0

  postgres:
    networks:
      - noa-internal
    # Only accessible from noa-api and private-worker
```

### Key Properties (Phase 1)

- **Private container isolation**: `internal: true` blocks all internet egress at the Docker network level
- **No cross-domain route**: private-worker and external-worker are on separate networks with no bridge
- **Noa API as gateway**: Only the Noa API container spans both networks
- **LAN-only binding**: Noa API binds to `127.0.0.1` or LAN IP, never `0.0.0.0`

## 20.2 Phase 2: macOS pf Firewall (MacBook Pro)

```
# /etc/pf.conf (MacBook Pro) — Noa private enclave

# Default deny all
block all

# Allow loopback
pass on lo0

# Allow established connections (return traffic)
pass out on en0 proto tcp from any to <mac_mini_ip> port 443 flags S/SA keep state

# Allow mTLS to Mac Mini only
pass in on en0 proto tcp from <mac_mini_ip> to any port 8443 flags S/SA keep state

# Block ALL other IPv4 egress
block out on en0 all

# Block ALL IPv6
block on en0 inet6 all

# Block DNS to all external resolvers
block out on en0 proto {tcp, udp} from any to any port 53
```

### Key Properties (Phase 2)

- **Deny by default**: All traffic blocked unless explicitly allowed
- **LAN allow**: Only the Mac Mini's static IP can reach the MacBook Pro
- **IPv6 blocked entirely**: Prevents IPv6 egress bypass
- **DNS blocked**: No external DNS resolution possible
- **No outbound internet**: Even if code inside the container tries to reach the internet, pf blocks it at the OS level

## 20.3 Docker Network Policy (External Container — Both Phases)

- Egress allowlist: `api.anthropic.com`, `api.openai.com`, `*.googleapis.com`, `api.notion.com`, `api.tavily.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`
- All other egress blocked via Docker network policy
- DNS queries logged for audit

## 20.4 Continuous Verification

| Test | Frequency | Method | Alert On |
|---|---|---|---|
| Private container egress test | Every 6 hours (cron) | `curl -s --max-time 5 https://canary.example.com` from inside private container | **Success** (should always fail) |
| Private container DNS test | Every 6 hours (cron) | `nslookup google.com` from inside private container | **Success** (should always fail) |
| mTLS certificate validity (Phase 2) | Daily | Check cert expiry, alert if < 30 days | Cert expiring soon |
| Egress allowlist audit | Weekly | Log all external domains contacted by external container, diff against allowlist | Unknown domain contacted |
| IPv6 egress test | Every 6 hours (cron) | `curl -6 https://canary.example.com` from inside private container | **Success** (should always fail) |

## 20.5 mTLS Operations (Phase 2 Only)

- **Certificate generation**: `openssl` or `cfssl` with local CA. CA key stored in macOS Keychain (never on disk unencrypted).
- **Rotation procedure**: See Section 11.3 (grace period approach)
- **Revocation**: CRL (Certificate Revocation List) checked on each connection. CRL hosted on Mac Mini.
- **Time sync**: Both machines must use the same NTP source. Certificate validation fails on clock drift > 5 minutes.

---

# 21. Policy & Approval Framework

## Risk Tiers

### Low

- Local summarization
- Draft generation
- Read-only queries
- Memory recall
- Web search
- Reading emails / calendar / Notion pages

### Medium

- Sending email (preview required)
- Creating calendar events (preview required)
- Creating/updating Notion pages (preview required)
- Non-critical repo modifications
- Storing long-term memory facts

### High

- Dependency changes
- System file modification
- Financial transactions
- Merging to main branch
- Deleting data (emails, calendar events, Notion pages)

## Approval Rules

| Risk Tier | Requires | Preview? |
|---|---|---|
| Low | No approval | No |
| Medium | Explicit user approval (web or mobile) | Yes — dry-run preview shown |
| High | Mobile approval + Step-up Auth | Yes — preview + diff |

### Step-up Auth

- Biometric confirmation (Face ID / Touch ID)
- Re-authentication
- Device binding verification

---

# 22. Run/Event Model

Every user interaction that triggers Noa action becomes a **Run**. The Run is the unified API abstraction that all clients (Web, Mobile, CLI) consume.

## 22.1 Run Schema

```json
{
  "run_id": "uuid",
  "thread_id": "uuid",
  "user_id": "uuid",
  "status": "pending | running | awaiting_approval | completed | failed | cancelled",
  "risk_tier": "low | medium | high",
  "privacy_mode": "private | external",
  "created_at": "2026-03-04T10:00:00Z",
  "updated_at": "2026-03-04T10:00:05Z",
  "summary": "string (short description of what the run does)"
}
```

## 22.2 Event Stream (Append-Only)

Every Run has an ordered, append-only list of events:

```json
{
  "event_id": "uuid",
  "run_id": "uuid",
  "event_type": "message_received | classification_done | step_started | token_stream | tool_called | tool_result | approval_requested | approval_received | artifact_created | result_ready | error",
  "timestamp": "2026-03-04T10:00:01Z",
  "payload": { "..." }
}
```

### Event Types

| Event Type | Payload | When |
|---|---|---|
| `message_received` | User message text | Run starts |
| `classification_done` | `{ privacy_mode, confidence, reasoning }` | After router classifies |
| `step_started` | `{ step_name, model }` | Orchestrator enters a graph node |
| `token_stream` | `{ token, position }` | Each token from LLM (SSE) |
| `tool_called` | `{ tool_name, args }` | Tool invocation begins |
| `tool_result` | `{ tool_name, result_summary, duration_ms }` | Tool completes |
| `approval_requested` | `{ risk_tier, preview }` | Approval gate reached |
| `approval_received` | `{ decision: "approved" | "denied", user_id }` | User responds |
| `artifact_created` | `{ artifact_id, type, name }` | File/output produced |
| `result_ready` | `{ response_text }` | Final response |
| `error` | `{ code, message }` | Error occurred |

## 22.3 Artifacts

Runs may produce artifacts (files, diffs, exports):

```json
{
  "artifact_id": "uuid",
  "run_id": "uuid",
  "type": "file | diff | export | preview",
  "name": "string",
  "mime_type": "string",
  "size_bytes": 0,
  "storage_ref": "string (reference to object storage)",
  "created_at": "2026-03-04T10:00:05Z"
}
```

Artifact metadata is stored in Postgres. Artifact content is stored on the local filesystem in a dedicated artifacts directory.

## 22.4 SSE Endpoint

Clients subscribe to real-time events via Server-Sent Events:

```
GET /api/v1/runs/{run_id}/events
Accept: text/event-stream
Authorization: Bearer {access_token}

← event: token_stream
← data: {"token": "Hello", "position": 0}

← event: tool_called
← data: {"tool_name": "web_search", "args": {"query": "..."}}

← event: result_ready
← data: {"response_text": "Here is what I found..."}
```

This is the **same endpoint** consumed by Web UI, Mobile (PWA or native), and CLI. All clients render the same event timeline.

## 22.5 Run Storage

- Runs and events are stored in Postgres (`runs`, `run_events` tables)
- Events are append-only — never modified or deleted
- Run status is updated in place as the run progresses
- Completed runs are queryable for history and debugging

---

# 23. Task Scheduling & Prioritization

When Noa processes multiple concurrent or queued tasks, scheduling follows deterministic rules — not LLM judgment. This is a direct consequence of the governed execution model (Section 2).

## 23.1 Deterministic Sorting Rules

Tasks in the queue are ordered by:

1. **Priority tier** (descending):
   - `critical` — system health checks, security alerts, approval responses
   - `high` — user-initiated with explicit urgency ("do this now")
   - `normal` — standard user requests (default)
   - `background` — deferred tasks, auto-extraction, scheduled jobs

2. **Within the same priority tier**: FIFO (first in, first out)

3. **Tie-breaking**: Earlier `queued_at` timestamp wins. Timestamps are UTC from the system clock.

The LLM does not influence task ordering. Priority is assigned by the orchestrator based on task type and user-specified urgency.

## 23.2 Approval Batching

When multiple tasks require approval (Medium or High risk tier), they are batched to reduce notification fatigue:

- **Batch window**: 30 seconds (configurable). If multiple approval-required tasks arrive within this window, they are grouped into a single approval request.
- **Single notification**: One push notification is sent per batch, not one per task.
- **Batch review UI**: The approval screen (web or mobile) shows all pending tasks in the batch. User can approve or deny each individually, or approve/deny all.
- **Partial approval**: Approved tasks proceed immediately. Denied tasks are cancelled. Unanswered tasks remain pending until the batch timeout (default: 5 minutes).
- **No cross-domain batching**: Private-domain and external-domain tasks are never batched together — they are separate approval groups.

## 23.3 Dependency Handling

Some tasks have implicit or explicit dependencies:

| Dependency Type | Example | Handling |
|---|---|---|
| **Explicit** | "Send the email I just drafted" | Orchestrator resolves the reference to the draft task's output before scheduling the send |
| **Sequential** | Calendar check → schedule event | Second task waits for first to complete |
| **Independent** | Web search + read email | May execute concurrently |

Rules:

- Dependencies are resolved by the orchestrator at scheduling time, not by the LLM at execution time
- Circular dependencies are detected and rejected with a user-facing error
- A failed dependency cancels all downstream tasks and notifies the user
- Max dependency chain depth: 5 (prevents runaway task chains from prompt injection or recursive loops)

## 23.4 Task Queue UI

All clients display a visible task queue showing:

- All active, queued, and recently completed runs
- Per-run: status, priority, position, and estimated wait time
- Approval-pending runs are highlighted with the dry-run preview summary
- User actions: reorder tasks within the same priority tier, cancel any queued task, retry any failed task
- Queue updates are streamed in real-time via SSE (Run/Event model)

---

# 24. Cost Control

## Global Controls

- Monthly token cap (hard limit, Noa refuses requests when exceeded)
- Daily token cap (soft warning at 80%, hard limit at 100%)
- Per-task token limit
- Max iterations per coding task
- Max tool calls per workflow

## Token Tracking

Every LLM call logs:

- Provider and model name
- Input tokens and output tokens
- Estimated cost in USD (based on provider pricing)
- Cumulative session total

## Model Routing for Cost

Noa uses the cheapest sufficient model:

- Use Ollama (free) for private tasks
- Use smaller remote models (gpt-4o-mini, claude-haiku) for straightforward external tasks
- Escalate to full models (gpt-4o, claude-sonnet) only when:
  - Coding complexity exceeds threshold
  - Smaller model fails or produces low-quality output
  - User explicitly requests it

## Display

Token usage and cost are displayed in all clients:

- Per-message breakdown (model, tokens, cost)
- Session total
- Daily / monthly cumulative with budget progress bar

---

# 25. API Contract Standards

## 25.1 OpenAPI

- All Noa API endpoints are documented via **OpenAPI 3.1** specification
- FastAPI auto-generates the OpenAPI schema from endpoint definitions
- The OpenAPI spec is version-controlled alongside this document
- Breaking changes require a spec review before deployment

## 25.2 API Versioning

- All API endpoints are prefixed with `/api/v1/`
- Major version increments (`v2`) only for breaking changes
- Minor additions (new fields, new endpoints) are backward-compatible within the same version
- Deprecated endpoints are marked in OpenAPI and removed after 2 minor releases
- Mobile clients (especially native iOS) may lag behind Web — backward compatibility is critical

## 25.3 Standard Response Envelope

All API responses follow a consistent envelope:

```json
{
  "data": { "..." },
  "meta": {
    "request_id": "uuid",
    "trace_id": "uuid",
    "timestamp": "2026-03-04T10:00:00Z"
  },
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

## 25.4 Idempotency

All write endpoints accept an `Idempotency-Key` header:

- Clients must send a unique key for each distinct write operation
- The server de-duplicates requests with the same key within 24 hours
- This is critical for mobile clients on unreliable networks

---

# 26. Security Controls

## Required (Both Phases)

- LAN-only access to Noa API (no direct internet exposure)
- VPN for remote access (WireGuard / Tailscale)
- Encrypted volumes for all persistent data
- Audit logging for all tool invocations
- Immutable, append-only audit log with hash chain integrity verification
- Secrets manager for all credentials (see Section 11)
- Container hardening on all containers (see Section 8)
- DNS monitoring on external container egress
- Docker network isolation between private and external domains
- Continuous network verification (see Section 20.4)

## Required (Phase 2 Only)

- mTLS between control plane and private domain (physical machines)
- pf firewall on private machine blocking all internet egress (IPv4 + IPv6)

## Strongly Recommended

- Dependency scanning in coding workflow
- Rate limiting on Noa API endpoints (see Section 19.3)

---

# 27. Threat Model

## 27.1 Trust Assumptions

| Entity | Trust Level | Rationale |
|---|---|---|
| Host machine (macOS) | **Trusted** | Owner-controlled, physical access |
| Local network (LAN) | **Partially trusted** | Home network; VPN for remote; mTLS for Phase 2 inter-machine |
| Docker runtime | **Trusted** | Required for isolation, but not a hard security boundary — defense in depth |
| Remote LLM APIs (Anthropic, OpenAI) | **Untrusted with data** | API providers see the prompts and responses sent to them. No private data should be sent. |
| External tool APIs (Google, Notion) | **Untrusted with private data** | They see the user's calendar/email/notes content by design, but not private-domain data |
| Internet at large | **Untrusted** | All egress is allowlisted and monitored |

**Explicitly not addressed (accepted risks):**

- **Host OS compromise**: If the machine's OS is compromised, all bets are off. This is a single-user personal system; host hardening is the owner's responsibility.
- **Physical access attack**: FileVault / APFS encryption is the mitigation.

### Phase 1 Security Trade-off

In Phase 1, domain isolation is container-based, not physical. This means:

- A Docker escape could potentially access private data (defense in depth mitigates, but the boundary is softer than physical separation)
- The private container's internet isolation relies on Docker networking, not OS-level firewall
- This is an accepted trade-off for Phase 1 simplicity. Phase 2 upgrades to physical isolation for stronger guarantees.

## 27.2 STRIDE Analysis

| Threat | Category | Mitigation |
|---|---|---|
| Attacker intercepts inter-domain traffic | **Spoofing / Tampering** | Docker network isolation (Phase 1), mTLS (Phase 2) |
| Malicious prompt in tool output tricks LLM | **Tampering** | Output validation pipeline (Section 16), prompt injection detection |
| External container exfiltrates API keys | **Information Disclosure** | Keys injected via tmpfs, egress allowlisted, DNS monitored |
| Compromised Ollama model produces harmful output | **Tampering** | Model pinning by SHA256, air-gapped pull, read-only mount |
| Attacker gains network access and calls Noa API | **Spoofing** | LAN-only binding, VPN for remote, JWT auth on all endpoints |
| External container pivots to private container | **Elevation of Privilege** | Separate Docker networks, no route exists |
| Router misclassifies private task as external | **Information Disclosure** | Network isolation backstop + fail-safe (low confidence → force private) |
| Private data leaks via RPC response | **Information Disclosure** | RPC contract size limits + DLP redaction + canary tests |
| Audit log tampered to hide activity | **Repudiation** | Hash-chain integrity, append-only log |
| Cost runaway from LLM API abuse | **Denial of Service** | Hard token caps (monthly, daily, per-task) |
| Memory over-collection without consent | **Information Disclosure** | Auto-extraction off by default, review queue, user approval required |
| Duplicate emails/events from retries | **Tampering** | Idempotency keys on all write tool actions |
| Shell escape from coding container accesses private data | **Elevation of Privilege** | Shell only in external container, workspace-scoped namespace, no mount/route to private domain, seccomp profile blocks private container shell entirely (Section 2.4) |
| Docker escape compromises domain isolation | **Elevation of Privilege** | Container hardening, seccomp profiles, read-only root (Phase 1 accepted risk; Phase 2 adds physical isolation) |

---

# 28. Logging & Observability

## 28.1 Audit Log

Every tool invocation Noa triggers must log:

- Timestamp (UTC)
- User ID
- Session ID
- Device ID
- Trace ID (for request correlation across services)
- Domain used (private / external)
- Model provider and model name
- Token usage (input / output)
- Cost estimate (USD)
- Tool name and arguments
- Tool result summary (truncated per RPC contract limits)
- Side effects (email sent, event created, etc.)
- Privacy mode classification, confidence score, and reasoning

## 28.2 Log Integrity

- Audit logs are append-only (stored in Postgres)
- Each entry includes a SHA256 hash of the previous entry (hash chain)
- Log tampering is detectable by verifying the chain
- Private-domain internal logs stay in the private domain
- Control-plane logs are in Postgres

## 28.3 Structured Logging

All services emit **structured JSON logs** (not plain text):

```json
{
  "timestamp": "2026-03-04T10:00:00.123Z",
  "level": "info",
  "service": "noa-api",
  "trace_id": "uuid",
  "span_id": "uuid",
  "message": "Tool invocation completed",
  "data": {
    "tool": "web_search",
    "duration_ms": 234,
    "status": "success"
  }
}
```

### Standards

- Every request gets a unique `trace_id` that propagates across all services (Noa API → worker → tool)
- Logs are queryable by `trace_id` for end-to-end debugging
- Log levels: `debug`, `info`, `warn`, `error`
- No PII or secrets in log messages at any level

## 28.4 Metrics

Key operational metrics (exposed via `/api/v1/health/metrics`):

| Metric | Type | Purpose |
|---|---|---|
| `noa_requests_total` | Counter | Total API requests by endpoint and status |
| `noa_request_duration_seconds` | Histogram | Request latency distribution |
| `noa_llm_tokens_total` | Counter | Token usage by provider and model |
| `noa_llm_cost_usd_total` | Counter | Cumulative LLM cost |
| `noa_tool_invocations_total` | Counter | Tool calls by tool name and status |
| `noa_queue_depth` | Gauge | Current private task queue depth |
| `noa_active_runs` | Gauge | Currently active runs |
| `noa_private_worker_healthy` | Gauge | Private domain health (1 = healthy, 0 = unhealthy) |

## 28.5 Health Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | Basic liveness check |
| `GET /api/v1/health/ready` | Readiness (all dependencies connected) |
| `GET /api/v1/health/metrics` | Prometheus-compatible metrics |

## 28.6 LLM Observability (Optional)

- LangSmith integration for tracing LLM calls, tool usage, and graph execution
- Gated behind environment flag (`LANGSMITH_API_KEY`)
- When enabled, traces are sent to LangSmith — do **not** enable for `private` tasks

## 28.7 Data Retention

- Audit logs retained for 90 days by default (configurable)
- Run events retained indefinitely (part of the Run history)
- Conversation threads retained indefinitely until user deletes them
- Long-term memory retained indefinitely until user deletes individual facts
- Cost/usage summaries retained indefinitely (aggregated, no PII)
- Tool transcripts purged after session ends
- Expired logs are securely deleted

---

# 29. Client Architecture & Mobile Access

Noa is an **API-first system**. All clients consume the same API and Run/Event model (Section 22). No client has privileged access — all go through the Noa API.

## 29.1 Client Overview

| Client | Technology | Capabilities | Phase |
|---|---|---|---|
| **Web UI** | React + Vite | Chat, runs, approvals, admin, artifacts, memory audit | Phase 1 |
| **Mobile (PWA)** | Web UI as PWA on iPhone | Chat, runs, approvals, history (via VPN) | Phase 1 |
| **Mobile (Native)** | SwiftUI (iOS) | Chat, runs, approvals, voice, push (APNs), Keychain | Phase 2 |
| **CLI** | Python | Chat, tool invocation, scripting | Phase 1 |

## 29.2 Web UI (Primary Client)

The web UI is the primary development and debugging interface:

- Chat with streaming (SSE via Run/Event model)
- Run timeline with event details
- Approval interface with dry-run previews
- Task queue visualization
- Memory Audit UI (review, approve, delete facts)
- Cost dashboard
- Admin: settings, model selection, privacy controls
- Artifact viewer (diffs, files, exports)

Served by the Noa API container. Accessible via LAN or VPN.

## 29.3 Mobile Access

### Phase 1: PWA (Progressive Web App)

The web UI is installable as a PWA on iPhone:

- **Add to Home Screen** for app-like experience
- Full chat with streaming
- Run history and status
- Approval interface
- Access via VPN (WireGuard / Tailscale)
- **Limitations**: No native push notifications, limited background capability, no voice recording in background

### Phase 2: Native iOS App (SwiftUI Thin Client)

The native app extends PWA capabilities with:

- **Push Notifications (APNs)**: approval_requested, run_completed, run_failed
- **Voice**: Record audio, send to backend for processing, stream response
- **Biometric Auth**: Face ID / Touch ID for step-up authentication
- **Secure Storage**: Keychain for session tokens
- **Background**: Receive push and display actions without opening the app
- **Offline Queue**: Requests made offline are queued with idempotency keys and sent when connectivity resumes

The native app is a **thin client** — all intelligence remains server-side. The app is UI + audio + auth + push.

## 29.4 Connection Security

- All clients connect to Noa API exclusively over VPN (WireGuard / Tailscale) when remote
- No direct internet exposure of Noa API
- Certificate pinning on the native iOS app to prevent MITM

## 29.5 Push Notifications (Native iOS — Phase 2)

- Approval requests are sent via Apple Push Notification Service (APNs)
- Push payload contains only: notification type (`approval_required | run_completed | run_failed`), request ID, and risk tier
- No task content, tool names, or private data in the push payload
- Full context is fetched from Noa API after the user opens the notification (over VPN)

## 29.6 Approval Flow (All Clients)

```
Noa encounters medium/high risk action
       ↓
Noa generates dry-run preview (Section 19.2)
       ↓
Run event: approval_requested (visible to all connected clients)
       ↓
Push notification sent (native iOS only)
       ↓
User reviews preview on any client (web, PWA, or native)
       ↓
User approves / denies (+ biometric for high tier on native)
       ↓
Run event: approval_received — Noa resumes or aborts task
```

---

# 30. Resource Management

## Phase 1 (Single Machine)

| Resource | Allocation |
|---|---|
| Noa API + orchestrator | 2 CPU, 2 GB RAM |
| External container | 2 CPU, 4 GB RAM (configurable) |
| Private container (Ollama) | Remaining CPU, up to 32 GB RAM |
| Postgres | 1 CPU, 2 GB RAM |
| Coding workspace | NVMe SSD for repo I/O |
| Max concurrent external tasks | 2 (configurable) |
| Max execution time per external task | 5 minutes |

## Phase 2 (Dual Machine)

### Mac Mini (Control Plane + External Domain)

- Noa API and orchestrator are lightweight — minimal CPU/RAM
- External container: capped at 2 CPU, 4 GB RAM (configurable)
- Postgres: 2 GB RAM
- Coding workspace: NVMe SSD for repo I/O

### MacBook Pro (Sealed Private Enclave)

- Ollama: up to 48 GB RAM (reserving 16 GB for macOS + Docker)
- Apple Silicon GPU: fully available to Ollama for inference acceleration
- No coding repos, no build tools — minimal disk I/O beyond embeddings and memory
- Wake-on-LAN for on-demand activation
- Sleep timeout: 30 minutes of idle after last private task completes

---

# 31. Failure Handling

## Private Domain Unavailable

### Phase 1

- Private container health check fails → attempt container restart
- If restart fails → private tasks enter durable queue (Section 17)
- Never silently fallback to external — fail closed for private tasks
- External tasks continue unaffected

### Phase 2

- Private tasks enter durable queue
- Wake-on-LAN signal sent automatically
- If queue timeout expires: notify user with options (switch to external / wake manually / cancel)
- Never silently fallback to external — fail closed for private tasks
- External tasks continue unaffected

## External Domain Failure

- Retry up to `max_iterations` with exponential backoff
- On persistent failure, escalate to manual review
- Do not auto-merge failed patches
- Notify user with failure summary and suggested next steps

## Tool Failure

- Individual tool failures do not crash the agent
- Noa reports the tool error to the user and suggests alternatives
- Failed tool calls are logged with full error context
- Retry logic: up to 2 retries with backoff for transient errors (network timeouts, rate limits)
- Idempotency keys prevent duplicate side effects on retry (Section 19.1)

## Database Failure

- Postgres unavailability is a critical failure — Noa API returns 503
- Postgres runs with Docker restart policy `unless-stopped`
- Daily backup enables recovery

---

# 32. Worker Pool Abstraction

To enable future scaling of coding capacity without architectural changes.

## 32.1 Worker Registry

```json
{
  "worker_id": "uuid",
  "worker_type": "coding | private | external",
  "domain": "private | external",
  "capabilities": {
    "languages": ["python", "typescript", "go"],
    "max_concurrency": 2,
    "cpu_cores": 4,
    "ram_gb": 16
  },
  "status": "online | offline | busy",
  "last_heartbeat": "2026-02-24T10:00:00Z"
}
```

## 32.2 Current Workers (MVP)

| Worker | Type | Domain | Policy |
|---|---|---|---|
| `external-worker-1` | external + coding | External | External domain rules |
| `private-worker-1` | private | Private | Private domain rules, RPC contract |

## 32.3 Future Expansion

To add a coding worker on another machine later:

1. Register the new worker in the worker registry
2. The new worker **must** be classified as `external` in the policy engine — coding is always external, regardless of which machine it runs on
3. The new worker **must not** mount private memory/RAG/embeddings volumes
4. Workspace sync via `git clone` per job (no shared filesystem)
5. Workspace cleanup policy: delete after job completes or after 24 hours (configurable)
6. Egress rules: same allowlist as the external container

**Hard policy rule**: No coding worker may access private volumes. Coding is always in the external domain.

---

# 33. Non-Goals

Noa does **not**:

- Allow uncontrolled agent autonomy
- Allow cross-domain implicit data transfer
- Permit skill marketplace plugins (MVP)
- Permit direct shell execution without sandbox
- Replace the user's judgment on high-risk actions
- Run anything in the cloud — all infrastructure is local
- Store raw private content on the control plane

## Multi-User Readiness

Noa is designed as a **single owner-operator system** for MVP. However, the architecture explicitly supports future multi-user extension:

- Postgres with user-scoped data and row-level security readiness
- Session management supports multiple concurrent sessions
- Audit logging includes user ID on every entry
- API authentication is token-based with scoped permissions
- Run/Event model includes user_id on every run

Multi-user support is a future extension (Section 35), not an MVP requirement.

---

# 34. Testing Requirements

Before deployment:

### Privacy & Isolation

- Validate privacy routing (`private` tasks never hit external LLM API)
- Validate private container cannot reach the internet (egress test must fail)
- Validate no direct network route between private and external containers
- Run canary token test: inject canary into private memory, scan control-plane Postgres, assert not found
- Run RPC contract limit test: send oversized responses from private worker, assert rejection
- Run DLP redaction test: insert PII into private worker response, assert redaction on control plane side
- Automated privacy regression suite: weekly cron replaying test prompts, asserting correct classification + routing

### Phase 2 Additional Privacy Tests

- Validate mTLS between machines (reject unauthenticated connections)
- Validate pf firewall on MacBook Pro: IPv4, IPv6, and DNS (all must fail)

### Functional

- Verify all 5 tools work end-to-end (Calendar, Gmail, Notion, Web Search, Memory)
- Verify tool enable/disable prevents execution
- Verify idempotency: retry `send_email` with same key, assert no duplicate
- Verify dry-run previews render for all Medium-risk actions
- Verify coding task contract: submit job, receive structured output
- Verify Run/Event model: events stream correctly via SSE to all connected clients

### Reliability

- Verify private domain unavailability handling: queue → timeout → user notification
- Verify durable queue survives Noa API restart (Postgres-backed)
- Verify Postgres backup and restore procedure
- Stress test coding iteration caps

### Security

- Run simulated prompt injection against output validation
- Verify no private data appears in external container logs or control-plane storage
- Verify token caps halt execution when exceeded
- Verify audit log hash chain integrity after 100+ entries
- Verify session expiry and token refresh flow
- Verify approval flow end-to-end (preview → approve → resume) on web and mobile
- Verify failed auth lockout after 5 attempts

### API

- Verify OpenAPI spec is auto-generated and accurate
- Verify API versioning (v1 endpoints respond correctly)
- Verify idempotency key deduplication on all write endpoints
- Verify standard response envelope on all endpoints

---

# 35. Future Extensions

- Encrypted remote backup for private domain
- Advanced anomaly detection on tool calls
- Automatic red-team simulations
- Model fallback strategies (auto-switch provider on failure)
- Additional tools: Slack, GitHub Issues, Jira, file management
- Voice interface (native iOS client)
- **Multi-user support** with role-based access, row-level security, per-user quotas
- VM boundary for private domain (stronger isolation than Docker)
- Additional coding workers (see Section 32)
- CI integration for PR validation
- **Phase 2 deployment**: Physical domain isolation with dedicated MacBook Pro
- WebSocket upgrade for bidirectional real-time collaboration (if SSE proves insufficient)

---

# 36. Build Phases

## Phase 1: Backend Foundation (API-first)

1. Postgres schema: users, conversations, messages, runs, run_events, approvals, artifacts, audit_log, task_queue
2. Noa API (FastAPI) with OpenAPI spec
3. SSE streaming via `/api/v1/runs/{id}/events`
4. LangGraph orchestrator with router, agent, tool, and responder nodes
5. Risk tiers + approval framework
6. Auth (JWT sessions, login, refresh)
7. Audit logging with hash chain
8. Docker Compose for all services (Phase 1 single-machine deployment)
9. Private worker with Ollama + RPC contract
10. External worker with tool integrations

**Milestone**: Backend API is stable and testable. Clients can be developed in parallel.

## Phase 2: Web Client (React + Vite)

1. Chat UI with streaming (SSE)
2. Run timeline with event details
3. Approval interface with dry-run previews
4. Task queue visualization
5. Memory Audit UI
6. Cost dashboard
7. Settings and admin views
8. Artifact viewer
9. PWA manifest for mobile installation

**Milestone**: Web is the primary interface. PWA on iPhone provides 24/7 mobile access.

## Phase 3: Native iOS Client (SwiftUI)

1. Chat UI with streaming
2. Push notifications (APNs) for approvals and run status
3. Voice recording and playback
4. Biometric step-up auth (Face ID / Touch ID)
5. Secure storage (Keychain)
6. Offline request queue with idempotency
7. VPN auto-connect

**Milestone**: Mobile is a full-featured thin client with voice and push.

## Phase 4: Dual-Machine Deployment (Optional)

1. Move private container to MacBook Pro
2. Configure mTLS between machines
3. Enable Wake-on-LAN
4. Apply pf firewall on MacBook Pro
5. Verify physical isolation with expanded test suite

**Milestone**: Maximum security posture with physical domain isolation.

---

# 37. Definition of Done

The system is complete (Phase 1 + 2) when:

- Noa responds to user messages via web UI with streamed output
- Private tasks are processed in the private container only (Ollama)
- External tasks and coding route to the external container
- All 5 MVP tools function correctly with idempotency and previews
- Conversation memory persists across sessions (Postgres checkpointer)
- Long-term memory stores and recalls facts with user-controlled auto-extraction
- Memory Audit UI allows user to review, approve, and delete stored facts
- RAG answers questions about ingested documents
- Token usage and cost are displayed per message and per session
- Model selection works from the UI (Ollama / Anthropic / OpenAI)
- Privacy routing classifies correctly with fail-safe for low confidence
- RPC contract enforced between domains (size limits, redaction, schema validation)
- No raw private content stored on control plane (canary tests pass)
- Cost limits are enforced
- All actions are logged in the immutable audit log (Postgres, hash chain)
- Run/Event model streams correctly to all connected clients via SSE
- Approval flow works on web UI and PWA
- Docker network isolation verified (private container cannot reach internet)
- Durable queue handles private domain unavailability gracefully
- Output validation rejects malformed or suspicious responses
- Continuous network verification running and alerting
- OpenAPI spec is auto-generated and accurate
- API versioning is functional
- PWA is installable on iPhone
- Postgres backups are automated and tested

---

# 38. Architectural Philosophy

Noa embodies:

- **Governed agentic execution** — the foundational invariant (Section 2). Deterministic outer shell, bounded inner autonomy. The LLM reasons within steps; the orchestrator controls the workflow.
- **Deterministic graph execution** — given the same state, the same path executes. Privacy classification is probabilistic with network isolation as the hard backstop.
- **Domain isolation** — private and external domains are strictly separated. Phase 1 uses container isolation; Phase 2 upgrades to physical machine isolation. The RPC contract is the architectural boundary in both phases.
- **Contained shell execution** — shell access exists only in the external coding sandbox. The private domain has zero shell capability. (Section 2.4)
- **Enforceable contracts** — every byte crossing the domain boundary is schema-validated, size-limited, and DLP-scanned
- **Explicit approval governance** — risk-tiered human-in-the-loop with dry-run previews
- **API-first design** — all clients consume the same API and Run/Event model. No client has privileged access.
- **Modular extensibility** — tools, models, workers, and clients are pluggable via registries and contracts
- **Defense in depth** — layered security at every boundary (application, container, network, firewall)
- **Replaceable model backends** — no vendor lock-in
- **Memory as a first-class concern** — Noa learns and remembers, with user control and auditability
- **Multi-user readiness** — single-user MVP with architectural foundations for multi-user extension

```
Noa decides.
Workers execute.
The LLM reasons — it does not orchestrate.
Shell access is sandboxed to the coding container.
Privacy is enforced at the domain boundary.
Contracts are enforced at the RPC layer.
Cost is enforced at the policy layer.
Execution is sandboxed.
Memory is local and user-controlled.
Clients are thin — the API is the product.
```

End of Specification.
