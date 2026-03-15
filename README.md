# Noa

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/typescript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![Swift 6](https://img.shields.io/badge/swift-6-orange.svg)](https://swift.org/)
[![Tests](https://img.shields.io/badge/tests-2%2C400%2B-brightgreen.svg)](#run-tests)
[![Coverage](https://img.shields.io/badge/coverage-84%25-brightgreen.svg)](#run-tests)
[![PostgreSQL 16](https://img.shields.io/badge/postgres-16-336791.svg)](https://www.postgresql.org/)

**A governed personal AI agent with dual-domain architecture.**

Run an AI agent on your own hardware that enforces privacy boundaries, governs every action through risk-tiered approvals, tracks costs, and integrates with Google Calendar, Gmail, Notion, and web search — with a React web UI and native iOS app.

Built as a portfolio project demonstrating applied agent engineering: LangGraph state machine orchestration, container-based domain isolation, function-level tool governance, immutable audit logging, multi-provider LLM routing, and production-grade infrastructure with 2,400+ tests.

<!-- TODO: Add demo GIF / screenshots here -->

## Quick Start

```bash
git clone <this-repo> && cd Noa
docker-compose up -d
docker-compose exec noa-api alembic upgrade head
# Frontend: cd web && npm install && npm run dev → http://localhost:5173
```

> See [docs/SETUP.md](docs/SETUP.md) for full setup including secret management and Ollama configuration.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Agent & Prompt Engineering](#agent--prompt-engineering)
- [Tech Stack](#tech-stack)
- [How to Run and Test](#how-to-run-and-test)
- [What to Review](#what-to-review)
- [Key Design Decisions](#key-design-decisions)
- [Known Risks and Limitations](#known-risks-and-limitations)
- [Questions for the Reviewer](#questions-for-the-reviewer)
- [Roadmap](#roadmap)

---

## Problem Statement

Existing AI assistants operate as black boxes — they route all data through cloud servers, offer no governance over what actions the agent takes, provide no cost transparency, and give users no control over privacy boundaries.

Noa addresses this by enforcing:

- **Domain isolation** — private data processed by local models in a network-isolated container with no internet access
- **Risk-tiered approvals** — low-risk actions auto-approve, medium-risk show a preview, high-risk require biometric step-up authentication
- **Hard budget limits** — per-task, daily, and monthly cost caps enforced before execution
- **Immutable audit log** — every action recorded in a hash-chain log for tamper detection

---

## What It Does

1. User sends a message in the **Chat** interface (web or iOS)
2. The **privacy router** classifies the request as private or external based on content analysis, tool dependencies, and user overrides
3. The **LangGraph orchestrator** runs the deterministic state machine: router → agent → tools → responder
4. The **agent node** invokes the appropriate LLM (local Ollama or cloud API) with available tools
5. **Tool calls** are dispatched through the governed gateway — rate-limited, idempotent, audited, risk-classified
6. Results stream back via **SSE** in real time with tool call visibility
7. The **cost tracker** records token usage and checks budget limits at every step

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

### Pages

Chat, Runs, Run Detail, Approvals, Tools, Settings, Cost, Memory, Queue, Artifacts — 10 pages across web and iOS.

---

## Architecture

### Orchestrator (LangGraph State Machine)

```
__start__ → ROUTER → AGENT ──(has tool_calls)──→ TOOLS ──(rounds < max)──→ AGENT
                        │                           │
                        └──(no tool_calls)──→ RESPONDER ←──(rounds >= max)──┘
                                                 │
                                              __end__
```

**Bounded autonomy:** Max 10 tool calls per step, max 3 rounds (configurable), 120-second timeout, cost tracking at every iteration.

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

**Key isolation guarantee:** The `noa-internal` Docker network has no internet route. Even if the private worker code had a bug that tried to phone home, the network layer blocks it. Private data physically cannot leave the machine.

> For the full system diagram, component table, and project structure, see [docs/Tech.md](docs/Tech.md).

---

## Agent & Prompt Engineering

### System Prompt

The system prompt (`prompts/system_prompt.txt`) is the single source of truth — the UI reads from and writes to this file directly (no hidden backend overrides). It enforces bounded autonomy, approval awareness, privacy transparency, and proactive memory.

### Privacy Classification

| Signal | Priority | Example |
|--------|----------|---------|
| Explicit user override | Highest | User sets `privacy_mode: "private"` |
| Tool dependency | High | Request needs Gmail → external domain |
| Content analysis | Medium | Keywords like "journal", "diary", "password" → private |
| Fail-safe default | Lowest | Low confidence → defaults to private (safer) |

### Tool Governance

Tools are dispatched through a governed gateway with 8-step enforcement per call: capability check → rate limit → idempotency → risk classification → execution → output validation → audit → cost tracking.

| Tool | Functions | Risk Tier | Domain |
|------|-----------|-----------|--------|
| **Web Search** | `web_search()` | Low | External |
| **Calendar** | `list_events()`, `create_event()` | Low / Medium | External |
| **Gmail** | `search_emails()`, `read_email()`, `send_email()` | Low / Medium | External |
| **Notion** | `search_pages()`, `read_page()`, `create_page()` | Low / Medium | External |
| **Memory** | `remember()`, `recall()` | Medium | Private |

### Multi-Model Routing

| Provider | Models | Input / Output (per 1M tokens) | Use Case |
|----------|--------|---------------------------------|----------|
| **Anthropic** | Claude Sonnet 4 | $3.00 / $15.00 | Default external |
| **Anthropic** | Claude Haiku 4.5 | $0.25 / $1.25 | Fast/cheap tasks |
| **Anthropic** | Claude Opus 4 | $15.00 / $75.00 | Complex reasoning |
| **OpenAI** | GPT-4o | $2.50 / $10.00 | Alternative external |
| **OpenAI** | GPT-4o-mini | $0.15 / $0.60 | Budget-conscious |
| **OpenAI** | GPT-4.1 | $2.00 / $8.00 | Latest generation |
| **OpenAI** | GPT-4.1-mini | $0.40 / $1.60 | Lightweight latest gen |
| **Ollama** | Any local model | Free | Private domain |

### Tool Chaining Example

```
User: "Find the latest news about AI regulation and email me a summary"

Round 1: web_search("AI regulation latest news 2026")
Round 2: send_email(to: user, subject: "AI Regulation Summary", body: <synthesized>)
         → Triggers Medium-risk approval gate → User approves → Email sent
```

---

## Tech Stack

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

## How to Run and Test

### Prerequisites

- Docker Desktop (macOS or Linux)
- Python 3.11+
- Node.js 18+ (for frontend)
- Ollama (optional, for private domain)

### Setup

```bash
git clone <this-repo> && cd Noa

# Store secrets (macOS Keychain or environment variables)
# macOS:
./tools/keychain_store.sh set ANTHROPIC_API_KEY "sk-ant-..."
./tools/keychain_store.sh set OPENAI_API_KEY "sk-..."
# Linux/CI: export ANTHROPIC_API_KEY=... and OPENAI_API_KEY=...

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

### Run Tests

```bash
# Backend tests
pytest tests/unit/ -v                         # Unit tests (fast)
pytest tests/integration/ -v                  # Integration (requires Postgres)
pytest tests/ --cov=src/noa --cov-report=html # Full suite + coverage

# Static analysis
ruff check src/ && mypy src/

# Frontend tests
cd web && npm run test                        # Vitest
cd web && npm run test:e2e                    # Playwright E2E

# Mutation testing (critical paths)
mutmut run
```

Expected: **2,400+ tests passing**, 84% coverage, 0 mypy errors, 0 ruff violations.

> For the full test coverage breakdown by area, see [docs/Tech.md](docs/Tech.md#testing).

---

## What to Review

### Start Here (6 files)

| File | Description |
|------|-------------|
| `src/noa/orchestrator/graph.py` | LangGraph state machine — topology, conditional edges, bounded autonomy |
| `src/noa/orchestrator/runner.py` | Execution engine — compiles graph, streams SSE events, enforces timeout |
| `src/noa/tools/gateway.py` | Tool dispatch — rate limiting, idempotency, audit, cost tracking |
| `src/noa/orchestrator/nodes/router.py` | Privacy classification — domain routing, model selection |
| `src/noa/policy/engine.py` | Approval framework — risk tiers, step-up auth |
| `src/noa/api/v1/chat.py` | Chat endpoint — SSE streaming, orchestrator invocation |

### Architectural Decisions to Validate

- Dual-domain isolation via Docker networks (not row-level filtering or encryption)
- LangGraph for deterministic outer shell with bounded LLM autonomy inside
- Fixed graph topology with conditional edges (not dynamic graph construction)
- File-based system prompt as single source of truth (UI reads/writes directly)
- Function-level tool capabilities (not just tool-level on/off)
- Hash-chain audit log for tamper detection
- Idempotency at the gateway level (not relying on LLM deduplication)
- JWT with httpOnly cookies (not localStorage) for session management

> For the full file list (13 additional files), see [docs/Tech.md](docs/Tech.md#key-components-deep-dive).

---

## Key Design Decisions

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
| **Multi-provider LLM routing** | Users pick the right model for each task — cheap and fast (Haiku/GPT-4o-mini) or powerful (Opus/GPT-4o) |
| **iOS native with certificate pinning** | SPKI-based pinning in release builds prevents MITM; offline queue handles network interruptions |

---

## Known Risks and Limitations

| Risk | Status | Mitigation |
|------|--------|------------|
| Local model quality varies by hardware (70b needs significant VRAM) | By design | 3-tier model policy: 8b fast, 14b default, 70b judge — users select based on hardware |
| No multi-user authentication | By design | Single-user system running on personal hardware; profile isolation not user isolation |
| Single-machine container isolation (not physical) | Phase 1 | Phase 2 targets dedicated hardware for private domain with mTLS between machines |
| Knowledge graph / memory grows unbounded | Open | Manual clearing available; no automatic pruning yet |
| Ollama structured output depends on model compliance | Mitigated | JSON schema in API payload + repeated instructions in prompt |
| Cloud LLM costs can accumulate across tools | Mitigated | Hard per-task, daily, and monthly budget limits enforced before execution |

---

## Questions for the Reviewer

1. **Domain isolation** — Is container-level network isolation sufficient for Phase 1, or should we add encryption at rest for the private domain before moving to physical isolation?
2. **Approval model** — Are the 3 risk tiers (Low/Medium/High) well-calibrated? Should there be a 4th tier for irreversible actions (e.g., "delete all emails matching...")?
3. **Tool governance** — Is function-level capability granting the right granularity, or is it over-engineered for a single-user system?
4. **Cost control** — Are hard limits (fail before execution) the right approach, or should there be a "soft warning" tier that prompts the user but allows override?
5. **Agent autonomy** — Is 3 tool-rounds with 10 calls per round the right balance between capability and safety?
6. **Biggest risk** — What is the single biggest architectural risk you see?

---

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **Waves 1-22** | Core platform: backend, iOS, web, tools, governance, domain isolation, quality infra (130 phases) | Complete |
| **Auth Stability** | Session validation, error clarity, 7-day tokens, startup check | Complete |
| **Wave 23** | Observability: health dashboard, error rate tracking, alerting, structured log aggregation | Planned |
| **Wave 23B** | DB Security: Postgres Row-Level Security (RLS) for domain isolation | Planned |
| **Wave 24** | Polish: Microsoft Outlook, bundle optimization, voice UX, iOS widgets | Planned |
| **Phase 2** | Physical isolation: dedicated Mac for private domain, mTLS, air-gapped network | Planned |
| **Future** | MCP Server: expose Noa as an MCP server for Claude Desktop integration | Planned |

---

## References

- [docs/Tech.md](docs/Tech.md) — Technical deep-dive (architecture diagrams, component tables, project structure, test coverage)
- [docs/SETUP.md](docs/SETUP.md) — Full system setup guide
- [docs/RUNBOOK.md](docs/RUNBOOK.md) — Operations and troubleshooting
- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — Quick start for developers
- `SPEC.md` — Authoritative product specification (97KB, 150+ sections)
- `Plan/PLAN.md` — Full wave and phase status tracking (22 waves, 130 phases)
- `Plan/TRACEABILITY.md` — Spec coverage matrix

---

## License

Copyright (c) 2024-2026 Martin Noetzel. All rights reserved.

This software and its source code are proprietary. No part of this project may be copied, modified, distributed, or used without explicit written permission from the author.
