# Noa Technical Guide

> A comprehensive guide to understanding Noa — its architecture, functionality, strengths, and weak points.
> Last updated: 2026-04-09

---

## Table of Contents

1. [What Is Noa?](#what-is-noa)
2. [Core Philosophy: Governed Execution](#core-philosophy-governed-execution)
3. [Architecture Overview](#architecture-overview)
4. [The Dual-Domain Model](#the-dual-domain-model)
5. [How a Request Flows Through the System](#how-a-request-flows-through-the-system)
6. [Tech Stack & Why We Chose It](#tech-stack--why-we-chose-it)
7. [Project Structure](#project-structure)
8. [Key Components Deep-Dive](#key-components-deep-dive)
9. [Database & Migrations](#database--migrations)
10. [Security Model](#security-model)
11. [Docker & Networking](#docker--networking)
12. [Testing](#testing)
13. [Development Workflow](#development-workflow)
14. [Configuration](#configuration)
15. [Strengths](#strengths)
16. [Weak Points & Known Gaps](#weak-points--known-gaps)
17. [What's Built & What's Next](#whats-built--whats-next)

---

## What Is Noa?

Noa is a **governed personal AI agent** that runs entirely on local hardware. Think of it as a personal assistant that can read your emails, manage your calendar, search the web, and remember things about you — but with strict rules about **what it can do**, **when it needs your permission**, and **where your private data goes**.

The two core principles:

1. **Your private data never leaves your machine.** Journals, personal notes, and sensitive information stay in a sealed container with no internet access.
2. **Every action is governed.** Noa classifies actions by risk level. Low-risk actions (like a web search) happen automatically. High-risk actions (like sending an email) require your explicit approval.

Noa is **not** an autonomous agent. It is a **governed execution engine** — the LLM handles reasoning and tool argument generation, but the workflow topology, approval gates, privacy routing, and cost limits are all enforced by deterministic code that the LLM cannot modify or bypass.

### Noa in the Broader Strategy

Noa is one half of a two-product strategy:

- **Noa** — A governed orchestration layer that coordinates tools, enforces policy, and composes cross-domain decisions. "Optimizes life decisions."
- **TheCoach** — A vertical decision engine for endurance training. "Optimizes training decisions."

Noa can call TheCoach as a tool. TheCoach works independently of Noa. They share architectural principles but have separate codebases and target audiences.

---

## Core Philosophy: Governed Execution

This is the most important concept in Noa. Every architectural decision flows from it.

### Deterministic Outer Shell

The orchestration layer is deterministic and predefined. The LLM does not control it.

| Invariant | What It Means |
|-----------|---------------|
| **Fixed workflow topology** | The LangGraph state machine defines the node sequence (`router → classifier → planner → agent → tools → evaluator`). The LLM cannot add, remove, or reorder nodes. |
| **Static tool allowlists** | The set of tools available to any step is defined at graph compile time. The LLM cannot invoke unlisted tools. |
| **Explicit approval checkpoints** | Every side-effecting action passes through a risk-tier check. The LLM cannot skip or defer approval gates. |
| **Pre-execution privacy routing** | Domain classification happens before the LLM sees the task. The LLM cannot change its own routing. |
| **Fixed cost and iteration limits** | Token caps, retry limits, and tool call budgets are enforced by the orchestrator, not requested by the LLM. |

### Bounded Inner Autonomy

Within a single orchestrated step, the LLM has bounded freedom:

**The LLM may:**
- Reason about user intent
- Generate arguments for tool calls
- Synthesize structured outputs (answers, summaries, code)
- Choose parameters for an allowed tool (e.g., which calendar date to query)
- Decide *which* allowed tool to call (from the step's allowlist)

**The LLM may NOT:**
- Invent new workflow stages or nodes
- Bypass approval checkpoints
- Escalate model tier outside policy
- Change domain routing (private ↔ external)
- Execute tools not in the current step's allowlist
- Modify its own system prompt or tool definitions
- Persist state outside the checkpointer

### Why This Matters

| If the LLM could... | Then... |
|---|---|
| Control execution order | Auditability breaks — log replay becomes non-deterministic |
| Skip approval gates | Policy enforcement weakens — risk tiers become advisory |
| Choose its own model tier | Cost control becomes probabilistic |
| Override privacy routing | Private data could reach external APIs |
| Add workflow stages | Prompt injection gains execution authority |

---

## Architecture Overview

```
+------------------------------------------------------------------+
|                        YOUR MACHINE                               |
|                                                                   |
|  +------------------+        +--------------------------------+   |
|  |   Web Client     |        |   iOS App / CLI (future)       |   |
|  |   (React)        |        |                                |   |
|  +--------+---------+        +---------------+----------------+   |
|           |          HTTP (port 8000)         |                   |
|           +----------------+-----------------+                    |
|                            |                                      |
|              +-------------v--------------+                       |
|              |         Caddy (TLS)        |                       |
|              +-------------+--------------+                       |
|                            |                                      |
|                 +----------v-----------+                          |
|                 |      noa-api         |                          |
|                 |  (FastAPI Gateway)   |                          |
|                 |                      |                          |
|                 |  - Auth (JWT)        |                          |
|                 |  - Orchestrator      |                          |
|                 |  - Policy Engine     |                          |
|                 |  - Privacy Router    |                          |
|                 |  - Tool Gateway      |                          |
|                 +----+------------+----+                          |
|                      |            |                               |
|        +-------------+            +--------------+                |
|        | noa-internal network      noa-external  |                |
|        | (NO internet)             network       |                |
|        |                           (internet)    |                |
|  +-----v--------+  +--------+  +--v-----------+ |                |
|  | private-      |  |Postgres|  | external-    | |                |
|  | worker        |  |  16    |  | worker       | |                |
|  |               |  |        |  |              | |                |
|  | - Ollama (AI) |  | Control|  | - Anthropic  | |                |
|  | - Memory/RAG  |  | Plane  |  | - OpenAI     | |                |
|  | - Local files  |  | DB     |  | - Google AI  | |                |
|  +---------------+  +--------+  | - Tools      | |                |
|                                 +--------------+ |                |
|                                                                   |
+------------------------------------------------------------------+
```

**Key idea:** The `noa-api` container sits on *both* networks. It's the only bridge between the sealed private world and the internet-connected external world. Nothing else crosses that boundary.

### Container Topology

| Container | Port | Networks | Role |
|-----------|------|----------|------|
| **caddy** | 443, 80 | both | TLS termination, reverse proxy |
| **noa-api** | 8000 | both (gateway) | FastAPI, orchestrator, auth, policy, tool gateway |
| **postgres** | 5432 | internal only | Control-plane database |
| **private-worker** | 8001 | internal only (NO internet) | Ollama, memory, local processing |
| **external-worker** | 8002 | external only (has internet) | LLM APIs, tool integrations |
| **backup** | — | internal only | pg_dump + GPG encryption sidecar |

---

## The Dual-Domain Model

This is the most important architectural concept in Noa. Everything splits into two domains:

```
+============================+     +============================+
||    PRIVATE DOMAIN        ||     ||    EXTERNAL DOMAIN       ||
||                          ||     ||                          ||
||  Network: noa-internal   ||     ||  Network: noa-external   ||
||  Internet: NONE          ||     ||  Internet: YES           ||
||                          ||     ||                          ||
||  What lives here:        ||     ||  What lives here:        ||
||  - Personal journals     ||     ||  - LLM API calls         ||
||  - Private memories      ||     ||  - Calendar integration  ||
||  - Sensitive notes       ||     ||  - Email integration     ||
||  - Local AI (Ollama)     ||     ||  - Web search            ||
||  - RAG vector store      ||     ||  - Notion integration    ||
||                          ||     ||                          ||
||  AI Model: Ollama        ||     ||  AI Models: Claude,      ||
||  (runs locally)          ||     ||  GPT-4, Gemini           ||
||                          ||     ||                          ||
||  Can access external     ||     ||  Can access private      ||
||  domain? NO              ||     ||  domain? NO              ||
+============================+     +============================+
                    \                     /
                     \                   /
                      +--noa-api (gateway)--+
                      |  Routes requests    |
                      |  to correct domain  |
                      +---------------------+
```

**Why two domains?** If you tell Noa "remember that my therapist's name is Dr. Smith", that fact is stored in the private domain. When Noa later uses Claude (an external API) to help you draft an email, that private fact is *never* sent to the external API. The network-level isolation makes this guarantee physical, not just a software promise.

### How the Privacy Router Decides

When a request comes in, the privacy router classifies it in priority order:

```
1. Explicit override     -- User said "keep this private" or "use external"
       |
       v  (no override?)
2. Tool-based routing    -- Requested tools imply a domain
       |                    (e.g., "send email" -> external,
       v  (no tools?)       "remember" -> private)
3. Content analysis      -- Keywords like "journal", "private", "secret"
       |                    trigger private routing
       v  (low confidence?)
4. Fail-safe             -- Default to PRIVATE (safe fallback)
```

**Availability handling:** If the user explicitly requests a domain that's unavailable:
- Private unavailable → queue (retry later)
- External unavailable → error (can't fulfill)
- Low-confidence classification → force private (safe default)

**Private keywords:** journal, diary, private, personal, my notes, my files, secret, password, confidential

**Private tools:** memory

**External tools:** calendar, gmail, notion, web_search

### Domain Isolation Enforcement (Three Layers)

1. **Network level** — Docker networks with `internal: true` physically block internet access
2. **Application level** — ToolGateway checks `adapter.domain` matches `request.privacy_mode`
3. **Volume level** — Private data volumes mounted only on private-worker and noa-api

---

## How a Request Flows Through the System

Here's what happens when you type "What's on my calendar today?" into Noa:

```
User types message
        |
        v
[1] POST /api/v1/chat (ChatRequest: message, thread_id, privacy_mode?, model?, tool_scope?)
        |
        v
[2] Auth middleware validates JWT token → extracts user_id
        |
        v
[3] Thread created or reused; Run created (status: pending → running)
        |
        v
[4] OrchestratorRunner starts LangGraph execution (Langfuse trace opened)
        |
        +---> [router node]
        |       PrivacyClassifier: "calendar" → EXTERNAL domain
        |       Model selected: claude-sonnet (or user override)
        |       SSE event: classification_done
        |
        +---> [classifier node]
        |       Task type: "execution" (heuristic or LLM-based)
        |       SSE event: task_classified
        |
        +---> [planner node] (skipped for simple_utility / execution)
        |       Generates 2-4 step execution plan
        |       Selects archetype (execution, research, comparative_selection)
        |
        +---> [agent node]
        |       ProviderRouter dispatches to Anthropic/OpenAI/Google
        |       LLM response: "I need to call calendar.list_events"
        |       SSE event: tool_calls
        |
        +---> [tools node]
        |       ToolGateway checks:
        |         ✓ Tool in allowlist?
        |         ✓ Domain matches? (calendar → external ✓)
        |         ✓ User has capability grant?
        |         ✓ Policy engine: risk_tier=LOW → auto-approve
        |       Executes via DirectApiAdapter → Google Calendar API
        |       SSE event: tool_results
        |
        +---> [conditional edge: more tool calls needed?]
        |       tool_rounds < max (3) AND tool_calls exist → back to agent
        |       no more tool calls → forward to evaluator
        |
        +---> [evaluator node]
                Scores response on rubric (goal_alignment, completeness, ...)
                score >= 3.0 → pass → __end__
                score >= 2.0 → reroute → agent (with feedback, max 2 cycles)
                score <  2.0 → flag → __end__
                Persists scores to response_evaluations table
                SSE event: response
                SSE event: done (run_id, total_cost, status)
                |
                v
[5] Events streamed via SSE to client in real-time
        |
        v
[6] Run completed, audit log entry written, usage stats recorded, Langfuse trace closed
```

### SSE Event Types

The chat endpoint returns a `text/event-stream` with these typed events:

| Event Type | Payload | When |
|------------|---------|------|
| `meta` | request_id, user_id, environment | Immediately |
| `message_received` | message text | After validation |
| `classification_done` | privacy_mode, model | After router node |
| `agent_thinking` | token count | During LLM inference |
| `tool_calls` | function, args, preview | When LLM requests tools |
| `tool_results` | name, result or error | After tool execution |
| `approval_requested` | risk_tier, tool, function, preview | When approval needed |
| `response` | text | Final response |
| `done` | run_id, total_cost, status | Completion |

SSE keepalive pings (`: comment`) sent every 15 seconds to prevent proxy timeouts.

### The LangGraph Pipeline (Conditional Edges)

```
__start__ → router → classifier ──(simple_utility)──→ agent ⇄ tools
                         │                              │
                         └──(complex)──→ planner → agent │
                                                         ↓
                                                    evaluator ──(reroute)──→ agent
                                                         │
                                                      __end__
```

**6 nodes, 4 conditional edges:**

**Conditional edge: classifier → ?**
- `simple_utility` → `agent` (skip planner)
- All other task types → `planner`

**Conditional edge: agent → ?**
- If `tool_calls` exist → `tools`
- If no `tool_calls` → `evaluator`

**Conditional edge: tools → ?**
- If `tool_rounds < max_retries` → `agent`
- Otherwise → `evaluator`

**Conditional edge: evaluator → ?**
- `pass` (score >= 3.0) or `flag` (score < 2.0) → `__end__`
- `reroute` (score 2.0-3.0) and `eval_cycle < max_cycles` → `agent` (with feedback)
- `reroute` and `eval_cycle >= max_cycles` → `__end__`

**Four conditions stop the pipeline:**
1. Agent returns no tool_calls and evaluator passes (done reasoning)
2. `tool_rounds >= MAX_TOOL_ROUNDS` (default 3)
3. Evaluator verdict is `pass` or `flag`
4. Reroute cycle limit reached (default 2)

---

## Tech Stack & Why We Chose It

### Core Framework Choices

| Technology | What It Does | Why We Chose It |
|---|---|---|
| **Python 3.11** | Language | Dominant in AI/ML ecosystem. Async support mature. Huge library ecosystem for LLM integrations. |
| **FastAPI** | Web framework | Async-native, automatic OpenAPI docs, Pydantic integration for request validation. |
| **LangGraph** | AI orchestration | Gives us a *deterministic* state machine for LLM workflows. Unlike raw LangChain, LangGraph lets us define fixed node topologies — critical for governance. |
| **PostgreSQL 16** | Database | Battle-tested relational DB. Concurrent access from multiple containers. True async I/O via `asyncpg`. |
| **SQLAlchemy 2.0** | ORM | Industry standard Python ORM. Version 2.0 has native async support. Type-safe query building. |
| **Docker** | Containerization | *The* mechanism for domain isolation. Docker networks enforce the private/external boundary at the OS level. |

### Why These Specific Choices Matter

**LangGraph over raw LangChain:** LangChain is flexible but chaotic — agents can call arbitrary chains of tools in unpredictable order. LangGraph forces us to define a state machine (`router → classifier → planner → agent → tools → evaluator`). For a *governed* AI agent, predictability is a feature, not a limitation.

**FastAPI over Django/Flask:** Django is too opinionated and synchronous-first. Flask lacks built-in async. FastAPI gives us async request handling (critical when waiting on LLM API responses that take seconds), automatic request validation via Pydantic, and auto-generated API documentation.

**PostgreSQL over SQLite:** We need concurrent access from multiple containers (api, workers), ACID transactions for audit logs, and the ability to scale. SQLite can't handle concurrent writes from multiple processes.

**Pydantic everywhere:** Pydantic validates data at every boundary — API requests, config loading, RPC messages between domains. We use `pydantic-settings` for 12-factor app configuration (all config via environment variables).

### Supporting Libraries

| Library | Purpose |
|---|---|
| **structlog** | Structured JSON logging. Every log line is machine-parseable. Automatically strips secrets from log output. |
| **httpx** | Async HTTP client for calling LLM APIs and inter-service communication. |
| **python-jose** | JWT token creation and validation for authentication. |
| **passlib + bcrypt** | Secure password hashing. bcrypt is deliberately slow to resist brute-force attacks. |
| **Alembic** | Database migration management. Versioned migration files for safe upgrades/rollbacks. |
| **ruff** | Ultra-fast Python linter and formatter. Replaces flake8, isort, and black in a single tool. |
| **mypy** | Static type checker in strict mode. Catches type errors before runtime. |
| **pytest** | Testing framework with async support via `pytest-asyncio`. |
| **nh3** | HTML sanitization (replaces bleach). Prevents XSS in user-generated content. |
| **DOMPurify** | Frontend-side HTML sanitization for rendered content. |

### Frontend Stack

| Technology | Purpose |
|---|---|
| **React 18** | UI framework with hooks |
| **TypeScript** | Type-safe frontend code |
| **Vite** | Build tool (fast HMR, tree-shaking) |
| **TanStack Query** | Async state management (caching, mutations) |
| **Tailwind CSS** | Utility-first styling |
| **Shadcn/ui** | Component library (Radix primitives + Tailwind) |
| **Vitest** | Unit testing |
| **Playwright** | E2E browser testing |

### iOS Stack

| Technology | Purpose |
|---|---|
| **Swift 6** | Strict concurrency (Sendable, actor isolation) |
| **SwiftUI** | Declarative UI |
| **SPM** | Package management |
| **ASWebAuthenticationSession** | OAuth flows |
| **XCTest** | Unit + integration testing |

---

## Project Structure

```
/workspace/
|
+-- SPEC.md                    # THE source of truth (governance model, contracts)
+-- STRATEGY.md                # Product strategy (Noa + TheCoach)
+-- CLAUDE.md                  # AI agent orchestration protocol
|
+-- src/noa/                   # Application code
|   +-- __init__.py
|   +-- config.py              # Settings (env vars → Pydantic model)
|   +-- types.py               # Shared enums (PrivacyMode, RiskTier)
|   |
|   +-- api/                   # HTTP layer (FastAPI)
|   |   +-- app.py             # App factory, lifespan (wires everything)
|   |   +-- app_state.py       # Typed shared state (router, runner, gateway, memory)
|   |   +-- middleware.py       # Request ID, error handling, CORS, CSP
|   |   +-- deps.py            # Dependency injection helpers
|   |   +-- sse_types.py       # 14 typed SSE event TypedDicts
|   |   +-- v1/                # Versioned endpoints
|   |   |   +-- health.py      # GET /health, GET /ready, GET /health/tools
|   |   |   +-- auth.py        # POST /token, /register, /refresh, /logout, /me
|   |   |   +-- chat.py        # POST /chat (SSE streaming)
|   |   |   +-- runs.py        # GET /runs, GET /runs/{id}/events
|   |   |   +-- approvals.py   # GET/POST /approvals
|   |   |   +-- threads.py     # CRUD /threads
|   |   |   +-- settings.py    # GET/PATCH /settings
|   |   |   +-- memory.py      # GET/POST/DELETE /memory
|   |   |   +-- tools.py       # GET /tools, POST /tools, capability management
|   |   |   +-- cost.py        # GET /cost (usage stats)
|   |   |   +-- voice.py       # POST /voice (Whisper transcription)
|   |   |   +-- google_oauth.py # OAuth2 flow (authorize/callback/status/disconnect)
|   |   +-- schemas/           # Request/response Pydantic models
|   |
|   +-- auth/                  # Authentication
|   |   +-- service.py         # User CRUD, token management
|   |   +-- jwt.py             # JWT encode/decode
|   |   +-- password.py        # bcrypt hashing
|   |   +-- middleware.py       # @require_auth decorator → AuthUser
|   |
|   +-- orchestrator/          # LangGraph AI pipeline
|   |   +-- graph.py           # State machine definition (conditional edges)
|   |   +-- state.py           # AgentState TypedDict (~20 fields)
|   |   +-- runner.py          # OrchestratorRunner (graph execution, SSE yield)
|   |   +-- checkpointer.py    # Conversation state persistence
|   |   +-- nodes/
|   |       +-- router.py      # Privacy classification + model selection
|   |       +-- classifier.py  # Task type classification (heuristic + LLM)
|   |       +-- planner.py     # Execution plan generation (complex tasks only)
|   |       +-- agent.py       # LLM decision-making via ProviderRouter
|   |       +-- tools.py       # Tool execution via ToolGateway
|   |       +-- evaluator.py   # Response quality scoring + reroute logic
|   |
|   +-- privacy/               # Privacy classification
|   |   +-- classifier.py      # 4-level routing logic
|   |   +-- metrics.py         # Confidence scoring
|   |
|   +-- policy/                # Action governance
|   |   +-- engine.py          # Risk tier classification (LOW/MEDIUM/HIGH)
|   |   +-- approval.py        # Approval state machine
|   |   +-- preview.py         # Dry-run preview generation
|   |   +-- schemas.py         # Approval models
|   |
|   +-- tools/                 # Tool system
|   |   +-- gateway.py         # Central dispatch (idempotency, rate limits, capabilities, policy)
|   |   +-- interface.py       # ToolInterface Protocol + ToolAdapter
|   |   +-- capabilities.py    # DbCapabilityChecker (per-user, per-function grants)
|   |   +-- definitions.py     # TOOL_SCHEMAS dict (function defs for all providers)
|   |   +-- registration.py    # Startup tool registration (Tavily, Calendar, Gmail, Notion, Memory)
|   |   +-- adapters/          # DirectApiAdapter, HttpToolAdapter, McpRemoteAdapter
|   |
|   +-- runs/                  # Run execution tracking
|   |   +-- service.py         # Run CRUD (async)
|   |   +-- events.py          # Append-only event log
|   |
|   +-- audit/                 # Audit logging
|   |   +-- logging.py         # Structured JSON logger (secret sanitization)
|   |   +-- service.py         # Hash-chain audit trail
|   |   +-- integrity.py       # Chain verification
|   |
|   +-- private_worker/        # Private domain worker
|   |   +-- app.py             # FastAPI app (port 8001, noa-internal only)
|   |   +-- rpc.py             # RPC contract validation
|   |   +-- handlers.py        # Task handlers (remember, recall, summarize, ...)
|   |   +-- memory_store.py    # JSON-file-per-fact persistence
|   |   +-- dlp.py             # Data loss prevention
|   |
|   +-- external_worker/       # External domain worker
|   |   +-- app.py             # FastAPI app (port 8002, noa-external only)
|   |   +-- llm/               # LLM provider abstraction
|   |   |   +-- router.py      # ProviderRouter (selects provider, formats tools, dispatches)
|   |   |   +-- anthropic.py   # Anthropic (Claude) — /v1/messages, tool_use, retry 429/529
|   |   |   +-- openai.py      # OpenAI (GPT) — /v1/chat/completions, tool_calls, retry 429
|   |   |   +-- google_ai.py   # Google AI (Gemini) — /generateContent
|   |   |   +-- ollama.py      # Ollama (local) — /api/chat
|   |   +-- tools/             # Tool integrations (Calendar, Gmail, Notion, Tavily)
|   |
|   +-- db/                    # Database layer
|       +-- base.py            # SQLAlchemy base, metadata
|       +-- session.py         # Async session factory
|       +-- models/            # ORM models (see Database section)
|
+-- web/                       # React/TypeScript frontend
|   +-- src/
|       +-- api/               # HTTP client + schema types
|       +-- auth/              # AuthContext, AuthGuard, token persistence
|       +-- components/
|       |   +-- chat/          # ThreadSidebar, ChatMessages, ChatComposer, ApprovalCard
|       |   +-- settings/      # GeneralSettings, GoogleSettings, ToolSettings
|       |   +-- runs/          # RunTimeline, EventDetails
|       |   +-- tools/         # ToolDashboard, CredentialModal
|       |   +-- ui/            # Shadcn/ui components
|       +-- hooks/             # useChatSSE, useOptimisticMessages, useThreads
|       +-- pages/             # Chat, Threads, Settings, Memory, Queue, Runs, Cost, Approvals
|
+-- ios/                       # iOS app (Swift 6 / SwiftUI)
|   +-- Noa/Sources/           # APIClient, SSEClient, services, view models, views
|   +-- Noa/Tests/             # 270+ XCTest cases
|
+-- tests/                     # Python test suite
|   +-- conftest.py            # Shared fixtures
|   +-- unit/                  # Unit tests (no external deps)
|   +-- integration/           # Integration tests (real DB via testcontainers)
|
+-- docker/                    # Dockerfiles (per-service)
+-- docker-compose.yml         # Production-like deployment
+-- docker-compose.dev.yml     # Dev environment
+-- alembic/                   # Database migrations (19 versions)
+-- prompts/                   # System prompt (canonical file, UI reads/writes it)
+-- tools/                     # Dev tools (notify.py, keychain_store.sh, pre-push-hook.sh)
+-- Plan/                      # Planning docs, reviews, retros, findings
+-- pyproject.toml             # Python project config
+-- Makefile                   # Common dev commands
```

---

## Key Components Deep-Dive

### The Orchestrator (`src/noa/orchestrator/`)

This is the brain of Noa. It uses LangGraph to define a state machine with conditional edges:

```python
# Simplified from graph.py
graph = StateGraph(AgentState)

graph.add_node("router",     router_node)      # Classify privacy domain & pick model
graph.add_node("classifier", classifier_node)  # Categorize task type (simple/exec/research/decision)
graph.add_node("planner",    planner_node)     # Generate execution plan for complex tasks
graph.add_node("agent",      agent_node)       # LLM generates response/tool calls
graph.add_node("tools",      tool_node)        # Execute tool calls via ToolGateway
graph.add_node("evaluator",  evaluator_node)   # Score response quality, reroute if needed

graph.add_edge(START,      "router")
graph.add_edge("router",   "classifier")
graph.add_edge("planner",  "agent")

# Conditional: classifier fast-paths simple tasks past planner
graph.add_conditional_edges("classifier", route_after_classifier, {
    "agent": "agent",       # simple_utility skips planner
    "planner": "planner"    # complex tasks get a plan
})

# Conditional: agent decides if tools are needed
graph.add_conditional_edges("agent", route_after_agent, {
    "tools": "tools",
    "evaluator": "evaluator"
})

# Conditional: tools loop back or exit
graph.add_conditional_edges("tools", route_after_tools, {
    "agent": "agent",
    "evaluator": "evaluator"
})

# Conditional: evaluator passes, flags, or reroutes
graph.add_conditional_edges("evaluator", route_after_evaluator, {
    "__end__": END,
    "agent": "agent"        # reroute with feedback (max 2 cycles)
})
```

The `AgentState` is a TypedDict that flows through every node:

```python
class AgentState(TypedDict):
    messages: list              # Conversation history (HumanMessage, AIMessage, ToolMessage)
    privacy_mode: str           # "private" or "external" (PrivacyMode enum)
    selected_model: str         # Which LLM to use (e.g., "anthropic/claude-sonnet-4-20250514")
    requested_tools: list       # Tool definitions available to the LLM
    tool_results: list          # Results from tool execution
    tool_rounds: int            # Counter for tool-loop iteration cap
    max_retries: int            # Configurable tool-loop limit (default 3)
    llm_usage: list             # Per-step cost tracking (provider, model, tokens, cost_usd)
    total_cost: float           # Running cost for this run
    task_type: str              # Classifier output: simple_utility/execution/research/decision_intelligence
    plan: str | None            # Planner output: numbered execution plan (None for simple tasks)
    archetype: str | None       # Planner archetype: execution/research/comparative_selection
    eval_verdict: str           # Evaluator verdict: pass/reroute/flag
    eval_cycle: int             # Current reroute cycle count (max 2)
    eval_scores: dict           # Per-dimension rubric scores (1-5)
    tool_scope: str | None      # Task-specific tool filtering (e.g., "email_draft")
    # ... plus run/thread/user context fields
```

### The Tool Gateway (`src/noa/tools/gateway.py`)

The Tool Gateway is the **single point of control** for all tool execution. Every tool call flows through it:

```
Tool call requested
        |
        v
[1] Allowlist check ─── Tool registered? ──> NO → ToolNotFoundError
        |
        v (yes)
[2] Domain check ─── adapter.domain matches request.privacy_mode? ──> NO → DomainViolationError
        |
        v (yes)
[3] Capability check ─── User has grant for this tool+function? ──> NO → PermissionDeniedError
        |
        v (yes)
[4] Policy check ─── Risk tier classification
        |
        +── LOW → auto-approve
        +── MEDIUM → require approval (return preview)
        +── HIGH → require approval + step-up auth
        |
        v (approved)
[5] Idempotency check ─── Cached response for this key? ──> YES → return cached
        |
        v (no cache)
[6] Rate limit check ─── Per-user, per-tool sliding window ──> EXCEEDED → RateLimitError
        |
        v (allowed)
[7] Execute via adapter (DirectApiAdapter / HttpToolAdapter / McpRemoteAdapter)
        |
        v
[8] Cache response (if idempotency key provided)
        |
        v
[9] Record telemetry (tool_call_logs table) + fire audit callback
```

**Registered tools at startup:**

| Tool | Domain | API | Requires |
|------|--------|-----|----------|
| **web_search** | external | Tavily API | TAVILY_API_KEY |
| **calendar** | external | Google Calendar API v3 | Google OAuth |
| **gmail** | external | Gmail API v1 | Google OAuth |
| **notion** | external | Notion API v1 | NOTION_TOKEN |
| **memory** | private | In-process MemoryStore | — |
| **external_memory** | external | In-process MemoryStore | — |

**Custom tools** can be registered via `POST /api/v1/tools` (stored in `custom_tools` table, loaded at startup).

**MCP servers** can be connected via `POST /api/v1/mcp-servers` (JSON-RPC 2.0 over HTTP+SSE, auto-discovery of tools).

### LLM Provider System (`src/noa/external_worker/llm/`)

The ProviderRouter selects and dispatches to the appropriate LLM:

```
ProviderRouter.complete(messages, model, tools, privacy_mode)
        |
        v
[1] Privacy enforcement ─── private mode? ──> Only Ollama allowed
        |
        v
[2] Provider selection ─── model string → provider client
        |
        +── "anthropic/*" → AnthropicClient.complete()
        +── "openai/*"    → OpenAIClient.complete()
        +── "google_ai/*" → GoogleAIClient.complete()
        +── "ollama/*"    → OllamaClient.complete()
        |
        v
[3] Tool format translation ─── Each provider has different tool JSON format
        |
        v
[4] Normalized response → { content, tool_calls, usage, provider, model }
```

**Per-client details:**

| Provider | Endpoint | Retry Logic | Auth |
|----------|----------|-------------|------|
| **Anthropic** | `POST /v1/messages` | 429, 529 with backoff | `x-api-key` header |
| **OpenAI** | `POST /v1/chat/completions` | 429 with backoff | `Authorization: Bearer` |
| **Google AI** | `POST /generateContent` | No retry | `?key=` query param |
| **Ollama** | `POST /api/chat` | No retry (local) | None |

All clients use **httpx** with a 60-second timeout. Responses are buffered (not streamed from provider to client).

### The Policy Engine (`src/noa/policy/engine.py`)

Every tool call gets classified by risk:

| Risk Tier | Actions | Behavior |
|-----------|---------|----------|
| **LOW** | web_search, memory recall/remember, read email/calendar, draft email | Auto-approved |
| **MEDIUM** | send email, create calendar event, create Notion page | Show preview, ask user for approval |
| **HIGH** | delete email/calendar/Notion, modify system files, financial transactions | Preview + step-up auth (biometric) |

Unknown actions default to **HIGH** (conservative).

When `approvals_enabled=False` (configurable per user), policy checks are skipped entirely.

### The Audit System (`src/noa/audit/`)

Every significant action creates an audit log entry. Entries are hash-chained:

```
Entry #1                    Entry #2                    Entry #3
+------------------+        +------------------+        +------------------+
| event: "login"   |        | event: "run"     |        | event: "tool"    |
| data: {...}      |        | data: {...}      |        | data: {...}      |
| prev_hash: null  |--+     | prev_hash: abc1  |--+     | prev_hash: def2  |
| hash: abc123     |  |     | hash: def234     |  |     | hash: ghi345     |
+------------------+  |     +------------------+  |     +------------------+
                      |                           |
                      +--hash(null + event_data)  +--hash(abc1 + event_data)
```

If anyone tampers with Entry #2, its hash changes, which breaks the chain at Entry #3. This makes the audit trail tamper-evident.

Additionally, every tool call is logged in `tool_call_logs` with latency, status, cache hit, and the tool/function name — visible via `GET /health/tools`.

### RPC Contract (Private Worker)

Communication between the API gateway and the private worker:

```
noa-api                                    private-worker
   |                                            |
   |  POST /rpc                                 |
   |  {                                         |
   |    "request_id": "uuid",                   |
   |    "task_type": "remember",  <-- allowed set only
   |    "payload": {              <-- max 16 KB
   |      "fact": "...",                        |
   |      "user_id": "..."                      |
   |    }                                       |
   |  }                                         |
   | -----------------------------------------> |
   |                                            |
   |  200 OK                                    |
   |  {                                         |
   |    "request_id": "uuid",                   |
   |    "status": "success",                    |
   |    "result": {...}           <-- max 64 KB |
   |  }                                         |
   | <----------------------------------------- |
```

Validated on both sides. If either side sends malformed data, it's rejected.

**Task types:** remember, recall, rag_query, rag_ingest, summarize, search

**Note:** rag_query, rag_ingest, summarize, and search are currently stubbed (return empty results). See [Weak Points](#weak-points--known-gaps).

---

## Database & Migrations

### Key Tables

```
+-------------+     +-------------+     +-----------------+
|   users     |---->|auth_sessions|     |  audit_entries  |
| - email     |     | - device_id |     | - event         |
| - pass_hash |     | - token     |     | - data (JSON)   |
| - is_active |     | - user_id   |     | - prev_hash     |
+------+------+     +-------------+     | - hash          |
       |                                +-----------------+
       |
       v
+------+--------+     +-----------+     +-------------+
| conversations |---->|   runs    |---->| run_events  |
| - title       |     | - status  |     | - event_type|
| - user_id     |     | - risk    |     | - payload   |
| - domain      |     | - privacy |     | - timestamp |
+---------------+     | - summary |     +-------------+
                      +-----+-----+
                            |
                      +-----+-----+     +------------------+
                      | approvals |     | tool_call_logs   |
                      | - status  |     | - tool           |
                      | - tool    |     | - function       |
                      | - function|     | - latency_ms     |
                      | - risk    |     | - status         |
                      | - preview |     | - cached         |
                      +-----------+     +------------------+

+------------------+     +------------------+     +------------------+
| tool_capabilities|     | google_creds     |     | device_tokens    |
| - user_id       |     | - user_id        |     | - user_id        |
| - tool_name     |     | - access_token   |     | - device_id      |
| - function_name |     |   (encrypted)    |     | - token          |
| - capability    |     | - refresh_token  |     | - platform       |
+------------------+     |   (encrypted)    |     +------------------+
                         +------------------+
                                                  +------------------+
+------------------+     +------------------+     | usage_stats      |
| custom_tools     |     | task_queues      |     | - run_id (FK)    |
| - name           |     | - task_type      |     | - input_tokens   |
| - base_url       |     | - priority       |     | - output_tokens  |
| - auth_type      |     | - payload        |     | - cost_usd       |
| - schema         |     | - status         |     | - model          |
+------------------+     +------------------+     +------------------+
```

### Migration History

19 Alembic migrations covering:
- Initial schema (users, sessions, conversations, runs)
- Audit entries with hash chain
- Tool capabilities and call logs
- Usage stats with FK to runs
- Google OAuth encrypted token storage
- Device tokens for APNs
- Domain column on conversations (FR1)
- Indexes on hot query paths (user_id, run_id, created_at)
- Approval structured fields (CQ9)

### Running Migrations

```bash
alembic upgrade head                                    # Apply all
alembic revision --autogenerate -m "describe change"    # Create new
alembic downgrade -1                                    # Rollback one step
```

---

## Security Model

### Authentication Flow

```
[User]                    [noa-api]                   [Database]
  |                          |                            |
  |  POST /api/v1/auth/register (first run)              |
  |  POST /api/v1/auth/token    (subsequent)             |
  |  {email, password}       |                            |
  | -----------------------> |                            |
  |                          |  Verify bcrypt hash        |
  |                          | -------------------------> |
  |                          | <------------------------- |
  |                          |                            |
  |  {access_token (7d),     |                            |
  |   refresh_token (90d)}   |                            |
  | <----------------------- |                            |
  |                          |                            |
  |  Any authenticated request                            |
  |  Authorization: Bearer <access_token>                 |
  | -----------------------> |                            |
  |                          |  @require_auth validates   |
  |                          |  JWT signature + expiry    |
  |                          |  Extracts AuthUser         |
  |  200 OK                  |  (user_id, device_id,     |
  | <----------------------- |   email)                   |
```

**Token lifecycle:**
- Access token: 7-day TTL, signed with SECRET_KEY
- Refresh token: 90-day TTL
- JWT claims: sub (user_id), type, iat, exp, jti, sid (session_id)
- Refresh via POST /api/v1/auth/refresh
- Logout invalidates session in DB

### Container Hardening

Every worker container runs with:
- **Read-only filesystem** — can't write to system directories
- **All capabilities dropped** — no `NET_RAW`, no `SYS_ADMIN`, nothing
- **no-new-privileges** — can't escalate via setuid binaries
- **Non-root user** (`noa:noa`) — even if exploited, limited damage
- **tmpfs volumes** limited to 256MB — prevents disk-filling attacks
- **Resource limits** — CPU and memory caps per container
- **Health checks** — Docker-level health probes for auto-restart

### Web Security Headers

- **CSP** (Content Security Policy) — restricts script/style sources
- **X-Content-Type-Options: nosniff** — prevents MIME sniffing
- **CORS** — restricted to configured origins (tightened per environment)
- **HttpOnly cookies** — session cookies not accessible via JavaScript
- **nh3 sanitization** — server-side HTML cleaning
- **DOMPurify** — client-side HTML sanitization

### Google OAuth Token Storage

Google OAuth tokens (access + refresh) are encrypted at rest in the database using a dedicated `token_crypto` module. Tokens are decrypted only when needed for API calls and never logged.

---

## Docker & Networking

### Network Isolation

```
                      INTERNET
                         |
                    +---------+
                    |  Caddy  |
                    +----+----+
                         |
          +--------------+--------------+
          |       noa-external          |
          |       (internet OK)         |
          |                             |
     +----+----+                   +----+----+
     | noa-api |                   | external|
     | (both   |                   | worker  |
     | nets)   |                   +---------+
     +----+----+
          |
          +--------------+--------------+
          |       noa-internal          |
          |       (NO internet)         |
          |                             |
     +----+----+  +----------+    +----+----+
     | postgres|  | backup   |    | private |
     |         |  | sidecar  |    | worker  |
     +---------+  +----------+    +---------+
```

The `noa-internal` network has `internal: true` in Docker Compose, which means Docker itself blocks any route to the internet. This isn't just a firewall rule — the network physically has no gateway to the outside.

### Resource Limits

| Container | CPU | Memory | Notes |
|-----------|-----|--------|-------|
| noa-api | 2 | 2 GB | Gateway, orchestrator |
| private-worker | 4 | 32 GB | Ollama model loading |
| external-worker | 2 | 4 GB | LLM API calls |
| postgres | 2 | 2 GB | Database |

---

## Testing

### Test Suite Overview

| Test Area | Files | Approx. Tests | Covers |
|-----------|-------|---------------|--------|
| Auth & sessions | 8 | ~120 | JWT, login, register, OAuth, refresh, lockout |
| Orchestrator | 12 | ~200 | Graph execution, conditional edges, tool dispatch, state machine |
| Tools & gateway | 15 | ~250 | Each tool independently, gateway dispatch, capabilities, rate limiting |
| Privacy & domain isolation | 6 | ~80 | Router, classifier, DLP, cross-domain checks |
| Cost tracking | 4 | ~60 | Pricing, budget limits, usage aggregation |
| API endpoints | 20 | ~350 | All routers, contract tests, error handling |
| Database & models | 10 | ~130 | ORM models, relationships, migrations, Postgres integration |
| Queue & resilience | 4 | ~50 | Durable queue, backoff, idempotency |
| Audit | 3 | ~40 | Hash chain, retention, queryability |
| Frontend (Vitest) | 11 | ~175 | Pages, components, API client, auth context |
| E2E (Playwright) | 5 | ~40 | Login, chat, settings, tools, approvals |
| iOS (XCTest) | 15 | ~224 | Models, services, view models, integration flows |
| **Total** | **~120** | **~2,400+** | **84% code coverage** |

### Running Tests

```bash
# All Python tests
pytest

# Specific phase tests
pytest -m f1            # Foundation phase 1
pytest -m oc2           # Orchestration phase 2
pytest -m qe4           # Postgres integration tests

# With coverage
pytest --cov=src/noa --cov-report=term-missing

# Static checks
ruff check src/ tests/
mypy src/               # Strict mode, 0 errors enforced

# Frontend
cd web && npm run test          # Vitest
cd web && npm run test:e2e      # Playwright

# iOS
cd ios && swift test
```

### Test Philosophy

- Tests trace to SPEC.md sections (e.g., `"""§9.2: Request payload must not exceed 16 KB."""`)
- Integration tests use real Postgres via testcontainers (no SQLite mocking)
- Mutation testing via mutmut on critical paths (auth, router, gateway)
- Flaky detection via pytest-repeat in nightly CI

---

## Development Workflow

### Phase Execution Pipeline

```
  Plan           Test            Code          Code Review       QA Review
+--------+    +--------+    +----------+    +------------+    +-----------+
| Define |    | Write  |    | Write    |    | Fast code  |    |  QA agent |
| phase  |--->| failing|--->| code to  |--->| review     |--->|  reviews  |
| in     |    | tests  |    | pass     |    | (sonnet)   |    |  against  |
| PLAN.md|    | (red)  |    | tests    |    | fix obvious|    |  checklist|
+--------+    +--------+    +----------+    +------------+    +-----------+
```

### Quality Gates (Before Merge)

```bash
ruff check src/ tests/    # Linting
mypy src/                 # Type checking (strict, 0 errors)
pytest                    # All tests green
```

### Git Conventions

- **Branches:** `agent/<agent_id>-<task_slug>`
- **Commits:** `<scope>: <summary>` (e.g., `dw3: implement Docker network isolation`)
- **Merges:** Always `--no-ff` (preserves branch history)
- **No force-push.** Ever.

---

## Configuration

All configuration flows through environment variables (12-factor app). The `Settings` class in `src/noa/config.py` validates everything at startup:

```bash
# Core
NOA_ENV=development              # development | production | testing
API_HOST=127.0.0.1               # Bind address (localhost only!)
API_PORT=8000                    # API port

# Database
DATABASE_URL=postgresql+asyncpg://noa:noa@localhost:5432/noa

# Security
SECRET_KEY=change-me-in-prod     # JWT signing key (MUST change in prod)

# LLM Providers
ANTHROPIC_API_KEY=sk-...         # Anthropic (Claude)
OPENAI_API_KEY=sk-...            # OpenAI (GPT)
GOOGLE_AI_API_KEY=...            # Google AI (Gemini)
OLLAMA_BASE_URL=http://...       # Ollama (local)

# Tool Credentials
GOOGLE_CLIENT_ID=...             # Google OAuth
GOOGLE_CLIENT_SECRET=...         # Google OAuth
NOTION_TOKEN=ntn_...             # Notion API
TAVILY_API_KEY=tvly-...          # Tavily web search

# Defaults
DEFAULT_EXTERNAL_MODEL=openai/gpt-4.1-mini
DEFAULT_PRIVATE_MODEL=ollama/llama3.1

# Logging
LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR
```

**Production safety:** App refuses to start if `SECRET_KEY` is still the dev default.

---

## Strengths

### 1. Deterministic Governance (The Big Differentiator)

Noa's core strength is that **the LLM cannot control the execution path**. The LangGraph state machine defines a fixed topology (`router → classifier → planner → agent → tools → evaluator`). Tool allowlists are static. Approval gates are enforced by the orchestrator, not requested by the model. This makes the system auditable, predictable, and resistant to prompt injection escalation.

Most AI agent frameworks give the LLM full control over tool calling and workflow branching. Noa inverts this: the outer shell is deterministic, and the LLM has bounded autonomy only within individual steps.

### 2. Physical Domain Isolation

Privacy isn't a software flag — it's enforced by Docker network topology. The private worker **physically cannot reach the internet** because the `noa-internal` network has no gateway. No amount of prompt injection, code bugs, or configuration mistakes can cause private data to leak to external APIs through the private domain. This is a guarantee that pure application-level isolation can never provide.

### 3. Comprehensive Audit Trail

Three layers of audit:
- **Run events** — append-only event log for every step in every run
- **Tool call logs** — latency, status, cache hit for every tool execution
- **Hash-chained audit entries** — tamper-evident log of all significant actions

Together, these make any execution fully reproducible from logs.

### 4. Multi-Provider LLM Support with Normalized Interface

Anthropic, OpenAI, Google AI, and Ollama all return the same normalized response format. Switching providers is a configuration change, not a code change. Tool definitions are automatically formatted per provider (Anthropic uses flat `tool__function` names, OpenAI uses nested format).

### 5. Fine-Grained Capability System

Tool permissions are per-user, per-tool, and per-function. A user can be granted access to `calendar.list_events` without being granted `calendar.delete_event`. Grants are stored in the database and enforced at the gateway level.

### 6. Real-Time Streaming (SSE)

The chat endpoint streams 14 typed SSE events as the orchestrator processes. Clients get real-time visibility into classification, tool calls, approvals, and costs — not just the final answer. This enables responsive UIs and transparent AI behavior.

### 7. Cost Tracking & Control

Every LLM call records input/output tokens, model, provider, and cost. The runner sums per-run costs after graph execution completes. Usage stats are persisted to the database and queryable via the cost dashboard. Token budgets and iteration limits are enforced by the orchestrator.

### 8. Container Hardening

Read-only filesystems, dropped capabilities, no-new-privileges, non-root users, resource limits, and health checks on every container. The attack surface is minimized even if a container is compromised.

### 9. Mature Test Infrastructure

2,400+ tests, 84% coverage, mutation testing, Postgres integration tests, Playwright E2E, iOS XCTest. CI enforces ruff + mypy (strict, 0 errors) + pytest as merge gates.

### 10. Three-Client Coverage

Web (React), iOS (SwiftUI), and a backend that serves all three via a consistent API. The iOS app supports offline queuing, biometric auth, push notifications, and voice recording.

---

## Weak Points & Known Gaps

### Critical Gaps

#### 1. No Semantic Search / RAG (HIGH impact)

The private worker's recall function uses **placeholder embeddings** (empty arrays). There's no actual embedding generation or vector similarity search. The `rag_query`, `rag_ingest`, `summarize`, and `search` handlers are **stubbed** — they return empty results.

**Impact:** Memory recall is effectively keyword-based, not semantic. The system can remember facts but can't do "find memories related to..." in any meaningful way.

**To fix:** Integrate a local embedding model (e.g., `nomic-embed-text` via Ollama) and a vector store (e.g., ChromaDB or pgvector) in the private worker.

#### 2. No LLM Streaming (MEDIUM-HIGH impact)

All LLM responses are **buffered** — the system waits for the complete response before forwarding anything to the client. SSE events stream the *orchestration steps* (classification, tool calls, etc.), but the actual LLM text generation isn't streamed token-by-token.

**Impact:** Users see a delay between "thinking" and "response" instead of tokens appearing as they're generated. This feels slow, especially for long responses.

**To fix:** Implement streaming in each provider client (Anthropic and OpenAI both support streaming) and yield partial response SSE events.

#### 3. Token Revocation Missing (MEDIUM impact)

Logging out invalidates the session in the database, but **issued JWT tokens remain valid until expiry** (7 days). There's no token revocation list or server-side token validation.

**Impact:** If a token is stolen, it can be used for up to 7 days even after the user logs out.

**To fix:** Either implement a token blacklist (checked on every request) or switch to short-lived tokens (15-30 min) with frequent refresh. The former trades statelessness for security; the latter adds refresh overhead.

#### 4. Biometric Step-Up Auth Not Wired (MEDIUM impact)

The policy engine classifies HIGH-risk actions as requiring step-up authentication. The iOS client has biometric service tests. But **there's no backend endpoint to verify biometric auth** — the step-up auth path in the policy engine checks `request.step_up_verified` but nothing sets it to `True`.

**Impact:** HIGH-risk actions that should require biometric confirmation currently can't be properly authorized through the step-up flow.

### Architectural Concerns

#### 5. Privacy Classification Is Naive

The privacy router uses **keyword substring matching** ("journal", "diary", "private", "secret") to classify requests. It only examines the most recent user message, ignoring conversation context.

**Weaknesses:**
- "private company" or "diary industry" would trigger false private routing
- A multi-turn conversation about private topics might lose context on the next message
- No ML-based intent classification

**Acceptable because:** The fail-safe defaults to private, and users can always override explicitly. But this will need improvement for production quality.

#### 6. In-Memory State That Should Be Persistent

Several critical subsystems use in-memory state that's **lost on restart**:
- **Idempotency cache** (ToolGateway) — duplicate tool calls possible after restart
- **Rate limiting** (ToolGateway) — rate limits reset on restart
- **Tool-loop state** — if the container restarts mid-run, the run is lost

**Impact:** Acceptable for a single-user local deployment but would be problematic at scale.

#### 7. Tool Definition Fragmentation

Tool information is spread across three locations:
1. `TOOL_SCHEMAS` dict in `definitions.py` — function signatures
2. `TOOL_CAPABILITIES` dict in `capabilities.py` — permission model
3. Per-adapter config in `registration.py` — domain, auth

Changes must be coordinated across all three. There's no single registry that unifies them.

#### 8. Single-User Assumption

While the database has a `users` table and user-scoped queries, the system is fundamentally designed for a single user:
- No multi-tenancy isolation
- No per-user resource limits
- Google OAuth tokens shared at the account level
- Tool credentials not user-scoped (except `tool_capabilities`)

This is by design (personal AI agent), but it means Noa can't be trivially extended to serve multiple users.

#### 9. No Timeout at Orchestrator Level

The orchestrator has no built-in timeout. If an LLM provider hangs beyond the 60-second httpx timeout, or if a tool execution takes forever, the only protection is the httpx client timeout. There's no graph-level watchdog.

#### 10. Egress Control Is Advisory Only

The `noa.egress.allowlist` Docker label on the external worker specifies which domains it should be allowed to reach — but **Docker doesn't enforce this natively**. It requires an external proxy (not implemented). The external worker can currently reach any internet host.

#### 11. Private Worker Concurrency

The private worker's `MemoryStore` uses JSON-file-per-fact persistence with no locking or concurrency control. Concurrent writes from multiple requests could corrupt fact files. This is unlikely in single-user usage but is a theoretical concern.

#### 12. Checkpoint Table Unused

There's a `checkpoints` database table for persisting LangGraph state, but it's **not actually used** — graph state lives only in memory during execution. If the server crashes mid-run, that run's state is lost.

### What These Gaps Mean in Practice

For a **single-user, locally-deployed personal AI agent** (Noa's target), most of these are acceptable trade-offs:
- Token revocation matters less when only one person uses the system
- In-memory rate limits are fine for a single user
- Keyword-based privacy classification works when the user can override
- No streaming is a UX inconvenience, not a correctness issue

For **production/multi-user deployment**, these would need to be addressed in priority order: streaming → token revocation → RAG → biometric step-up → persistent idempotency.

---

## What's Built & What's Next

### Completed (Waves 1–23, 189 phases)

- **Foundation**: Project scaffold, Postgres schema, FastAPI, JWT auth, bcrypt passwords
- **Orchestration**: LangGraph state machine with conditional edges, runs/events, hash-chained audit logging, policy engine with 3 risk tiers
- **Domain Workers**: Private worker (Ollama, memory, RPC), external worker (4 LLM providers), Docker network isolation, privacy router
- **Tools**: Memory, Calendar, Gmail, Notion, Web Search. Tool gateway with idempotency, rate limits, capabilities, approval flow. Custom tool registration. MCP server connector.
- **Advanced Backend**: Cost control, output validation, task scheduling, durable queue, coding sandbox
- **Web Client**: React app with 10+ pages (Chat, Runs, Approvals, Tools, Settings, Cost, Memory, Queue, Artifacts). SSE streaming. Tailwind + Shadcn/ui.
- **iOS Client**: SwiftUI app (Chat, Settings, Approvals). Push notifications (APNs), voice recording (Whisper), offline queue, certificate pinning, biometric auth.
- **LLM Providers**: Anthropic, OpenAI, Google AI, Ollama — all wired with real httpx clients
- **Google OAuth2**: Full OAuth flow (backend + web + iOS) with encrypted token storage
- **Security**: Container hardening (read-only, dropped caps, resource limits), CSP headers, CORS, nh3/DOMPurify sanitization, structured logging with secret stripping
- **Operations**: Backup infrastructure (pg_dump + GPG), log rotation, health checks, TLS (Caddy), Docker healthchecks
- **Quality**: 2,400+ tests, 84% coverage, mypy strict (0 errors), ruff, Playwright E2E, mutation testing, CI/CD pipelines

### Coming Up

| Wave | Focus | Key Items |
|------|-------|-----------|
| **24** | Observability & Ops | Health dashboard, error rate tracking, alerting (ntfy), structured log aggregation, query performance audit |
| **24B** | Database Security | Postgres Row-Level Security for domain isolation (defense in depth beyond application-level WHERE clauses) |
| **25** | Polish & Capabilities | Microsoft Outlook (OAuth2 + Graph API), bundle optimization, voice UX, iOS widgets, new MCP servers |
| **Phase 2** | Physical Isolation | Dedicated Mac for private domain, mTLS, air-gapped network (container isolation → machine isolation) |

### Deployment Stages

| Stage | Backend | iOS App | Networking |
|-------|---------|---------|------------|
| **1 — Dev** (current) | Docker on Mac (localhost:8000) | Xcode direct install | Tailscale VPN mesh (100.x.x.x) |
| **2 — TestFlight** | Mac or small VPS (Hetzner/fly.io) | TestFlight distribution | Let's Encrypt / Cloudflare TLS |
| **3 — Production** | Dedicated server + domain + TLS | App Store / Ad Hoc | Certificate pinning active |

---

## Quick Reference

| I want to... | Do this |
|---|---|
| Read the full specification | Open `SPEC.md` |
| Understand the product strategy | Open `STRATEGY.md` |
| See what's been built | Check `Plan/PLAN.md` |
| Run the app locally | `docker-compose up` |
| Run tests | `pytest` |
| Run tests for one phase | `pytest -m f1` (replace with phase ID) |
| Check code quality | `ruff check src/ tests/ && mypy src/` |
| Add a database migration | `alembic revision --autogenerate -m "description"` |
| Find a QA review | Look in `Plan/REVIEWS/` |
| Understand an architecture decision | Check `Plan/ARCH_INVARIANTS.md` |
| See known issues | Check `Plan/FINDINGS.md` |
| Understand the orchestrator | Read `src/noa/orchestrator/graph.py` + `nodes/` |
| Understand tool dispatch | Read `src/noa/tools/gateway.py` |
| Understand privacy routing | Read `src/noa/privacy/classifier.py` |
| Understand LLM providers | Read `src/noa/external_worker/llm/router.py` |
| See all SSE event types | Read `src/noa/api/sse_types.py` |
| See all config options | Read `src/noa/config.py` |
