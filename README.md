# Noa

**A governed personal AI agent with dual-domain architecture.**

Run an AI agent on your own hardware that enforces privacy boundaries, governs every action through risk-tiered approvals, tracks costs, and integrates with Google Calendar, Gmail, Notion, and web search — with a React web UI and native iOS app.

Built as a portfolio project demonstrating applied agent engineering: LangGraph state machine orchestration, container-based domain isolation, function-level tool governance, immutable audit logging, multi-provider LLM routing, and production-grade infrastructure with 2,200+ tests.

---

## Table of Contents

- [Project Assumptions](#0-project-assumptions)
- [Problem Statement](#1-problem-statement)
- [What It Does](#2-what-it-does)
- [Architecture](#3-architecture)
- [Agent & Prompt Engineering](#4-agent--prompt-engineering)
- [Tech Stack](#5-tech-stack)
- [How to Run and Test](#6-how-to-run-and-test)
- [What to Review](#7-what-to-review)
- [Key Design Decisions](#8-key-design-decisions)
- [Known Risks and Limitations](#9-known-risks-and-limitations)
- [Questions for the Reviewer](#10-questions-for-the-reviewer)
- [Roadmap](#11-roadmap)

---

## 0. Project Assumptions

These assumptions define the project scope. All architecture and design decisions build on them.

- Single-user system running on personal hardware — no multi-tenant authentication
- Privacy enforcement is at the network level (container isolation), not row-level filtering
- Phase 1 uses Docker containers for domain isolation; Phase 2 targets physical machine isolation
- Secrets are managed via macOS Keychain at runtime — no `.env` files in production
- Local models (Ollama) handle private data; cloud APIs (Anthropic, OpenAI) handle external tasks
- All data stays on the user's machine (PostgreSQL on local Docker, no cloud persistence)

---

## 1. Problem Statement

Existing AI assistants operate as black boxes — they route all data through cloud servers, offer no governance over what actions the agent takes, provide no cost transparency, and give users no control over privacy boundaries. For power users who want an AI agent integrated into their daily workflow, this creates real problems:

- **Privacy**: Journal entries, personal notes, and financial data shouldn't leave the local machine
- **Governance**: Sending emails, creating calendar events, and modifying documents should require explicit approval, graduated by risk
- **Cost control**: Unbounded API calls to GPT-4 or Claude can generate surprising bills
- **Auditability**: No way to know what the agent did, when, and why

Noa addresses all four by enforcing:

- **Domain isolation** — private data processed by local models in a network-isolated container with no internet access
- **Risk-tiered approvals** — low-risk actions auto-approve, medium-risk show a preview, high-risk require biometric step-up authentication
- **Hard budget limits** — per-task, daily, and monthly cost caps enforced before execution
- **Immutable audit log** — every action recorded in a hash-chain log for tamper detection

---

## 2. What It Does

1. User sends a message in the **Chat** interface (web or iOS)
2. The **privacy router** classifies the request as private or external based on content analysis, tool dependencies, and user overrides
3. The **LangGraph orchestrator** runs the deterministic state machine: router → agent → tools → responder
4. The **agent node** invokes the appropriate LLM (local Ollama or cloud API) with available tools
5. **Tool calls** are dispatched through the governed gateway — rate-limited, idempotent, audited, risk-classified
6. Results stream back via **SSE** in real time with tool call visibility
7. The **cost tracker** records token usage and checks budget limits at every step

### Pages at a Glance

| Page | Purpose |
|------|---------|
| **Chat** | Main interface — send messages, stream responses, see tool calls in real time |
| **Runs** | History of all agent executions with token usage and cost per run |
| **Run Detail** | Deep-dive into a single run — full event stream (router, agent, tools, response) |
| **Approvals** | Pending human-in-the-loop decisions for medium/high-risk actions |
| **Tools** | Tool registry — health checks, capability toggles, custom tool registration |
| **Settings** | Model/provider selection, privacy mode, governance limits, Google OAuth |
| **Cost** | Token usage dashboard — breakdown by provider/model, daily/monthly trends |
| **Memory** | Long-term fact store — view, search, and manage remembered facts |
| **Queue** | Private domain task queue — tasks waiting when private worker is unavailable |
| **Artifacts** | Generated content — summaries, exports, draft documents |

### Dual-Domain Architecture

| Domain | Network | LLM | Tools | Internet |
|--------|---------|-----|-------|----------|
| **Private** | `noa-internal` (sealed) | Ollama (local) | Memory (remember/recall) | None |
| **External** | `noa-external` | Anthropic, OpenAI, Google AI | Calendar, Gmail, Notion, Web Search | HTTPS only |
| **Gateway** | Both networks | Routes between domains | All (governed) | Bridges both |

### Risk-Tiered Approval Model

| Tier | Examples | Approval | Step-Up Auth |
|------|----------|----------|--------------|
| **Low** | Web search, read emails, list events | Auto-approve | No |
| **Medium** | Send email, create event, write Notion | Preview + confirm | No |
| **High** | Delete data, system changes | Preview + confirm | Biometric (iOS) |

---

## 3. Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER DEVICES                                   │
│                                                                             │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│    │   React Web  │    │   iOS App    │    │   iOS App    │                │
│    │   (Vite)     │    │  (SwiftUI)   │    │  (Offline)   │                │
│    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
│           │                   │                   │                         │
│           └───────────────────┼───────────────────┘                         │
│                               │ HTTPS / SSE                                 │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────────┐
│                          DOCKER HOST                                        │
│                               │                                             │
│    ┌──────────────────────────▼──────────────────────────────────┐          │
│    │                    Caddy (Reverse Proxy)                     │          │
│    │              TLS termination, CORS, CSP headers              │          │
│    └──────────────────────────┬──────────────────────────────────┘          │
│                               │                                             │
│    ┌──────────────────────────▼──────────────────────────────────┐          │
│    │                      API Gateway                             │          │
│    │                   FastAPI (port 8000)                         │          │
│    │                                                              │          │
│    │  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────┐  │          │
│    │  │  Auth   │  │   Chat   │  │  Runs   │  │   Settings   │  │          │
│    │  │ (JWT)   │  │  (SSE)   │  │  Cost   │  │   Tools      │  │          │
│    │  └─────────┘  └────┬─────┘  └─────────┘  └──────────────┘  │          │
│    │                    │                                         │          │
│    │         ┌──────────▼──────────┐                             │          │
│    │         │   Orchestrator      │                             │          │
│    │         │  (LangGraph FSM)    │                             │          │
│    │         │                     │                             │          │
│    │         │  Router → Agent ──→ Tools ──→ Responder          │          │
│    │         │            ↑          │                            │          │
│    │         │            └──────────┘ (max 3 rounds)            │          │
│    │         └──────────┬──────────┘                             │          │
│    │                    │                                         │          │
│    │         ┌──────────▼──────────┐                             │          │
│    │         │   Privacy Router    │                             │          │
│    │         │   "private" or      │                             │          │
│    │         │   "external"?       │                             │          │
│    │         └────┬───────────┬────┘                             │          │
│    │              │           │                                   │          │
│    └──────────────┼───────────┼───────────────────────────────────┘          │
│                   │           │                                              │
│    ╔══════════════╧═══╗  ╔═══╧══════════════╗                              │
│    ║  noa-internal    ║  ║  noa-external    ║   ← Docker networks          │
│    ║  (NO INTERNET)   ║  ║  (HTTPS only)    ║                              │
│    ║                  ║  ║                  ║                              │
│    ║ ┌──────────────┐ ║  ║ ┌──────────────┐ ║                              │
│    ║ │   Private    │ ║  ║ │   External   │ ║                              │
│    ║ │   Worker     │ ║  ║ │   Worker     │ ║                              │
│    ║ │  (port 8001) │ ║  ║ │  (port 8002) │ ║                              │
│    ║ │              │ ║  ║ │              │ ║                              │
│    ║ │  ┌────────┐  │ ║  ║ │  ┌────────┐  │ ║                              │
│    ║ │  │ Ollama │  │ ║  ║ │  │Anthropic│  │ ║                              │
│    ║ │  │ (local)│  │ ║  ║ │  │ OpenAI  │  │ ║                              │
│    ║ │  └────────┘  │ ║  ║ │  │Google AI│  │ ║                              │
│    ║ │              │ ║  ║ │  └────────┘  │ ║                              │
│    ║ │  ┌────────┐  │ ║  ║ │              │ ║                              │
│    ║ │  │ Memory │  │ ║  ║ │  ┌────────┐  │ ║                              │
│    ║ │  │(private│  │ ║  ║ │  │ Memory │  │ ║                              │
│    ║ │  │ store) │  │ ║  ║ │  │(external│  │ ║                              │
│    ║ │  └────────┘  │ ║  ║ │  │ store) │  │ ║                              │
│    ║ └──────────────┘ ║  ║ │  └────────┘  │ ║                              │
│    ║                  ║  ║ │              │ ║                              │
│    ╚══════════════════╝  ║ │  ┌────────┐  │ ║                              │
│                          ║ │  │Calendar│  │ ║                              │
│                          ║ │  │ Gmail  │  │ ║                              │
│                          ║ │  │ Notion │  │ ║                              │
│                          ║ │  │Tavily  │  │ ║                              │
│                          ║ │  └────────┘  │ ║                              │
│                          ║ └──────────────┘ ║                              │
│                          ╚══════════════════╝                              │
│                                                                             │
│    ┌────────────────────────────────────────────┐                           │
│    │              PostgreSQL 16                  │                           │
│    │    Shared DB, domain-scoped queries          │                           │
│    │    (Phase 2: separate DBs per domain)        │                           │
│    │                                              │                           │
│    │  threads.domain = 'private' | 'external'    │                           │
│    │  All queries filtered by domain column       │                           │
│    └────────────────────────────────────────────┘                           │
│                                                                             │
│    ┌────────────────────────────────────────────┐                           │
│    │           Tool Gateway                      │                           │
│    │  Rate limit → Idempotency → Risk classify   │                           │
│    │  → Approval gate → Execute → Audit log      │                           │
│    │  → Cost track → Output validation            │                           │
│    └────────────────────────────────────────────┘                           │
│                                                                             │
│    ┌────────────────────────────────────────────┐                           │
│    │           Durable Queue                     │                           │
│    │  When private worker is down:               │                           │
│    │  Chat → Queue → Drain when available        │                           │
│    │  Tasks live until completed or cancelled     │                           │
│    └────────────────────────────────────────────┘                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key isolation guarantee:** The `noa-internal` Docker network has no internet route. Even if the private worker code had a bug that tried to phone home, the network layer blocks it. Private data (journals, personal notes, passwords) physically cannot leave the machine.

**Phase 2 upgrade path:** The shared PostgreSQL instance is a pragmatic Phase 1 choice. Phase 2 moves to physically separate databases per domain with Postgres Row-Level Security (RLS) as an intermediate hardening step.

### Orchestrator (LangGraph State Machine)

The orchestrator uses a fixed-topology LangGraph graph with conditional edges for bounded autonomy:

```
__start__ → ROUTER → AGENT ──(has tool_calls)──→ TOOLS ──(rounds < max)──→ AGENT
                        │                           │
                        └──(no tool_calls)──→ RESPONDER ←──(rounds >= max)──┘
                                                 │
                                              __end__
```

**Bounded autonomy:**
- Max 10 tool calls per agent step
- Max 3 tool-execution rounds (configurable per user)
- 120-second timeout (configurable per user)
- Cost tracking at every iteration

### Multi-Agent System

| Component | File | Role |
|-----------|------|------|
| **Router Node** | `orchestrator/nodes/router.py` | Privacy classification, model selection, tool filtering |
| **Agent Node** | `orchestrator/nodes/agent.py` | LLM invocation with function-calling |
| **Tool Node** | `orchestrator/nodes/tools.py` | Tool dispatch through governed gateway |
| **Responder Node** | `orchestrator/nodes/responder.py` | Final response formatting |
| **Tool Gateway** | `tools/gateway.py` | Rate limiting, idempotency, audit, cost tracking |
| **Privacy Classifier** | `privacy/classifier.py` | Content analysis + keyword detection for domain routing |
| **Policy Engine** | `policy/engine.py` | Risk tier classification and approval routing |
| **Private Worker** | `private_worker/app.py` | Ollama RPC server — memory, embeddings (no internet) |
| **External Worker** | `external_worker/app.py` | Cloud LLM dispatch — Anthropic, OpenAI, Google AI |

### Data Flow

```
User Message → Web UI / iOS App
    ↓
POST /api/v1/chat (SSE stream)
    ↓
OrchestratorRunner.run()
    ↓
LangGraph: router_node → agent_node → (conditional) tool_node → responder_node
    ↓
Provider dispatch (Anthropic / OpenAI / Google AI / Ollama)
    ↓
Tool calls → ToolGateway → Adapters (Google, Notion, Tavily, Memory)
    ↓
SSE event stream: meta → tool_calls → tool_results → response → done
    ↓
RunService persists Run + Events + UsageStats to PostgreSQL
```

### Project Structure

```
src/noa/
├── api/                  FastAPI routes (17 routers: auth, chat, runs, tools, settings, cost, etc.)
├── orchestrator/         LangGraph state machine (graph, runner, nodes)
├── tools/                Tool system (gateway, definitions, capabilities, adapters)
├── auth/                 JWT + OAuth (bcrypt, refresh rotation, session management)
├── policy/               Approval engine (risk tiers, step-up auth)
├── privacy/              Domain classifier (content analysis, keyword detection)
├── cost/                 Token tracking + budget enforcement (pricing tables, limits)
├── audit/                Immutable hash-chain audit log
├── memory/               Long-term fact persistence (semantic recall)
├── queue/                Durable task queue (offline resilience, exponential backoff)
├── settings/             User preferences persistence
├── db/                   SQLAlchemy async ORM (18+ models)
├── external_worker/      Cloud LLM dispatch (Anthropic, OpenAI, Google AI)
├── private_worker/       Local worker (Ollama, memory store, DLP)
└── validation/           Output validation — content filter (prompt injection, exfil URLs), size limits

web/src/
├── pages/                15 React pages (Chat, Runs, Approvals, Tools, Settings, Cost, etc.)
├── components/           Shared UI (chat bubbles, layout, Radix primitives)
├── api/                  HTTP client + SSE handler + types
├── auth/                 Auth context + token storage
└── hooks/                Custom React hooks

ios/Noa/
├── Services/             Async actors (APIClient, SSEClient, AuthService, OfflineQueue)
├── Views/                SwiftUI views (Chat, Settings, Approvals)
├── ViewModels/           MVVM view models
├── Models/               Codable API models
└── Configuration/        Environment, service factory, certificate pinning

tests/
├── unit/                 105 test files (~1,931 tests)
└── integration/          10 test files (~56 tests)

alembic/versions/         17 database migrations
docker/                   Per-service Dockerfiles + Caddyfile
```

---

## 4. Agent & Prompt Engineering

### 4a. System Prompt Design

The system prompt (`prompts/system_prompt.txt`) is the single source of truth — the UI reads from and writes to this file directly (no hidden backend overrides). Key design choices:

- **Bounded autonomy**: Explicitly states the tool-round and tool-call limits so the LLM self-governs
- **Approval awareness**: Instructions to explain and wait for confirmation before risky actions
- **Privacy transparency**: The agent knows private requests go to a local model
- **Error handling**: Instructions to report failures clearly rather than retry silently
- **Proactive memory**: Instructed to store user preferences and facts without being asked

### 4b. Privacy Classification

The router classifies each request into private or external domain:

| Signal | Priority | Example |
|--------|----------|---------|
| Explicit user override | Highest | User sets `privacy_mode: "private"` |
| Tool dependency | High | Request needs Gmail → external domain |
| Content analysis | Medium | Keywords like "journal", "diary", "password" → private |
| Fail-safe default | Lowest | Low confidence → defaults to private (safer) |

### 4c. Function Calling & Tool Governance

Tools are defined as JSON Schema specifications and dispatched through a governed gateway:

| Tool | Functions | Risk Tier | Domain |
|------|-----------|-----------|--------|
| **Web Search** | `web_search()` | Low | External |
| **Calendar** | `list_events()`, `create_event()` | Low / Medium | External |
| **Gmail** | `search_emails()`, `read_email()`, `send_email()` | Low / Medium | External |
| **Notion** | `search_pages()`, `read_page()`, `create_page()` | Low / Medium | External |
| **Memory** | `remember()`, `recall()` | Medium | Private |

**Gateway enforcement per call:**
1. Capability check — is this user allowed this function?
2. Rate limit — token-bucket per user per tool
3. Idempotency — deduplication via request hash (5-minute TTL)
4. Risk classification — route to approval if medium/high
5. Execution — dispatch to adapter
6. Output validation — size limit (1 MB) + content filter (prompt injection, exfiltration URL, system prompt leak detection); blocked results never reach the LLM
7. Audit — log tool name, args, result, cost, latency
8. Cost tracking — record tokens and USD cost

### 4d. Multi-Model Routing

The agent supports multiple LLM providers with cost-aware selection:

| Provider | Models | Input / Output (per 1M tokens) | Use Case |
|----------|--------|---------------------------------|----------|
| **Anthropic** | Claude Sonnet | $3.00 / $15.00 | Default external |
| **Anthropic** | Claude Haiku | $0.25 / $1.25 | Fast/cheap tasks |
| **Anthropic** | Claude Opus | $15.00 / $75.00 | Complex reasoning |
| **OpenAI** | GPT-4o | $2.50 / $10.00 | Alternative external |
| **OpenAI** | GPT-4o-mini | $0.15 / $0.60 | Budget-conscious |
| **OpenAI** | GPT-4.1 | $2.00 / $8.00 | Latest generation |
| **Ollama** | Any local model | Free | Private domain |

Users can override model and provider per-chat in the Settings page.

### 4e. Tool Chaining

The agent can chain tools across multiple rounds. Example:

```
User: "Find the latest news about AI regulation and email me a summary"

Round 1: web_search("AI regulation latest news 2026")
Round 2: send_email(to: user, subject: "AI Regulation Summary", body: <synthesized>)
         → Triggers Medium-risk approval gate → User approves → Email sent
```

The orchestrator loops back from tools → agent for up to 3 rounds (configurable), enabling multi-step task completion.

---

## 5. Tech Stack

| Category | Technology |
|----------|------------|
| **Language** | Python 3.11+ (backend), TypeScript (frontend), Swift 6 (iOS) |
| **Backend** | FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| **Orchestration** | LangGraph + LangChain Core (state machine, conditional edges) |
| **Database** | PostgreSQL 16 (asyncpg) |
| **Auth** | JWT (python-jose), bcrypt, Google OAuth 2.0 |
| **Cloud LLMs** | Anthropic SDK, OpenAI SDK, Google AI SDK |
| **Local LLM** | Ollama |
| **Frontend** | React 18, Vite, Tailwind CSS, Radix UI, TanStack Query, Zod |
| **iOS** | SwiftUI, async/await actors, ASWebAuthenticationSession |
| **Streaming** | Server-Sent Events (SSE) |
| **Reverse Proxy** | Caddy (TLS, Let's Encrypt) |
| **Containers** | Docker Compose (5 services, 2 isolated networks) |
| **Security** | nh3 (HTML sanitization), DOMPurify (frontend), certificate pinning (iOS) |
| **Testing** | pytest, Vitest, Playwright, XCTest, mutmut (mutation testing) |
| **Static Analysis** | ruff, mypy (strict), ESLint, TypeScript strict |

---

## 6. How to Run and Test

### Prerequisites

- Docker Desktop (macOS or Linux)
- Python 3.11+
- Node.js 18+ (for frontend)
- Ollama (optional, for private domain)

### Setup

```bash
git clone <this-repo> && cd Noa

# Store secrets in macOS Keychain (never in .env)
./tools/keychain_store.sh set ANTHROPIC_API_KEY "sk-ant-..."
./tools/keychain_store.sh set OPENAI_API_KEY "sk-..."

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec noa-api alembic upgrade head
```

### Development Mode

```bash
# Backend (with live reload)
docker-compose -f docker-compose.dev.yml up -d

# Frontend
cd web && npm install && npm run dev
# Opens at http://localhost:5173

# Optional: Pull Ollama models for private domain
ollama pull qwen2.5:14b
ollama pull llama3.3:70b
```

### Environment Variables

All secrets are injected via Keychain at runtime. Container configuration uses:

| Variable | Default | Purpose |
|----------|---------|---------|
| `NOA_DOMAIN` | `localhost` | Domain for Caddy TLS |
| `NOA_ACME_EMAIL` | `noa@localhost` | Let's Encrypt email |
| `DATABASE_URL` | (compose-provided) | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | (Keychain) | Anthropic API access |
| `OPENAI_API_KEY` | (Keychain) | OpenAI API access |

### Run Tests

```bash
# Backend — unit tests (fast, no external calls)
pytest tests/unit/ -v

# Backend — integration tests (requires running Postgres)
pytest tests/integration/ -v

# Backend — full suite with coverage
pytest tests/ --cov=src/noa --cov-report=html

# Static analysis
ruff check src/
mypy src/

# Frontend — unit tests
cd web && npm run test

# Frontend — E2E tests (Playwright)
cd web && npm run test:e2e

# Mutation testing (critical paths only)
mutmut run
```

Expected: **2,200+ tests passing**, 84% coverage, 0 mypy errors, 0 ruff violations.

### Test Coverage

| Test Area | Files | Tests | Covers |
|-----------|-------|-------|--------|
| Auth & sessions | 8 | ~120 | JWT, login, register, OAuth, refresh, lockout |
| Orchestrator | 12 | ~200 | Graph execution, state machine, conditional edges, tool dispatch |
| Tools & governance | 15 | ~250 | Each tool independently, gateway, capabilities, rate limiting |
| Privacy & domain isolation | 6 | ~80 | Router, classifier, DLP, cross-domain checks |
| Cost tracking | 4 | ~60 | Pricing, budget limits, usage aggregation |
| API endpoints | 20 | ~300 | All 17 routers, contract tests, error handling |
| Database & models | 8 | ~100 | ORM models, relationships, migrations, integrity |
| Queue & resilience | 4 | ~50 | Durable queue, backoff, idempotency, drain worker |
| Audit | 3 | ~40 | Hash chain, retention, queryability |
| Frontend (Vitest) | 11 | ~200 | Pages, components, API client, auth context |
| E2E (Playwright) | 5 | ~30 | Login, chat, settings, tools, approvals |
| iOS (XCTest) | 15 | ~240 | Models, services, view models, integration flows |
| **Total** | **~120** | **~2,200+** | |

---

## 7. What to Review

### Start Here

These 6 files cover the core architecture end-to-end:

| File | Description |
|------|-------------|
| `src/noa/orchestrator/graph.py` | LangGraph state machine — topology, conditional edges, bounded autonomy |
| `src/noa/orchestrator/runner.py` | Execution engine — compiles graph, streams SSE events, enforces timeout |
| `src/noa/tools/gateway.py` | Tool dispatch — rate limiting, idempotency, audit, cost tracking |
| `src/noa/orchestrator/nodes/router.py` | Privacy classification — domain routing, model selection |
| `src/noa/policy/engine.py` | Approval framework — risk tiers, step-up auth |
| `src/noa/api/v1/chat.py` | Chat endpoint — SSE streaming, orchestrator invocation |

### Additional Files

| File | Description |
|------|-------------|
| `src/noa/api/app.py` | FastAPI factory — lifespan, middleware, CORS, CSP headers |
| `src/noa/tools/definitions.py` | JSON Schema tool specs — 14 tools, risk tiers, domain metadata |
| `src/noa/tools/capabilities.py` | Capability checker — function-level grants, DB-backed |
| `src/noa/cost/pricing.py` | Provider pricing tables — per-model cost estimation |
| `src/noa/auth/service.py` | Auth service — JWT, refresh rotation, lockout |
| `src/noa/audit/service.py` | Audit service — hash-chain integrity, retention scheduling |
| `src/noa/queue/durable.py` | Durable queue — exponential backoff, idempotency window |
| `src/noa/privacy/classifier.py` | Privacy classifier — keyword detection, domain routing |
| `src/noa/settings/service.py` | Settings service — user preferences, governance limits |
| `prompts/system_prompt.txt` | Agent system prompt — single source of truth for agent personality |
| `web/src/pages/Chat.tsx` | Main chat UI — SSE streaming, tool call visualization |
| `web/src/api/sse.ts` | SSE client — event parsing, auto-reconnect |
| `docker-compose.yml` | Production deployment — 5 services, 2 isolated networks |

### Architectural Decisions to Validate

- Dual-domain isolation via Docker networks (not row-level filtering or encryption)
- LangGraph for deterministic outer shell with bounded LLM autonomy inside
- Fixed graph topology with conditional edges (not dynamic graph construction)
- File-based system prompt as single source of truth (UI reads/writes directly)
- Function-level tool capabilities (not just tool-level on/off)
- Hash-chain audit log for tamper detection
- Idempotency at the gateway level (not relying on LLM deduplication)
- PostgresCheckpointer for run state persistence and resumability
- JWT with httpOnly cookies (not localStorage) for session management
- macOS Keychain for secrets (not environment variables)

---

## 8. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Dual-domain network isolation** | Container-level network isolation guarantees private data never reaches the internet — simpler and stronger than row-level filtering or encryption at rest |
| **LangGraph deterministic orchestrator** | Fixed topology with conditional edges gives predictable execution while allowing multi-step tool chaining within bounded limits |
| **Risk-tiered approval model** | Graduated trust matches action consequence — read operations auto-approve, writes require confirmation, deletes require biometric |
| **Function-level tool governance** | Granting `gmail.read_email` without `gmail.send_email` gives fine-grained control that tool-level on/off cannot achieve |
| **Hard budget enforcement** | Cost limits are enforced before execution (not after) — prevents bill shock from runaway API calls |
| **Immutable hash-chain audit** | Each entry references the prior entry's hash — tampering is detectable without a separate integrity service |
| **File-based system prompt** | `prompts/system_prompt.txt` is the single source of truth — the UI reads and writes it directly, no hidden backend overrides |
| **SSE streaming with keepalive** | 15-second keepalive pings prevent proxy timeouts during long tool calls; clients see real-time tool execution |
| **Durable queue for resilience** | When the private domain is unavailable, tasks queue with exponential backoff rather than failing |
| **Multi-provider LLM routing** | Users pick the right model for each task — cheap and fast (Haiku/GPT-4o-mini) or powerful (Opus/GPT-4o) |
| **iOS native with certificate pinning** | SPKI-based pinning in release builds prevents MITM; offline queue handles network interruptions |

---

## 9. Known Risks and Limitations

| Risk | Status | Mitigation |
|------|--------|------------|
| Agent execution limits (max_tool_calls, max_retries) stored but not enforced in orchestrator | Open (W22-H1) | Values are persisted and UI-configurable; enforcement wiring is next priority |
| Approvals toggle stored but not checked by orchestrator | Open (W22-H2) | Toggle exists in UI and DB; orchestrator always enforces approvals currently |
| Runs/Cost endpoints not domain-filtered | Open (W22-M1) | Thread isolation is complete; run/cost filtering scheduled for next wave |
| Local model quality varies by hardware (70b needs significant VRAM) | By design | 3-tier model policy: 8b fast, 14b default, 70b judge — users select based on hardware |
| No multi-user authentication | By design | Single-user system running on personal hardware; profile isolation not user isolation |
| Single-machine container isolation (not physical) | Phase 1 | Phase 2 targets dedicated hardware for private domain with mTLS between machines |
| Knowledge graph / memory grows unbounded | Open | Manual clearing available; no automatic pruning yet |
| Ollama structured output depends on model compliance | Mitigated | JSON schema in API payload + repeated instructions in prompt |
| Cloud LLM costs can accumulate across tools | Mitigated | Hard per-task, daily, and monthly budget limits enforced before execution |

---

## 10. Questions for the Reviewer

1. **Domain isolation** — Is container-level network isolation sufficient for Phase 1, or should we add encryption at rest for the private domain before moving to physical isolation?
2. **Approval model** — Are the 3 risk tiers (Low/Medium/High) well-calibrated? Should there be a 4th tier for irreversible actions (e.g., "delete all emails matching...")?
3. **Tool governance** — Is function-level capability granting the right granularity, or is it over-engineered for a single-user system?
4. **Cost control** — Are hard limits (fail before execution) the right approach, or should there be a "soft warning" tier that prompts the user but allows override?
5. **Agent autonomy** — Is 3 tool-rounds with 10 calls per round the right balance between capability and safety?
6. **Biggest risk** — What is the single biggest architectural risk you see?

---

## 11. Roadmap

| Phase | Name | Scope | Status |
|-------|------|-------|--------|
| **Wave 22** | Stabilization | Wire agent limits, resolve dead-end stores, domain-filter runs/cost | In Progress |
| **Wave 23** | Observability | Lightweight monitoring, alerting, structured log aggregation | Planned |
| **Wave 24** | iOS Distribution | TestFlight beta, offline-first enhancements | Planned |
| **Phase 2** | Physical Isolation | Dedicated Mac for private domain, mTLS, air-gapped network | Planned |
| **Future** | MCP Server | Expose Noa as an MCP server for Claude Desktop integration | Planned |

See `Plan/PLAN.md` for detailed phase definitions and wave tracking (22 waves, 115+ phases).

---

## References

- `SPEC.md` — Authoritative product specification (97KB, 150+ sections)
- `docs/Tech.md` — Technical deep-dive (architecture, security, request flow)
- `docs/SETUP.md` — Full system setup guide
- `docs/RUNBOOK.md` — Operations and troubleshooting
- `docs/GETTING_STARTED.md` — Quick start for developers
- `Plan/PLAN.md` — Full wave and phase status tracking
- `Plan/FINDINGS.md` — Audit findings (156 total, 148 resolved)
- `Plan/TRACEABILITY.md` — Spec coverage matrix
- `CLAUDE.md` — Guidance for AI assistants working on this codebase

---

## License

Copyright (c) 2024–2026 Martin Noetzel. All rights reserved.

This software and its source code are proprietary. No part of this project may be copied, modified, distributed, or used without explicit written permission from the author.
