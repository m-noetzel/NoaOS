# Noa Technical Guide

> A practical guide for engineers joining the Noa project.
> Last updated: 2026-03-05

---

## Table of Contents

1. [What Is Noa?](#what-is-noa)
2. [Architecture Overview](#architecture-overview)
3. [The Dual-Domain Model](#the-dual-domain-model)
4. [How a Request Flows Through the System](#how-a-request-flows-through-the-system)
5. [Tech Stack & Why We Chose It](#tech-stack--why-we-chose-it)
6. [Project Structure](#project-structure)
7. [Key Components Deep-Dive](#key-components-deep-dive)
8. [Database & Migrations](#database--migrations)
9. [Security Model](#security-model)
10. [Docker & Networking](#docker--networking)
11. [Testing](#testing)
12. [Development Workflow](#development-workflow)
13. [Configuration](#configuration)
14. [What's Built & What's Next](#whats-built--whats-next)

---

## What Is Noa?

Noa is a **governed personal AI agent** that runs entirely on local hardware. Think of it as a personal assistant that can read your emails, manage your calendar, search the web, and remember things about you -- but with strict rules about **what it can do**, **when it needs your permission**, and **where your private data goes**.

The two core principles:

1. **Your private data never leaves your machine.** Journals, personal notes, and sensitive information stay in a sealed container with no internet access.
2. **Every action is governed.** Noa classifies actions by risk level. Low-risk actions (like a web search) happen automatically. High-risk actions (like sending an email) require your explicit approval.

---

## Architecture Overview

```
+------------------------------------------------------------------+
|                        YOUR MACHINE                               |
|                                                                   |
|  +------------------+        +--------------------------------+   |
|  |   Web Client     |        |   CLI (future)                 |   |
|  |   (React)        |        |                                |   |
|  +--------+---------+        +---------------+----------------+   |
|           |          HTTP (port 8000)         |                   |
|           +----------------+-----------------+                    |
|                            |                                      |
|                 +----------v-----------+                          |
|                 |      noa-api         |                          |
|                 |  (FastAPI Gateway)   |                          |
|                 |                      |                          |
|                 |  - Auth (JWT)        |                          |
|                 |  - Orchestrator      |                          |
|                 |  - Policy Engine     |                          |
|                 |  - Privacy Router    |                          |
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
|  | - Local files  |  | DB     |  | - Tools      | |                |
|  +---------------+  +--------+  +--------------+ |                |
|                                                                   |
+------------------------------------------------------------------+
```

**Key idea:** The `noa-api` container sits on *both* networks. It's the only bridge between the sealed private world and the internet-connected external world. Nothing else crosses that boundary.

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
||  - RAG vector store      ||     ||  - Code execution        ||
||                          ||     ||                          ||
||  AI Model: Ollama        ||     ||  AI Models: Claude,      ||
||  (runs locally)          ||     ||  GPT-4, etc.             ||
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
       |                    (e.g., "send email" -> external)
       v  (no tools?)
3. Content analysis      -- Keywords like "journal", "private", "secret"
       |                    trigger private routing
       v  (low confidence?)
4. Fail-safe             -- Default to PRIVATE (safe fallback)
```

---

## How a Request Flows Through the System

Here's what happens when you type "What's on my calendar today?" into Noa:

```
User types message
        |
        v
[1] POST /api/v1/runs
        |
        v
[2] Auth middleware validates JWT token
        |
        v
[3] Run created (status: pending -> running)
        |
        v
[4] LangGraph orchestrator starts
        |
        +---> [router node]
        |       Classifies: "calendar" -> EXTERNAL domain
        |       Selects model: Claude (via Anthropic API)
        |
        +---> [agent node]
        |       LLM decides: "I need to call the calendar tool"
        |
        +---> [tools node]
        |       Policy engine checks risk: read_calendar -> LOW
        |       Auto-approved (no user prompt needed)
        |       Calls calendar API, gets today's events
        |
        +---> [responder node]
                Formats response: "You have 3 meetings today..."
                |
                v
[5] Events streamed via SSE to client
        |
        v
[6] Run completed, audit log entry written (hash-chained)
```

### The LangGraph Pipeline (Fixed Topology)

The orchestrator always follows this exact sequence -- no dynamic branching:

```
__start__ --> router --> agent --> tools --> responder --> __end__
    |                                                        |
    |           (may loop: agent <-> tools)                  |
    +------------ fixed, deterministic path -----------------+
```

This is intentional. A fixed topology means the system is predictable and auditable. You always know what step Noa is on.

---

## Tech Stack & Why We Chose It

### Core Framework Choices

| Technology | What It Does | Why We Chose It |
|---|---|---|
| **Python 3.11** | Language | Dominant in AI/ML ecosystem. Async support mature. Huge library ecosystem for LLM integrations. |
| **FastAPI** | Web framework | Async-native, automatic OpenAPI docs, Pydantic integration for request validation. The fastest Python web framework for async workloads. |
| **LangGraph** | AI orchestration | Gives us a *deterministic* state machine for LLM workflows. Unlike raw LangChain, LangGraph lets us define fixed node topologies -- critical for governance. The agent can't "go rogue" outside the defined graph. |
| **PostgreSQL 16** | Database | Battle-tested relational DB. Handles our structured data (users, runs, audit logs) well. The `asyncpg` driver gives us true async I/O. |
| **SQLAlchemy 2.0** | ORM | Industry standard Python ORM. Version 2.0 has native async support. Type-safe query building. |
| **Docker** | Containerization | *The* mechanism for domain isolation. Docker networks enforce the private/external boundary at the OS level, not just in code. |

### Why These Specific Choices Matter

**LangGraph over raw LangChain:** LangChain is flexible but chaotic -- agents can call arbitrary chains of tools in unpredictable order. LangGraph forces us to define a state machine (`router -> agent -> tools -> responder`). For a *governed* AI agent, predictability is a feature, not a limitation.

**FastAPI over Django/Flask:** Django is too opinionated and synchronous-first. Flask lacks built-in async. FastAPI gives us async request handling (critical when waiting on LLM API responses that take seconds), automatic request validation via Pydantic, and auto-generated API documentation.

**PostgreSQL over SQLite:** We need concurrent access from multiple containers (api, workers), ACID transactions for audit logs, and the ability to scale. SQLite can't handle concurrent writes from multiple processes.

**Pydantic everywhere:** Pydantic validates data at every boundary -- API requests, config loading, RPC messages between domains. If bad data enters the system, Pydantic catches it immediately with clear error messages. We use `pydantic-settings` for 12-factor app configuration (all config via environment variables).

### Supporting Libraries

| Library | Purpose |
|---|---|
| **structlog** | Structured JSON logging. Every log line is machine-parseable. Automatically strips secrets from log output. |
| **httpx** | Async HTTP client for calling LLM APIs and inter-service communication. Drop-in replacement for `requests` with async support. |
| **python-jose** | JWT token creation and validation for authentication. |
| **passlib + bcrypt** | Secure password hashing. bcrypt is deliberately slow to resist brute-force attacks. |
| **Alembic** | Database migration management. Tracks schema changes as versioned migration files so we can upgrade/rollback safely. |
| **ruff** | Ultra-fast Python linter and formatter. Replaces flake8, isort, and black in a single tool. |
| **mypy** | Static type checker in strict mode. Catches type errors before runtime. |
| **pytest** | Testing framework with async support via `pytest-asyncio`. |

---

## Project Structure

```
/workspace/
|
+-- SPEC.md                    # THE source of truth (read this first)
+-- STRATEGY.md                # Product strategy (Noa + TheCoach)
+-- CLAUDE.md                  # AI agent orchestration protocol
|
+-- src/noa/                   # Application code
|   +-- __init__.py
|   +-- config.py              # Settings (env vars -> Pydantic model)
|   |
|   +-- api/                   # HTTP layer (FastAPI)
|   |   +-- app.py             # App factory + lifespan
|   |   +-- app_state.py       # Shared state (DB engine, sessions)
|   |   +-- middleware.py       # Request ID, error handling
|   |   +-- deps.py            # Dependency injection
|   |   +-- v1/                # Versioned endpoints
|   |   |   +-- health.py      # GET /health, GET /ready
|   |   |   +-- auth.py        # POST /token, /refresh, /logout
|   |   |   +-- runs.py        # POST /runs, GET /runs/{id}/events
|   |   |   +-- approvals.py   # GET/POST /approvals
|   |   +-- schemas/           # Request/response models
|   |
|   +-- auth/                  # Authentication
|   |   +-- service.py         # User CRUD, token management
|   |   +-- jwt.py             # JWT encode/decode
|   |   +-- password.py        # bcrypt hashing
|   |   +-- middleware.py       # @require_auth decorator
|   |
|   +-- orchestrator/          # LangGraph AI pipeline
|   |   +-- graph.py           # State machine definition
|   |   +-- state.py           # AgentState (messages, mode, costs)
|   |   +-- checkpointer.py    # Conversation state persistence
|   |   +-- nodes/
|   |       +-- router.py      # Privacy classification + model selection
|   |       +-- agent.py       # LLM decision-making
|   |       +-- tools.py       # Tool execution
|   |       +-- responder.py   # Response formatting
|   |
|   +-- privacy/               # Privacy classification
|   |   +-- classifier.py      # 4-level routing logic
|   |   +-- metrics.py         # Confidence scoring
|   |
|   +-- policy/                # Action governance
|   |   +-- engine.py          # Risk tier classification
|   |   +-- approval.py        # Approval state machine
|   |   +-- preview.py         # Dry-run preview generation
|   |   +-- schemas.py         # Approval models
|   |
|   +-- runs/                  # Run execution tracking
|   |   +-- service.py         # Run CRUD
|   |   +-- events.py          # Append-only event log
|   |
|   +-- audit/                 # Audit logging
|   |   +-- logging.py         # Structured JSON logger
|   |   +-- service.py         # Hash-chain audit trail
|   |   +-- integrity.py       # Chain verification
|   |
|   +-- private_worker/        # Private domain worker
|   |   +-- app.py             # FastAPI app
|   |   +-- rpc.py             # RPC contract validation
|   |   +-- ollama_client.py   # Local LLM client
|   |   +-- dlp.py             # Data loss prevention
|   |   +-- handlers.py        # Task handlers
|   |
|   +-- external_worker/       # External domain worker
|   |   +-- app.py             # FastAPI app
|   |   +-- llm/               # LLM provider abstraction
|   |   |   +-- router.py      # Model selection
|   |   |   +-- anthropic.py   # Anthropic (Claude) client
|   |   |   +-- openai.py      # OpenAI (GPT) client
|   |   +-- tools/             # Tool integrations
|   |
|   +-- db/                    # Database layer
|       +-- base.py            # SQLAlchemy base
|       +-- session.py         # Async session factory
|       +-- models/            # ORM models
|           +-- user.py
|           +-- session.py
|           +-- conversation.py
|           +-- run.py
|           +-- approval.py
|           +-- artifact.py
|           +-- audit.py
|           +-- task_queue.py
|           +-- usage.py
|
+-- tests/                     # Test suite
|   +-- conftest.py            # Shared fixtures
|   +-- unit/                  # Unit tests (no external deps)
|   +-- integration/           # Integration tests (Docker)
|
+-- docker/                    # Dockerfiles
+-- docker-compose.yml         # Production-like deployment
+-- docker-compose.dev.yml     # Dev environment
+-- alembic/                   # Database migrations
+-- scripts/                   # Utility scripts
+-- tools/                     # Dev tools (e.g., notify.py)
+-- Plan/                      # Planning docs, reviews, retros
+-- pyproject.toml             # Python project config
+-- Makefile                   # Common dev commands
```

---

## Key Components Deep-Dive

### The Orchestrator (`src/noa/orchestrator/`)

This is the brain of Noa. It uses LangGraph to define a state machine:

```python
# Simplified from graph.py
graph = StateGraph(AgentState)

graph.add_node("router",    router_node)    # Classify & pick model
graph.add_node("agent",     agent_node)     # LLM generates response/tool calls
graph.add_node("tools",     tools_node)     # Execute tool calls
graph.add_node("responder", responder_node) # Format final output

graph.add_edge(START,        "router")
graph.add_edge("router",    "agent")
graph.add_edge("agent",     "tools")        # or -> responder if no tools needed
graph.add_edge("tools",     "responder")
graph.add_edge("responder", END)
```

The `AgentState` is a TypedDict that flows through every node:

```python
class AgentState(TypedDict):
    messages: list          # Conversation history
    privacy_mode: str       # "private" or "external"
    selected_model: str     # Which LLM to use
    requested_tools: list   # Tools the LLM wants to call
    tool_results: list      # Results from tool execution
    total_cost: float       # Running cost for this run
    risk_tier: str          # "low", "medium", "high"
```

### The Policy Engine (`src/noa/policy/`)

Every tool call goes through the policy engine before execution:

```
Tool call requested
        |
        v
+-- Policy Engine classifies risk tier --+
|                                         |
|  LOW:    web_search, memory_recall      |  --> Auto-approve
|  MEDIUM: send_email, create_event       |  --> Show preview, ask user
|  HIGH:   delete_email, modify_system    |  --> Preview + step-up auth
|                                         |
+-----------------------------------------+
```

### The Audit System (`src/noa/audit/`)

Every significant action creates an audit log entry. Entries are chained:

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

### RPC Contract (`src/noa/private_worker/rpc.py`)

Communication between the API gateway and the private worker follows a strict contract:

```
noa-api                                    private-worker
   |                                            |
   |  POST /rpc                                 |
   |  {                                         |
   |    "idempotency_key": "uuid",              |
   |    "task_type": "recall",     <-- must be in allowed set
   |    "query": "therapist name", <-- max 4096 chars
   |    "max_tokens": 256          <-- max 4096
   |  }                                         |
   |  Total payload: max 16 KB                  |
   | -----------------------------------------> |
   |                                            |
   |  200 OK                                    |
   |  {                                         |
   |    "sensitivity_label": "high",            |
   |    "answer": "Dr. Smith",                  |
   |    "facts": [...]             <-- max 20 items
   |  }                                         |
   |  Total response: max 64 KB                 |
   | <----------------------------------------- |
```

The contract is validated on both sides. If either side sends malformed data, it's rejected. After 3 violations in 24 hours, the worker is paused automatically.

---

## Database & Migrations

### Key Tables

```
+-------------+     +-------------+     +-------------+
|   users     |---->|  sessions   |     | audit_log   |
| - email     |     | - token     |     | - event     |
| - pass_hash |     | - expiry    |     | - data      |
| - is_active |     | - user_id   |     | - prev_hash |
+------+------+     +-------------+     | - hash      |
       |                                +-------------+
       |
       v
+------+--------+     +-----------+     +-------------+
| conversations |---->|   runs    |---->| run_events  |
| - title       |     | - status  |     | - type      |
| - user_id     |     | - risk    |     | - data      |
+---------------+     | - privacy |     | - timestamp |
                      +-----+-----+     +-------------+
                            |
                            v
                      +-----+-----+     +-------------+
                      | approvals |     | usage_stats |
                      | - status  |     | - tokens    |
                      | - action  |     | - cost      |
                      +-----------+     +-------------+
```

### Running Migrations

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after changing models
alembic revision --autogenerate -m "describe the change"

# Rollback one step
alembic downgrade -1
```

Migrations are in `alembic/versions/`. Every migration has both `upgrade()` and `downgrade()` functions so changes are reversible.

---

## Security Model

### Authentication Flow

```
[User]                    [noa-api]                   [Database]
  |                          |                            |
  |  POST /api/v1/token      |                            |
  |  {email, password}       |                            |
  | -----------------------> |                            |
  |                          |  Verify bcrypt hash        |
  |                          | -------------------------> |
  |                          | <------------------------- |
  |                          |                            |
  |  {access_token (30min),  |                            |
  |   refresh_token (7days)} |                            |
  | <----------------------- |                            |
  |                          |                            |
  |  GET /api/v1/runs        |                            |
  |  Authorization: Bearer   |                            |
  |  <access_token>          |                            |
  | -----------------------> |                            |
  |                          |  @require_auth validates   |
  |                          |  JWT signature + expiry    |
  |  200 OK {runs: [...]}   |                            |
  | <----------------------- |                            |
```

### Container Hardening

Every worker container runs with:
- **Read-only filesystem** -- can't write to system directories
- **All capabilities dropped** -- no `NET_RAW`, no `SYS_ADMIN`, nothing
- **no-new-privileges** -- can't escalate via setuid binaries
- **Non-root user** (`noa:noa`) -- even if exploited, limited damage
- **tmpfs volumes** limited to 256MB -- prevents disk-filling attacks

---

## Docker & Networking

### Container Map

```
docker-compose.yml
|
+-- noa-api (port 8000)
|   |-- Networks: noa-internal + noa-external (GATEWAY)
|   |-- Depends on: postgres
|   +-- Role: FastAPI app, orchestrator, auth, policy
|
+-- postgres (port 5432)
|   |-- Network: noa-internal only
|   |-- Volume: postgres-data (persistent)
|   +-- Role: Control-plane database
|
+-- private-worker (port 8001)
|   |-- Network: noa-internal only (NO INTERNET)
|   |-- Volume: private-data (encrypted storage)
|   +-- Role: Ollama, memory, RAG
|
+-- external-worker (port 8002)
    |-- Network: noa-external only (HAS INTERNET)
    |-- Volume: coding-workspace (sandbox)
    +-- Role: LLM APIs, tool integrations
```

### Network Isolation

```
                      INTERNET
                         |
                    +---------+
                    | firewall|
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
     +----+----+                   +----+----+
     | postgres|                   | private |
     |         |                   | worker  |
     +---------+                   +---------+
```

The `noa-internal` network has `internal: true` in Docker Compose, which means Docker itself blocks any route to the internet. This isn't just a firewall rule -- the network physically has no gateway to the outside.

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run a specific phase's tests
pytest -m f1          # Foundation phase 1
pytest -m oc2         # Orchestration phase 2
pytest -m dw4         # Domain worker phase 4

# Run with coverage
pytest --cov=src/noa --cov-report=term-missing

# Run static checks (must pass before merge)
ruff check src/ tests/
mypy src/
```

### Test Philosophy

Every test traces back to SPEC.md. You'll see comments like:

```python
def test_private_worker_rejects_oversized_payload():
    """§9.2: Request payload must not exceed 16 KB."""
    ...
```

Tests follow a strict red-green cycle:
1. Write tests that **fail** (red phase)
2. Write code to make them **pass** (green phase)
3. Never merge if tests don't pass

### Test Markers

Tests are tagged by implementation phase so you can run just the tests for what you're working on:

| Marker | Wave | What It Covers |
|---|---|---|
| `f1`-`f4` | Foundation | Config, DB schema, FastAPI, Auth |
| `oc1`-`oc4` | Orchestration | LangGraph, Runs, Audit, Policy |
| `dw1`-`dw4` | Domain Workers | Private worker, External worker, Networking, Privacy |

---

## Development Workflow

### Phase Execution Pipeline

Every feature follows this pipeline:

```
  Plan           Test            Code          Code Review       QA Review
+--------+    +--------+    +----------+    +------------+    +-----------+
| Define |    | Write  |    | Write    |    | Fast code  |    |  QA agent |
| phase  |--->| failing|--->| code to  |--->| review     |--->|  reviews  |
| in     |    | tests  |    | pass     |    | (sonnet)   |    |  against  |
| master |    | (red)  |    | tests    |    | fix obvious|    |  checklist|
| plan   |    |        |    | (green)  |    | issues     |    |           |
+--------+    +--------+    +----------+    +------------+    +-----------+
                  |              |               |                  |
                  v              v               v                  v
              "At least      "All tests      APPROVE or        PASS: merge
               1 test         pass +          REQUEST_          FAIL: fix &
               must FAIL"     ruff + mypy"    CHANGES"          re-review
```

### Git Conventions

- **Branches:** `agent/<agent_id>-<task_slug>` (e.g., `agent/qa-dw4-review`)
- **Commits:** `<scope>: <summary>` (e.g., `dw3: implement Docker network isolation`)
- **Merges:** Always `--no-ff` (preserves branch history)
- **No force-push.** Ever.

### Code Quality Gates

Before any merge to `main`, these must pass:

```bash
ruff check src/ tests/    # Linting (style, imports, security)
mypy src/                 # Type checking (strict mode)
pytest                    # All tests green
```

---

## Configuration

All configuration flows through environment variables (12-factor app). The `Settings` class in `src/noa/config.py` validates everything at startup:

```bash
# Core
NOA_ENV=development              # development | production | testing
API_HOST=127.0.0.1               # Bind address (localhost only!)
API_PORT=8000                     # API port

# Database
DATABASE_URL=postgresql+asyncpg://noa:noa@localhost:5432/noa

# Security
SECRET_KEY=change-me-in-prod     # JWT signing key (MUST change in prod)
ACCESS_TOKEN_EXPIRE_MINUTES=30   # Short-lived access tokens
REFRESH_TOKEN_EXPIRE_DAYS=7      # Longer-lived refresh tokens

# Logging
LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR
```

**Important:** In production mode, the app refuses to start if `SECRET_KEY` is still the dev default. This is a deliberate safety catch.

Copy `.env.example` to `.env` and adjust values for your setup.

---

## What's Built & What's Next

### Completed (Waves 1-3)

```
Wave 1: Foundation          Wave 2: Orchestration       Wave 3: Domain Workers
+---------------------+    +---------------------+     +---------------------+
| [x] Project scaffold|    | [x] LangGraph graph |     | [x] Private worker  |
| [x] Postgres schema |    | [x] Run/Event model |     | [x] External worker |
| [x] FastAPI skeleton|    | [x] Audit logging   |     | [x] Network isolation|
| [x] JWT auth        |    | [x] Policy engine   |     | [x] Privacy router  |
+---------------------+    +---------------------+     +---------------------+
```

### Coming Up

```
Wave 4: Tools               Wave 5: Advanced Backend    Wave 6: Web Client
+---------------------+    +---------------------+     +---------------------+
| [ ] Memory tool     |    | [ ] Cost control    |     | [ ] React chat UI   |
| [ ] Calendar tool   |    | [ ] Output validation|    | [ ] Run timeline    |
| [ ] Gmail tool      |    | [ ] Scheduling      |     | [ ] Approval UI     |
| [ ] Notion tool     |    | [ ] Durable queue   |     | [ ] Task queue viz  |
| [ ] Web search      |    | [ ] Coding sandbox  |     | [ ] Memory audit UI |
| [ ] Tool governance |    |                     |     |                     |
+---------------------+    +---------------------+     +---------------------+
```

---

## Quick Reference

| I want to... | Do this |
|---|---|
| Read the full specification | Open `SPEC.md` |
| Understand the product strategy | Open `STRATEGY.md` |
| See what's been built | Check `Plan/PLAN.md` |
| Run the app locally | `docker-compose up` |
| Run tests | `pytest` |
| Run tests for one phase | `pytest -m f1` (replace `f1` with phase) |
| Check code quality | `ruff check src/ tests/ && mypy src/` |
| Add a database migration | `alembic revision --autogenerate -m "description"` |
| Find a QA review | Look in `Plan/REVIEWS/` |
| Understand an architecture decision | Check `Plan/ARCH_INVARIANTS.md` |
| See known issues | Check `Plan/FINDINGS.md` |
