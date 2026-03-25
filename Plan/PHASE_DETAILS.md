# Phase Details — Noa Implementation

> Status overview: see `PLAN.md` in this directory.
> Search for a phase ID (e.g., "### Phase F1") to find specific details.

---

## Wave 1: Project Foundation

Establishes the project skeleton, database, API framework, and authentication. After this wave, the system can accept authenticated requests and persist data.

---

### Phase F1: Project Scaffold & Docker Compose (~30 min)

**Goal:** No project structure exists yet. This phase creates the monorepo layout, Docker Compose configuration for all Phase 1 services, and the development tooling needed for all subsequent phases.

**Spec refs:** SPEC.md §4.1, §7.1, §8.1, §8.2, §20.1

**Depends on:** None
**Blocks:** F2, F3, F4, and all subsequent phases

**Deliverables:**
1. Monorepo directory structure (`src/`, `tests/`, `docker/`, `web/`)
2. Docker Compose file with all Phase 1 services (noa-api, postgres, private-worker, external-worker)
3. Docker network definitions (`noa-internal`, `noa-external`) with correct isolation
4. Python project configuration (pyproject.toml, dependencies)
5. Development environment setup (Makefile/scripts for common tasks)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | **CREATE** | Python project config with FastAPI, LangGraph, SQLAlchemy, Alembic, pytest deps |
| `docker-compose.yml` | **CREATE** | All Phase 1 services with network isolation per §20.1 |
| `docker/noa-api/Dockerfile` | **CREATE** | Noa API container image |
| `docker/private-worker/Dockerfile` | **CREATE** | Private worker container with Ollama, hardened per §8.1 |
| `docker/external-worker/Dockerfile` | **CREATE** | External worker container, hardened per §8.2 |
| `src/__init__.py` | **CREATE** | Root package |
| `src/noa/__init__.py` | **CREATE** | Noa package |
| `src/noa/config.py` | **CREATE** | App configuration (env vars, defaults) |
| `tests/conftest.py` | **CREATE** | Shared pytest fixtures |
| `Makefile` | **CREATE** | Dev commands (up, down, test, migrate, lint) |
| `.env.example` | **CREATE** | Environment variable template |

**Tests (~5):**
- Config loading: env vars parsed correctly, defaults applied
- Docker Compose validation: compose file is valid, networks defined correctly
- Package structure: imports resolve correctly

**Test gate:**
```bash
pytest tests/unit/test_config.py -v
```

---

### Phase F2: Postgres Schema & Alembic Migrations (~45 min)

**Goal:** No database schema exists. This phase creates the complete Postgres schema with all control-plane tables and Alembic migration infrastructure, enabling persistent storage for all subsequent features.

**Spec refs:** SPEC.md §10.1, §10.4, §22.1, §22.2, §22.5

**Depends on:** F1
**Blocks:** F3, F4, OC1, OC2, OC3

**Deliverables:**
1. SQLAlchemy ORM models for all control-plane tables
2. Alembic migration infrastructure with initial migration
3. Database connection management with async support
4. Schema covering: users, sessions, conversations, messages, runs, run_events, approvals, artifacts, audit_log, task_queue, usage_stats

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/db/__init__.py` | **CREATE** | Database package |
| `src/noa/db/engine.py` | **CREATE** | Async engine setup, session factory, connection pooling |
| `src/noa/db/models/__init__.py` | **CREATE** | Models package with Base |
| `src/noa/db/models/user.py` | **CREATE** | User model |
| `src/noa/db/models/session.py` | **CREATE** | Session model (auth sessions) |
| `src/noa/db/models/conversation.py` | **CREATE** | Conversation + Message models |
| `src/noa/db/models/run.py` | **CREATE** | Run + RunEvent models per §22.1-22.2 |
| `src/noa/db/models/approval.py` | **CREATE** | Approval model |
| `src/noa/db/models/artifact.py` | **CREATE** | Artifact model per §22.3 |
| `src/noa/db/models/audit.py` | **CREATE** | AuditLog model with hash chain field |
| `src/noa/db/models/task_queue.py` | **CREATE** | TaskQueue model per §17.2 |
| `src/noa/db/models/usage.py` | **CREATE** | UsageStats model |
| `alembic.ini` | **CREATE** | Alembic configuration |
| `alembic/env.py` | **CREATE** | Alembic environment setup |
| `alembic/versions/001_initial.py` | **CREATE** | Initial migration with all tables |
| `tests/unit/test_models.py` | **CREATE** | Model tests |

**Tests (~15):**
- Model creation: each model can be instantiated with valid data
- Schema validation: required fields enforced, types correct
- Relationships: foreign keys and relationships work correctly
- Run/Event model: events are append-only, status transitions valid
- Audit log: hash chain field present and computed correctly
- Migration: Alembic upgrade/downgrade cycle works

**Test gate:**
```bash
pytest tests/unit/test_models.py -v
```

---

### Phase F3: FastAPI Skeleton & Health Endpoints (~30 min)

**Goal:** No API server exists. This phase creates the FastAPI application with health endpoints, standard response envelope, error handling, and OpenAPI auto-generation.

**Spec refs:** SPEC.md §25.1, §25.2, §25.3, §28.5

**Depends on:** F1, F2
**Blocks:** F4, OC1, OC2

**Deliverables:**
1. FastAPI application factory with lifespan management
2. Standard response envelope middleware per §25.3
3. Health endpoints (liveness, readiness, metrics) per §28.5
4. OpenAPI 3.1 auto-generation with API versioning (`/api/v1/`)
5. CORS, request ID, and error handling middleware

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/api/__init__.py` | **CREATE** | API package |
| `src/noa/api/app.py` | **CREATE** | FastAPI app factory with lifespan |
| `src/noa/api/middleware.py` | **CREATE** | Response envelope, request ID, error handling |
| `src/noa/api/deps.py` | **CREATE** | Dependency injection (db session, current user) |
| `src/noa/api/v1/__init__.py` | **CREATE** | v1 API router |
| `src/noa/api/v1/health.py` | **CREATE** | Health endpoints per §28.5 |
| `src/noa/api/schemas/common.py` | **CREATE** | Standard envelope, error schemas per §25.3 |
| `tests/unit/test_api_health.py` | **CREATE** | Health endpoint tests |

**Tests (~12):**
- Health endpoints: `/health` returns 200, `/health/ready` checks deps
- Response envelope: all responses wrapped in standard format
- Error handling: validation errors return proper envelope
- Request ID: every response includes trace_id
- OpenAPI: spec is auto-generated and accessible
- API versioning: `/api/v1/` prefix works correctly

**Test gate:**
```bash
pytest tests/unit/test_api_health.py -v
```

---

### Phase F4: Authentication & Session Management (~45 min)

**Goal:** No authentication exists. This phase implements JWT-based auth with login, refresh, session management, and device binding per the security requirements.

**Spec refs:** SPEC.md §5.1, §5.2, §5.3, §5.4

**Depends on:** F2, F3
**Blocks:** OC2, OC4

**Deliverables:**
1. Login endpoint (username + password) returning JWT access + refresh tokens
2. Token refresh with rotating refresh tokens
3. Session management (creation, expiry, revocation)
4. Auth middleware for protected endpoints
5. Rate limiting on failed auth attempts (5 in 10 min → lockout)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/auth/__init__.py` | **CREATE** | Auth package |
| `src/noa/auth/jwt.py` | **CREATE** | JWT creation, verification, refresh logic |
| `src/noa/auth/service.py` | **CREATE** | Auth service (login, refresh, revoke) |
| `src/noa/auth/middleware.py` | **CREATE** | Auth middleware for protected routes |
| `src/noa/auth/password.py` | **CREATE** | Password hashing (argon2/bcrypt) |
| `src/noa/api/v1/auth.py` | **CREATE** | Auth endpoints (login, refresh, logout) |
| `tests/unit/test_auth.py` | **CREATE** | Auth tests |

**Tests (~18):**
- Login: valid credentials return tokens, invalid rejected
- JWT: tokens encode/decode correctly, expired tokens rejected
- Refresh: rotating refresh tokens work, old token invalidated
- Session: sessions created on login, expired after timeout (default 30 min)
- Device binding: sessions bound to device ID
- Revocation: logout invalidates all session tokens
- Rate limiting: 5 failed attempts → 30 min lockout
- Protected endpoints: unauthenticated requests return 401

**Test gate:**
```bash
pytest tests/unit/test_auth.py -v
```

---

## Wave 2: Orchestration Core

Builds the LangGraph orchestrator, Run/Event model with SSE streaming, audit logging, and the policy engine. After this wave, the system can orchestrate tasks through a governed pipeline.

---

### Phase OC1: LangGraph Orchestrator Skeleton (~45 min)

**Goal:** No orchestration exists. This phase creates the LangGraph state machine with the core node sequence (router → agent → tools → responder) and deterministic execution guarantees per the governed execution model.

**Spec refs:** SPEC.md §2.1, §2.2, §6.1, §7.1

**Depends on:** F2, F3
**Blocks:** OC2, OC4, DW1, DW2, DW4

**Deliverables:**
1. LangGraph state machine with fixed node topology per §2.1
2. Router node (privacy classification + model selection)
3. Agent node (LLM invocation with bounded autonomy)
4. Tool node (tool dispatch with allowlist enforcement)
5. Responder node (formatting, cost tracking)
6. Graph state schema and checkpointer (AsyncPostgresSaver)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/orchestrator/__init__.py` | **CREATE** | Orchestrator package |
| `src/noa/orchestrator/graph.py` | **CREATE** | LangGraph graph definition with node sequence |
| `src/noa/orchestrator/state.py` | **CREATE** | Graph state schema (AgentState) |
| `src/noa/orchestrator/nodes/__init__.py` | **CREATE** | Nodes package |
| `src/noa/orchestrator/nodes/router.py` | **CREATE** | Router node: classify privacy + select model |
| `src/noa/orchestrator/nodes/agent.py` | **CREATE** | Agent node: invoke LLM with bounded tools |
| `src/noa/orchestrator/nodes/tools.py` | **CREATE** | Tool node: dispatch tool calls with allowlist |
| `src/noa/orchestrator/nodes/responder.py` | **CREATE** | Responder node: format + cost tracking |
| `src/noa/orchestrator/checkpointer.py` | **CREATE** | AsyncPostgresSaver setup per §13.1 |
| `tests/unit/test_orchestrator.py` | **CREATE** | Orchestrator tests |

**Tests (~15):**
- Graph topology: nodes execute in fixed order (router → agent → tools → responder)
- Tool allowlist: agent cannot invoke tools not in its allowlist
- State management: state persists across steps via checkpointer
- Deterministic execution: same input → same path
- Node isolation: nodes cannot skip or reorder
- Bounded autonomy: LLM decisions stay within step constraints

**Test gate:**
```bash
pytest tests/unit/test_orchestrator.py -v
```

---

### Phase OC2: Run/Event Model & SSE Streaming (~45 min)

**Goal:** No run tracking or real-time streaming exists. This phase implements the Run/Event model with SSE streaming so all clients can consume the same real-time event timeline.

**Spec refs:** SPEC.md §22.1, §22.2, §22.3, §22.4, §22.5

**Depends on:** F2, F3, F4, OC1
**Blocks:** WC1, WC2

**Deliverables:**
1. Run CRUD service (create, update status, query)
2. Event append service (append-only, ordered events)
3. SSE endpoint (`/api/v1/runs/{run_id}/events`)
4. Artifact metadata service
5. Run lifecycle management (pending → running → completed/failed)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/runs/__init__.py` | **CREATE** | Runs package |
| `src/noa/runs/service.py` | **CREATE** | Run + Event CRUD service |
| `src/noa/runs/schemas.py` | **CREATE** | Run/Event Pydantic schemas per §22.1-22.2 |
| `src/noa/api/v1/runs.py` | **CREATE** | Run endpoints + SSE streaming per §22.4 |
| `src/noa/runs/artifacts.py` | **CREATE** | Artifact metadata service per §22.3 |
| `tests/unit/test_runs.py` | **CREATE** | Run/Event tests |

**Tests (~20):**
- Run creation: runs created with correct initial state
- Status transitions: valid transitions work, invalid rejected
- Event appending: events are ordered and append-only
- SSE streaming: events stream correctly via SSE endpoint
- Event types: all event types from §22.2 table are supported
- Artifact metadata: artifacts linked to runs correctly
- Run query: runs queryable by thread, user, status
- Auth: SSE endpoint requires authentication

**Test gate:**
```bash
pytest tests/unit/test_runs.py -v
```

---

### Phase OC3: Audit Logging with Hash Chain (~30 min)

**Goal:** No audit trail exists. This phase implements the immutable, append-only audit log with hash chain integrity verification for all tool invocations.

**Spec refs:** SPEC.md §28.1, §28.2, §28.3, §28.7

**Depends on:** F2
**Blocks:** OC4, TI1-TI6

**Deliverables:**
1. Audit log service with hash chain computation (SHA256)
2. Structured JSON logging across all services per §28.3
3. Audit log query API with trace_id correlation
4. Hash chain integrity verification endpoint
5. Data retention policy enforcement (90-day default)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/audit/__init__.py` | **CREATE** | Audit package |
| `src/noa/audit/service.py` | **CREATE** | Audit log service with hash chain |
| `src/noa/audit/schemas.py` | **CREATE** | Audit log entry schemas per §28.1 |
| `src/noa/audit/logging.py` | **CREATE** | Structured JSON logger setup per §28.3 |
| `src/noa/audit/integrity.py` | **CREATE** | Hash chain verification |
| `src/noa/api/v1/audit.py` | **CREATE** | Audit query endpoint |
| `tests/unit/test_audit.py` | **CREATE** | Audit log tests |

**Tests (~12):**
- Log creation: entries include all required fields per §28.1
- Hash chain: each entry's hash includes previous entry's hash
- Integrity check: valid chain passes, tampered chain detected
- Structured logging: JSON format with trace_id propagation
- Retention: entries older than retention period are purged
- No secrets: log entries never contain PII or secrets

**Test gate:**
```bash
pytest tests/unit/test_audit.py -v
```

---

### Phase OC4: Policy Engine & Approval Framework (~45 min)

**Goal:** No policy enforcement or approval mechanism exists. This phase creates the risk-tier system, approval gates, and dry-run preview generation for Medium/High risk actions.

**Spec refs:** SPEC.md §21, §19.2, §23.2, §29.6

**Depends on:** F4, OC1, OC3
**Blocks:** TI6, AB3

**Deliverables:**
1. Risk tier classification engine (Low/Medium/High) per §21
2. Approval gate integrated into orchestrator pipeline
3. Dry-run preview generation for Medium/High actions per §19.2
4. Approval endpoints (request, approve/deny) per §29.6
5. Approval batching within 30-second window per §23.2

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/policy/__init__.py` | **CREATE** | Policy package |
| `src/noa/policy/engine.py` | **CREATE** | Risk tier classification + policy rules per §21 |
| `src/noa/policy/approval.py` | **CREATE** | Approval service (request, approve, deny, batch) |
| `src/noa/policy/preview.py` | **CREATE** | Dry-run preview generator per §19.2 |
| `src/noa/policy/schemas.py` | **CREATE** | Policy/approval Pydantic schemas |
| `src/noa/api/v1/approvals.py` | **CREATE** | Approval endpoints per §29.6 |
| `tests/unit/test_policy.py` | **CREATE** | Policy engine tests |

**Tests (~18):**
- Risk classification: Low/Medium/High actions classified correctly per §21 tables
- Approval gates: Medium actions require approval, Low do not
- High-risk: requires step-up auth
- Preview generation: previews render for create/send actions
- Approval flow: request → approve → task resumes
- Denial flow: request → deny → task cancelled
- Batching: multiple approvals within 30s grouped into one request
- No cross-domain batching: private and external never batched together
- Timeout: unanswered approvals expire after 5 minutes

**Test gate:**
```bash
pytest tests/unit/test_policy.py -v
```

---

## Wave 3: Domain Workers & Isolation

Creates the private and external domain workers with strict network isolation and privacy routing. After this wave, the dual-domain architecture is functional.

---

### Phase DW1: Private Worker with Ollama & RPC Contract (~45 min)

**Goal:** No private domain processing exists. This phase creates the private worker service with Ollama integration and the full RPC contract (request/response schemas, size limits, DLP redaction).

**Spec refs:** SPEC.md §8.1, §9.1, §9.2, §9.3, §9.4, §13.1, §13.2

**Depends on:** F1, OC1
**Blocks:** DW3, DW4, TI1

**Deliverables:**
1. Private worker FastAPI service (runs inside private container)
2. Ollama client for local LLM inference
3. RPC request/response validation with hard limits per §9.1-9.2
4. DLP/redaction pipeline per §9.3
5. Contract violation detection and alerting per §9.4

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/private_worker/__init__.py` | **CREATE** | Private worker package |
| `src/noa/private_worker/app.py` | **CREATE** | Private worker FastAPI app |
| `src/noa/private_worker/ollama_client.py` | **CREATE** | Ollama API client |
| `src/noa/private_worker/rpc.py` | **CREATE** | RPC contract validation per §9.1-9.2 |
| `src/noa/private_worker/dlp.py` | **CREATE** | DLP scanner + redaction per §9.3 |
| `src/noa/private_worker/handlers.py` | **CREATE** | Task handlers (remember, recall, rag_query, etc.) |
| `src/noa/private_worker/schemas.py` | **CREATE** | Request/response schemas per §9.1-9.2 |
| `tests/unit/test_private_worker.py` | **CREATE** | Private worker tests |

**Tests (~20):**
- RPC request validation: oversized queries rejected, all fields validated
- RPC response validation: oversized responses rejected per §9.2
- DLP redaction: PII patterns (email, phone, SSN, CC) redacted with [REDACTED]
- Sensitivity labeling: responses tagged with sensitivity_label
- No passthrough: raw query never echoed back
- Contract violations: 3 violations in 24h triggers alert
- Task types: remember, recall, rag_query, summarize, search handled
- Ollama integration: inference calls formatted correctly
- Hard limits: all size limits from §9.1-9.2 enforced

**Test gate:**
```bash
pytest tests/unit/test_private_worker.py -v
```

---

### Phase DW2: External Worker Skeleton (~30 min)

**Goal:** No external domain execution exists. This phase creates the external worker service that handles remote LLM API calls and tool integrations.

**Spec refs:** SPEC.md §8.2, §6.2 (Domain B), §14.1

**Depends on:** F1, OC1
**Blocks:** DW3, TI2-TI5, AB5

**Deliverables:**
1. External worker service skeleton
2. LLM provider clients (Anthropic, OpenAI)
3. Provider routing based on configuration and user selection per §14.1
4. Tool dispatch framework (tool registry + invocation)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/external_worker/__init__.py` | **CREATE** | External worker package |
| `src/noa/external_worker/app.py` | **CREATE** | External worker FastAPI app |
| `src/noa/external_worker/llm/__init__.py` | **CREATE** | LLM clients package |
| `src/noa/external_worker/llm/anthropic.py` | **CREATE** | Anthropic Claude client |
| `src/noa/external_worker/llm/openai.py` | **CREATE** | OpenAI client |
| `src/noa/external_worker/llm/router.py` | **CREATE** | Provider selection logic per §14.1 |
| `src/noa/external_worker/tools/__init__.py` | **CREATE** | Tool registry + dispatch framework |
| `tests/unit/test_external_worker.py` | **CREATE** | External worker tests |

**Tests (~12):**
- Provider routing: correct provider selected based on config/user choice
- Provider isolation: private mode never routes to external providers
- LLM client: requests formatted correctly for each provider
- Tool registry: tools registered and discoverable
- Tool dispatch: tool calls routed to correct handler
- Error handling: provider failures handled gracefully

**Test gate:**
```bash
pytest tests/unit/test_external_worker.py -v
```

---

### Phase DW3: Docker Network Isolation & Verification (~30 min)

**Goal:** No network isolation enforcement or verification exists. This phase configures and tests the Docker network isolation between private and external domains, including continuous verification tests.

**Spec refs:** SPEC.md §20.1, §20.3, §20.4, §7.3

**Depends on:** DW1, DW2
**Blocks:** None (validation phase)

**Deliverables:**
1. Docker Compose network configuration validated and hardened
2. Egress allowlist for external container per §20.3
3. Continuous verification test suite per §20.4
4. Network isolation integration tests

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | **EDIT** | Harden network config, add egress rules |
| `scripts/verify_isolation.sh` | **CREATE** | Network isolation verification script per §20.4 |
| `tests/integration/test_network_isolation.py` | **CREATE** | Network isolation integration tests |

**Tests (~10):**
- Private container egress: curl to external URL must fail
- Private container DNS: DNS resolution of external domains must fail
- Cross-domain route: private cannot reach external container directly
- External egress: only allowlisted domains reachable
- Noa API bridges: API can reach both networks
- IPv6 blocked: no IPv6 egress from private container

**Test gate:**
```bash
pytest tests/integration/test_network_isolation.py -v
```

---

### Phase DW4: Privacy Router & Classification (~45 min)

**Goal:** No privacy classification exists. This phase implements the content-based privacy router that classifies tasks as private or external, with fail-safe handling for ambiguous classifications.

**Spec refs:** SPEC.md §14.2, §14.3, §18

**Depends on:** OC1, DW1, DW2
**Blocks:** None

**Deliverables:**
1. Privacy classifier (keyword + LLM-based analysis) per §18
2. Fail-safe routing for low-confidence classifications per §14.3
3. User override support (per-message privacy toggle)
4. Classification logging with confidence scores
5. Router evaluation metrics framework per §14.3

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/orchestrator/nodes/router.py` | **EDIT** | Add privacy classification logic per §14.2-14.3, §18 |
| `src/noa/privacy/__init__.py` | **CREATE** | Privacy package |
| `src/noa/privacy/classifier.py` | **CREATE** | Content-based privacy classifier |
| `src/noa/privacy/metrics.py` | **CREATE** | Classification metrics tracking per §14.3 |
| `tests/unit/test_privacy_router.py` | **CREATE** | Privacy routing tests |

**Tests (~18):**
- Explicit override: user toggle always respected
- Tool-based routing: Calendar/Gmail/Notion/Search → external, Memory → private
- Content analysis: mentions of personal data → private
- Low confidence fail-safe: confidence < 0.7 → force private (if available)
- Low confidence with unavailable private: user prompted
- Default mode: external (configurable)
- Logging: every classification logged with confidence + reasoning
- Never fallback: private tasks never silently route to external

**Test gate:**
```bash
pytest tests/unit/test_privacy_router.py -v
```

---

## Wave 4: Tool Integrations

Implements all 5 MVP tools (Memory, Calendar, Gmail, Notion, Web Search) plus tool governance. After this wave, Noa can interact with external services.

---

### Phase TI1: Memory Tool (Remember/Recall) (~30 min)

**Goal:** No long-term memory exists. This phase implements the Memory tool that stores facts with embeddings in the private domain and retrieves them via semantic search.

**Spec refs:** SPEC.md §12.5, §13.2, §13.3

**Depends on:** DW1
**Blocks:** AB4

**Deliverables:**
1. `remember(fact)` — stores fact with embedding via private worker RPC
2. `recall(query, n_results?)` — semantic search over stored facts
3. Fact storage with categories, status (approved/pending), and metadata per §13.2
4. Auto-extraction guardrails (off by default) per §13.2

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/memory.py` | **CREATE** | Memory tool (remember/recall) via RPC |
| `src/noa/private_worker/memory_store.py` | **CREATE** | Private-side fact storage + embedding |
| `src/noa/private_worker/handlers.py` | **EDIT** | Add memory task handlers |
| `tests/unit/test_memory_tool.py` | **CREATE** | Memory tool tests |

**Tests (~15):**
- Remember: fact stored with embedding, category, timestamp
- Recall: semantic search returns relevant facts
- Deduplication: exact duplicate facts rejected per §19.1
- Auto-extraction: off by default, pending state when enabled
- Schema: fact schema matches §13.2
- RPC: memory operations go through private worker RPC
- Limits: n_results capped at 20

**Test gate:**
```bash
pytest tests/unit/test_memory_tool.py -v
```

---

### Phase TI2: Google Calendar Tool (~30 min)

**Goal:** No calendar integration exists. This phase implements the Google Calendar tool with OAuth2 auth and all functions (list, create, update events).

**Spec refs:** SPEC.md §12.1

**Depends on:** DW2
**Blocks:** TI6

**Deliverables:**
1. `list_events(start_date, end_date)` — list events with title, time, attendees
2. `create_event(title, start, end, description?, attendees?)` — create event (Medium risk)
3. `update_event(event_id, changes)` — update event (Medium risk)
4. Google OAuth2 integration (calendar.readonly, calendar.events scopes)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/calendar.py` | **CREATE** | Google Calendar tool implementation |
| `src/noa/tools/google_auth.py` | **CREATE** | Shared Google OAuth2 client |
| `tests/unit/test_calendar_tool.py` | **CREATE** | Calendar tool tests |

**Tests (~15):**
- List events: returns events within date range
- Create event: creates event, returns event ID
- Update event: modifies event fields
- Risk tiers: list=Low, create/update=Medium
- Validation: no past events, no unreasonable durations per §16.3
- OAuth2: auth flow, token refresh
- Error handling: API failures handled gracefully

**Test gate:**
```bash
pytest tests/unit/test_calendar_tool.py -v
```

---

### Phase TI3: Gmail Tool (~30 min)

**Goal:** No email integration exists. This phase implements the Gmail tool with search, read, send, and draft functions.

**Spec refs:** SPEC.md §12.2

**Depends on:** DW2, TI2 (shared Google auth)
**Blocks:** TI6

**Deliverables:**
1. `search_emails(query, max_results?)` — search email summaries (Low risk)
2. `read_email(email_id)` — full email content (Low risk)
3. `send_email(to, subject, body)` — send email (Medium risk, preview required)
4. `draft_email(to, subject, body)` — create draft (Low risk)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/gmail.py` | **CREATE** | Gmail tool implementation |
| `src/noa/tools/google_auth.py` | **EDIT** | Add Gmail scopes (gmail.readonly, gmail.send, gmail.compose) |
| `tests/unit/test_gmail_tool.py` | **CREATE** | Gmail tool tests |

**Tests (~18):**
- Search: returns matching email summaries
- Read: returns full email content
- Send: sends email, returns confirmation (Medium risk)
- Draft: creates draft, returns draft ID (Low risk)
- Risk tiers: send=Medium, search/read/draft=Low
- Send confirmation logged before reporting success per §16.3
- Error handling: API failures handled gracefully

**Test gate:**
```bash
pytest tests/unit/test_gmail_tool.py -v
```

---

### Phase TI4: Notion Tool (~30 min)

**Goal:** No Notion integration exists. This phase implements the Notion tool with search, read, create, and update page functions.

**Spec refs:** SPEC.md §12.3

**Depends on:** DW2
**Blocks:** TI6

**Deliverables:**
1. `search_pages(query)` — search pages with titles and IDs (Low risk)
2. `read_page(page_id)` — page content as markdown (Low risk)
3. `create_page(parent_id, title, content)` — create page (Medium risk)
4. `update_page(page_id, content)` — update page (Medium risk)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/notion.py` | **CREATE** | Notion tool implementation |
| `tests/unit/test_notion_tool.py` | **CREATE** | Notion tool tests |

**Tests (~15):**
- Search: returns matching pages
- Read: returns page content as markdown
- Create: creates page under parent, returns page ID
- Update: updates page content
- Risk tiers: search/read=Low, create/update=Medium
- Content sanitized before display per §16.3
- Error handling: API failures handled gracefully

**Test gate:**
```bash
pytest tests/unit/test_notion_tool.py -v
```

---

### Phase TI5: Web Search Tool — Provider-Agnostic (~20 min)

**Goal:** No web search capability exists. This phase implements the Web Search tool with a provider-agnostic `SearchProvider` interface and Tavily as the first implementation. Additional providers (Serper, Exa, etc.) can be added later as drop-in implementations.

**Spec refs:** SPEC.md §12.4

**Depends on:** DW2
**Blocks:** TI6

**Deliverables:**
1. `web_search(query, max_results?)` — search results with title, URL, content snippet (Low risk)
2. `SearchProvider` abstract interface (provider-agnostic)
3. `TavilySearchProvider` — first concrete implementation
4. Provider selection via configuration

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/web_search.py` | **CREATE** | Web Search tool with SearchProvider interface |
| `src/noa/tools/search_providers/__init__.py` | **CREATE** | Search providers package |
| `src/noa/tools/search_providers/base.py` | **CREATE** | SearchProvider ABC |
| `src/noa/tools/search_providers/tavily.py` | **CREATE** | Tavily implementation |
| `tests/unit/test_web_search_tool.py` | **CREATE** | Web search tool tests |

**Tests (~10):**
- Search: returns results with title, URL, snippet
- Max results: respects max_results parameter
- Risk tier: always Low
- Provider interface: ABC enforces required methods
- Provider selection: correct provider instantiated from config
- Error handling: API failures handled gracefully

**Test gate:**
```bash
pytest tests/unit/test_web_search_tool.py -v
```

---

### Phase TI6: Tool Interface, Registry & Governance (MCP-ready) (~60 min)

**Goal:** All 5 MVP tools exist as standalone classes with no unified interface. The orchestrator's `tool_node` uses a hardcoded `execute_tool` placeholder. This phase introduces a `ToolInterface` Protocol that all tools implement, a `ToolRegistry` that the orchestrator dispatches through, an `MCPToolAdapter` stub for future MCP server integration, and governance layers (idempotency, rate limiting, dry-run previews) that wrap the unified interface.

**Spec refs:** SPEC.md §2.1 (static allowlists), §12 (tool definitions), §16 (output validation), §19.1 (idempotency), §19.2 (previews), §19.3 (rate limits), §25.4 (Idempotency-Key header)

**Depends on:** OC4, TI1-TI5
**Blocks:** None

**Deliverables:**

*Tool Interface & Registry:*
1. `ToolInterface` Protocol — unified contract: `name`, `domain`, `risk_tiers`, `async execute(function, args) → dict`
2. `ToolRegistry` — static `dict[str, ToolInterface]`, wired into orchestrator `tool_node`
3. Refactor all 5 MVP tools (MemoryTool, CalendarTool, GmailTool, NotionTool, WebSearchTool) to implement `ToolInterface`
4. `MCPToolAdapter` stub — implements `ToolInterface`, wraps future MCP `call_tool()`. Risk tiers come from static config, NOT from MCP server discovery. Transport layer (stdio/SSE) deferred.
5. Wire `tool_node` to dispatch through `ToolRegistry` instead of `execute_tool` placeholder

*Governance:*
6. Idempotency key enforcement on all write tools per §19.1
7. Per-tool rate limiting per §19.3
8. Dry-run preview generation for all Medium-risk actions per §19.2
9. Idempotency-Key header support on all write API endpoints per §25.4

**Architecture:**

```
tool_node (orchestrator)
    → ToolRegistry.dispatch(name, function, args)
        → GovernanceWrapper (idempotency + rate limit + preview)
            → ToolInterface.execute(function, args)
                → NativeTool (CalendarTool, GmailTool, ...)
                   OR
                → MCPToolAdapter → MCP Server (future)
```

**Key constraint:** The `ToolRegistry` is a static dict populated at startup from config. Tools cannot register themselves at runtime. This preserves §2.1 (static allowlists). MCP servers are declared in config with explicit risk-tier mappings — they do NOT self-declare capabilities.

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/interface.py` | **CREATE** | `ToolInterface` Protocol + `ToolRegistry` |
| `src/noa/tools/mcp_adapter.py` | **CREATE** | `MCPToolAdapter` stub (implements ToolInterface, defers transport) |
| `src/noa/tools/governance.py` | **CREATE** | `GovernanceWrapper` — idempotency, rate limiting, preview middleware |
| `src/noa/tools/idempotency.py` | **CREATE** | Idempotency key store + dedup logic |
| `src/noa/tools/rate_limiter.py` | **CREATE** | Per-tool rate limiting per §19.3 |
| `src/noa/tools/memory.py` | **EDIT** | Implement `ToolInterface` (add `execute()` dispatcher) |
| `src/noa/tools/calendar.py` | **EDIT** | Implement `ToolInterface` |
| `src/noa/tools/gmail.py` | **EDIT** | Implement `ToolInterface` |
| `src/noa/tools/notion.py` | **EDIT** | Implement `ToolInterface` |
| `src/noa/tools/web_search.py` | **EDIT** | Implement `ToolInterface` |
| `src/noa/orchestrator/nodes/tools.py` | **EDIT** | Replace `execute_tool` with `ToolRegistry.dispatch()` |
| `src/noa/api/middleware.py` | **EDIT** | Add Idempotency-Key header support |
| `tests/unit/test_tool_interface.py` | **CREATE** | ToolInterface, Registry, MCPToolAdapter tests |
| `tests/unit/test_tool_governance.py` | **CREATE** | Governance tests (idempotency, rate limits, previews) |

**Tests (~25):**

*Interface & Registry:*
- ToolInterface: all 5 MVP tools satisfy the Protocol
- ToolRegistry: dispatch routes to correct tool
- ToolRegistry: unknown tool raises error
- ToolRegistry: allowlist matches registry keys
- MCPToolAdapter: implements ToolInterface
- MCPToolAdapter: execute() raises NotImplementedError (transport not wired)
- MCPToolAdapter: risk_tiers come from static config, not server

*Governance:*
- Idempotency: duplicate send_email with same key → no re-send per §19.1
- Idempotency: duplicate create_event with same key → returns previous result
- Rate limits: send_email blocked after 10/hour per §19.3
- Rate limits: create_event blocked after 20/hour
- Rate limits: web_search blocked after 30/hour
- Preview generation: all create/send actions generate preview before execution
- Preview format: includes diff-like summary of changes
- API header: Idempotency-Key deduplicates within 24 hours

*Integration:*
- tool_node dispatches through ToolRegistry (not execute_tool)
- GovernanceWrapper wraps ToolInterface transparently

**Test gate:**
```bash
pytest tests/unit/test_tool_interface.py tests/unit/test_tool_governance.py -v
```

---

## Wave 5: Advanced Backend

Adds cost control, output validation, task scheduling, durable queuing, and the coding task contract. After this wave, the backend is feature-complete.

---

### Phase AB1: Cost Control & Token Tracking (~20 min)

**Goal:** No cost control exists. This phase implements token tracking, cost estimation, and hard budget limits (monthly, daily, per-task).

**Spec refs:** SPEC.md §24

**Depends on:** OC1, OC3
**Blocks:** None

**Integration contracts (R4):**
- `CostTracker.record(provider, model, input_tokens, output_tokens, cost_usd)` — called by workers after each LLM call
- `CostLimiter.check(scope: "monthly"|"daily"|"task", task_id?)` → `bool` — called by orchestrator before dispatching
- `UsageAPI` endpoints return per-message, session, daily, monthly breakdowns

**Deliverables:**
1. Token tracking per LLM call (provider, model, input/output tokens, cost)
2. Monthly and daily token caps with hard limits per §24
3. Per-task token limit enforcement
4. Model routing for cost (cheapest sufficient model) per §24
5. Cost display data for clients (per-message, session, daily, monthly)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/cost/__init__.py` | **CREATE** | Cost control package |
| `src/noa/cost/tracker.py` | **CREATE** | Token + cost tracking service |
| `src/noa/cost/limits.py` | **CREATE** | Budget limit enforcement (monthly, daily, per-task) |
| `src/noa/cost/pricing.py` | **CREATE** | Provider pricing tables for cost estimation |
| `src/noa/api/v1/usage.py` | **CREATE** | Usage/cost endpoints |
| `tests/unit/test_cost.py` | **CREATE** | Cost control tests |

**Tests (~15):**
- Token tracking: every LLM call logged with provider, model, tokens, cost
- Monthly cap: requests refused when monthly cap exceeded
- Daily cap: warning at 80%, hard limit at 100%
- Per-task limit: task aborted when per-task limit exceeded
- Cost estimation: USD cost calculated from provider pricing
- Display data: per-message, session, daily, monthly breakdowns returned

**Test gate:**
```bash
pytest tests/unit/test_cost.py -v
```

---

### Phase AB2: Output Validation Pipeline (~20 min)

**Goal:** No output validation exists. This phase implements the validation pipeline that checks all worker outputs before Noa acts on them (schema validation, size limits, content filtering, prompt injection detection).

**Spec refs:** SPEC.md §16.1, §16.2, §16.3, §16.4

**Depends on:** OC1, DW1, DW2
**Blocks:** None

**Integration contracts (R4):**
- `ValidationPipeline.validate(output: dict, context: ValidationContext)` → `ValidationResult` — called by orchestrator after every worker response
- `ValidationResult` has `passed: bool`, `failures: list[ValidationFailure]`, `filtered_output: dict`
- Pipeline stages: schema → size → content_filter → coding_check → tool_check → policy

**Deliverables:**
1. Schema validation for all worker responses per §16.1
2. Size limit enforcement per RPC and coding contracts
3. Content filtering (prompt injection markers, exfiltration URLs) per §16.4
4. Coding output checks (diff scoping, no unauthorized deps) per §16.2
5. Tool output checks (JSON schema, calendar/email validation) per §16.3

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/validation/__init__.py` | **CREATE** | Validation package |
| `src/noa/validation/pipeline.py` | **CREATE** | Validation pipeline (schema → size → content → policy) |
| `src/noa/validation/content_filter.py` | **CREATE** | Prompt injection detection, exfiltration URL scanning |
| `src/noa/validation/coding.py` | **CREATE** | Coding output validation per §16.2 |
| `src/noa/validation/tool_output.py` | **CREATE** | Tool output validation per §16.3 |
| `tests/unit/test_validation.py` | **CREATE** | Validation pipeline tests |

**Tests (~15):**
- Schema validation: malformed responses rejected
- Size limits: oversized responses rejected
- Prompt injection: responses with "ignore previous instructions" flagged
- Coding: diffs touching files outside workspace rejected
- Coding: unauthorized dependency additions detected
- Tool output: invalid JSON rejected
- Calendar: past events and unreasonable durations rejected
- Email: send confirmations logged before success

**Test gate:**
```bash
pytest tests/unit/test_validation.py -v
```

---

### Phase AB3: Task Scheduling & Prioritization (~20 min)

**Goal:** No task scheduling exists. This phase implements deterministic task ordering with priority tiers, FIFO within tiers, and dependency resolution.

**Spec refs:** SPEC.md §23.1, §23.3, §23.4

**Depends on:** OC4
**Blocks:** AB4

**Integration contracts (R4):**
- `TaskScheduler.enqueue(task, priority, dependencies?)` → `queue_position`
- `TaskScheduler.next()` → highest-priority unblocked task (FIFO within tier)
- `TaskScheduler.cancel(task_id)`, `TaskScheduler.retry(task_id)`
- Priority enum: `critical > high > normal > background`
- Max dependency chain depth: 5; circular deps rejected

**Deliverables:**
1. Priority-based task queue (critical > high > normal > background) per §23.1
2. FIFO ordering within same priority tier
3. Dependency resolution (explicit, sequential, independent) per §23.3
4. Circular dependency detection
5. Max dependency chain depth enforcement (5)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/scheduler/__init__.py` | **CREATE** | Scheduler package |
| `src/noa/scheduler/queue.py` | **CREATE** | Priority queue with deterministic ordering per §23.1 |
| `src/noa/scheduler/dependencies.py` | **CREATE** | Dependency resolution + validation per §23.3 |
| `src/noa/api/v1/tasks.py` | **CREATE** | Task queue endpoints per §23.4 |
| `tests/unit/test_scheduler.py` | **CREATE** | Scheduler tests |

**Tests (~15):**
- Priority ordering: critical > high > normal > background
- FIFO within tier: same priority → earliest queued_at first
- Dependency resolution: sequential tasks wait for predecessors
- Independent tasks: may execute concurrently
- Circular dependency: detected and rejected
- Chain depth: chains > 5 rejected
- Failed dependency: cancels downstream tasks
- LLM cannot influence ordering

**Test gate:**
```bash
pytest tests/unit/test_scheduler.py -v
```

---

### Phase AB4: Durable Queue & Private Domain Availability (~20 min)

**Goal:** No resilience for private domain unavailability exists. This phase implements the durable queue that holds private tasks when the private domain is down, with retry, timeout, and user notification.

**Spec refs:** SPEC.md §17.1, §17.2, §17.3

**Depends on:** DW1, AB3
**Blocks:** None

**Integration contracts (R4):**
- `DurableQueue.enqueue(task_type, payload, idempotency_key, timeout)` → `queue_id`
- `DurableQueue.poll()` → next ready task (respects retry backoff)
- `HealthChecker.is_available()` → `bool` (polls private container every 30s)
- Retry schedule: 5s, 15s, 45s exponential backoff; max queue depth: 50
- Idempotency window: 24h; duplicate keys rejected

**Deliverables:**
1. Durable queue in Postgres (survives API restart) per §17.2
2. Private container health check (30-second polling) per §17.1
3. Exponential backoff retries (5s, 15s, 45s) per §17.2
4. Queue depth limit (50 tasks), timeout per task type
5. User notifications for queue state changes per §17.3

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/queue/__init__.py` | **CREATE** | Queue package |
| `src/noa/queue/durable.py` | **CREATE** | Postgres-backed durable queue per §17.2 |
| `src/noa/queue/health.py` | **CREATE** | Private container health check per §17.1 |
| `src/noa/queue/notifications.py` | **CREATE** | User notification service per §17.3 |
| `tests/unit/test_durable_queue.py` | **CREATE** | Durable queue tests |

**Tests (~12):**
- Queue persistence: tasks survive API restart
- Idempotency: duplicate idempotency_key within 24h rejected
- Timeout: tasks fail after timeout with `private_domain_unavailable`
- Retry: exponential backoff at 5s, 15s, 45s
- Max depth: tasks rejected beyond 50
- Cancellation: user can cancel queued tasks
- Health check: container health polled every 30s
- Never fallback: private tasks never route to external

**Test gate:**
```bash
pytest tests/unit/test_durable_queue.py -v
```

---

### Phase AB5: Coding Task Contract & Worker (~20 min)

**Goal:** No coding task execution exists. This phase implements the coding task contract (input/output schema), the shell sandbox within the external container, and structured output from coding tasks.

**Spec refs:** SPEC.md §15, §2.4, §8.2 (Shell Sandbox)

**Depends on:** DW2
**Blocks:** None

**Integration contracts (R4):**
- `CodingContract` Pydantic models for input (repo, objective, constraints, test_command, max_iterations=3) and output (diff, test_results, lint, summary)
- `ShellSandbox.run(cmd, timeout=300, mem_limit="4g")` → `ShellResult(stdout, stderr, exit_code)`
- Max concurrent shells: 2; workspace scoping enforced via chroot/namespace
- Every command + exit code logged to audit

**Deliverables:**
1. Coding task input/output schema per §15
2. Shell sandbox execution (chroot, resource caps, audit) per §2.4
3. Structured coding output (diff, test results, lint, summary)
4. Workspace scoping enforcement (no access outside workspace)
5. Max iteration enforcement per §15

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/coding/__init__.py` | **CREATE** | Coding package |
| `src/noa/coding/contract.py` | **CREATE** | Coding task input/output schemas per §15 |
| `src/noa/coding/sandbox.py` | **CREATE** | Shell sandbox execution per §2.4 |
| `src/noa/coding/worker.py` | **CREATE** | Coding task worker (run tests, generate diff) |
| `tests/unit/test_coding.py` | **CREATE** | Coding task tests |

**Tests (~15):**
- Contract validation: tasks require all fields per §15
- Shell sandbox: commands scoped to workspace, resource-capped
- Output structure: diff, test results, lint, summary returned
- Workspace isolation: no access to paths outside workspace
- Max iterations: task aborted after max_iterations
- Audit: every shell command + exit code logged
- No private access: coding worker cannot reach private domain

**Test gate:**
```bash
pytest tests/unit/test_coding.py -v
```

---

## Wave 6: Web Client

Builds the React web UI as the primary interface. After this wave, users can interact with Noa through a full-featured web application installable as a PWA.

---

### Phase WC1: React Project Setup & Chat UI with SSE (~45 min)

**Goal:** No web interface exists. This phase creates the React application with real-time chat using SSE streaming from the Run/Event model.

**Spec refs:** SPEC.md §29.1, §29.2, §22.4

**Depends on:** OC2
**Blocks:** WC2, WC3, WC4, WC5, WC6, WC7

**Deliverables:**
1. React + Vite project setup
2. Chat interface with message input and streaming response display
3. SSE client consuming `/api/v1/runs/{run_id}/events`
4. Token streaming (character-by-character display)
5. Conversation thread management (create, list, resume, delete)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `web/package.json` | **CREATE** | React + Vite project dependencies |
| `web/vite.config.ts` | **CREATE** | Vite configuration |
| `web/src/App.tsx` | **CREATE** | App root with routing |
| `web/src/components/Chat/ChatView.tsx` | **CREATE** | Main chat interface |
| `web/src/components/Chat/MessageList.tsx` | **CREATE** | Message display with streaming |
| `web/src/components/Chat/MessageInput.tsx` | **CREATE** | User input with model selector |
| `web/src/hooks/useSSE.ts` | **CREATE** | SSE client hook per §22.4 |
| `web/src/api/client.ts` | **CREATE** | API client with auth |
| `web/src/api/runs.ts` | **CREATE** | Run/Event API client |
| `web/src/store/chat.ts` | **CREATE** | Chat state management |
| `tests/web/test_chat.tsx` | **CREATE** | Chat component tests |

**Tests (~15):**
- Chat render: messages display correctly
- SSE streaming: tokens render incrementally
- Message send: user input creates run via API
- Thread management: create, switch, delete threads
- Auth: API client includes auth token
- Model selector: user can select provider per message

**Test gate:**
```bash
cd web && npm test -- --run
```

---

### Phase WC2: Run Timeline & Event Details (~30 min)

**Goal:** No run visibility exists in the UI. This phase adds a run timeline showing all events for a run, enabling users to see the full execution path.

**Spec refs:** SPEC.md §22.2, §29.2

**Depends on:** WC1
**Blocks:** None

**Deliverables:**
1. Run timeline component showing ordered events
2. Event type indicators (classification, tool calls, approvals, results)
3. Event detail expansion (tool args, results, timing)
4. Run history list (recent runs with status)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/Run/RunTimeline.tsx` | **CREATE** | Run timeline with events |
| `web/src/components/Run/EventCard.tsx` | **CREATE** | Individual event display |
| `web/src/components/Run/RunHistory.tsx` | **CREATE** | Run history list |
| `tests/web/test_run_timeline.tsx` | **CREATE** | Run timeline tests |

**Tests (~12):**
- Timeline render: events display in order
- Event types: all event types render with appropriate indicators
- Event details: expandable detail view
- Run history: recent runs listed with status
- Real-time updates: new events appear via SSE

**Test gate:**
```bash
cd web && npm test -- --run
```

---

### Phase WC3: Approval Interface with Dry-Run Previews (~30 min)

**Goal:** No approval UI exists. This phase creates the approval interface where users review dry-run previews and approve/deny Medium/High risk actions.

**Spec refs:** SPEC.md §19.2, §21, §29.6

**Depends on:** WC1, OC4
**Blocks:** None

**Deliverables:**
1. Approval request notification in the UI
2. Dry-run preview display (diff-like summary)
3. Approve/Deny/Edit controls
4. Batch approval UI for multiple pending approvals per §23.2
5. Step-up auth indicator for High-risk actions

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/Approval/ApprovalPanel.tsx` | **CREATE** | Approval panel with preview |
| `web/src/components/Approval/PreviewCard.tsx` | **CREATE** | Dry-run preview display |
| `web/src/components/Approval/ApprovalBatch.tsx` | **CREATE** | Batch approval UI |
| `web/src/api/approvals.ts` | **CREATE** | Approval API client |
| `tests/web/test_approval.tsx` | **CREATE** | Approval UI tests |

**Tests (~12):**
- Approval notification: appears when approval_requested event received
- Preview display: dry-run summary renders correctly
- Approve action: sends approval, run resumes
- Deny action: sends denial, run cancelled
- Batch: multiple approvals grouped and manageable
- High-risk indicator: step-up auth badge displayed

**Test gate:**
```bash
cd web && npm test -- --run
```

---

### Phase WC4: Task Queue Visualization (~20 min)

**Goal:** No task queue visibility exists. This phase adds a visual task queue showing active, queued, and completed runs with status and user controls.

**Spec refs:** SPEC.md §23.4

**Depends on:** WC1
**Blocks:** None

**Deliverables:**
1. Task queue panel showing all active/queued/completed runs
2. Per-run status, priority, position display
3. User controls: cancel queued tasks, retry failed tasks
4. Real-time queue updates via SSE

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/Queue/TaskQueue.tsx` | **CREATE** | Task queue panel |
| `web/src/components/Queue/QueueItem.tsx` | **CREATE** | Individual queue item |
| `tests/web/test_queue.tsx` | **CREATE** | Task queue tests |

**Tests (~10):**
- Queue render: items display with status and priority
- Cancel: user can cancel queued tasks
- Retry: user can retry failed tasks
- Real-time: queue updates as tasks progress
- Priority display: items ordered by priority tier

**Test gate:**
```bash
cd web && npm test -- --run
```

---

### Phase WC5: Memory Audit UI (~30 min)

**Goal:** No memory management UI exists. This phase creates the Memory Audit UI where users can review, approve, edit, and delete stored facts.

**Spec refs:** SPEC.md §13.2 (Auto-Extraction Guardrails)

**Depends on:** WC1, TI1
**Blocks:** None

**Deliverables:**
1. Memory Audit panel showing all stored facts
2. Fact filtering by category (preference, habit, project context, personal info)
3. Pending fact review queue (approve, edit, discard)
4. Fact deletion with immediate removal
5. Memory stats display (total facts, per-category, storage size)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/Memory/MemoryAudit.tsx` | **CREATE** | Memory audit panel |
| `web/src/components/Memory/FactCard.tsx` | **CREATE** | Individual fact display with actions |
| `web/src/components/Memory/MemoryStats.tsx` | **CREATE** | Memory statistics display |
| `web/src/api/memory.ts` | **CREATE** | Memory API client |
| `tests/web/test_memory_audit.tsx` | **CREATE** | Memory audit tests |

**Tests (~12):**
- Fact display: facts render with category and status
- Filter: filter by category works
- Approve: pending facts can be approved
- Edit: facts can be edited before approval
- Delete: facts deleted immediately
- Stats: total facts, per-category counts display

**Test gate:**
```bash
cd web && npm test -- --run
```

---

### Phase WC6: Cost Dashboard & Settings (~25 min)

**Goal:** No cost visibility or settings UI exists. This phase adds the cost dashboard showing token usage and budget progress, and the admin settings panel.

**Spec refs:** SPEC.md §24, §14.4, §29.2

**Depends on:** WC1, AB1
**Blocks:** None

**Deliverables:**
1. Cost dashboard: per-message, session, daily, monthly breakdown with budget progress bar
2. Settings panel: default provider, privacy mode, temperature, token caps
3. Model selection UI per §14.4
4. Privacy mode toggle per §14.4

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/Cost/CostDashboard.tsx` | **CREATE** | Cost dashboard with budget bars |
| `web/src/components/Settings/SettingsPanel.tsx` | **CREATE** | Admin settings |
| `web/src/components/Settings/ModelSelector.tsx` | **CREATE** | Model/provider selection |
| `web/src/api/settings.ts` | **CREATE** | Settings API client |
| `tests/web/test_cost_settings.tsx` | **CREATE** | Cost dashboard + settings tests |

**Tests (~10):**
- Cost display: per-message breakdown renders
- Budget bar: daily/monthly progress displays
- Settings: default provider selectable
- Privacy toggle: privacy mode toggle works
- Model selector: provider + model selectable per message

**Test gate:**
```bash
cd web && npm test -- --run
```

---

### Phase WC7: Artifact Viewer & PWA Manifest (~25 min)

**Goal:** No artifact viewing or PWA capability exists. This phase adds the artifact viewer for diffs/files/exports and the PWA manifest for iPhone installation.

**Spec refs:** SPEC.md §22.3, §29.2, §29.3

**Depends on:** WC1
**Blocks:** None

**Deliverables:**
1. Artifact viewer: display diffs, files, and exports from runs
2. Diff viewer with syntax highlighting
3. PWA manifest for installable web app on iPhone
4. Service worker for offline shell and caching

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `web/src/components/Artifacts/ArtifactViewer.tsx` | **CREATE** | Artifact display component |
| `web/src/components/Artifacts/DiffViewer.tsx` | **CREATE** | Diff viewer with syntax highlighting |
| `web/public/manifest.json` | **CREATE** | PWA manifest per §29.3 |
| `web/public/sw.js` | **CREATE** | Service worker for PWA |
| `tests/web/test_artifacts.tsx` | **CREATE** | Artifact viewer tests |

**Tests (~10):**
- Artifact render: files display with correct mime type
- Diff viewer: diffs render with syntax highlighting
- PWA manifest: valid manifest with required fields
- Installable: meets PWA installability criteria

**Test gate:**
```bash
cd web && npm test -- --run
```

---

## Wave 8: Credential Management

Extends the settings system to persist user preferences in the database and adds configuration fields for all tool API keys and LLM provider/model selection. After this wave, users can configure credentials via the UI and the backend stores them securely in Postgres (with keychain injection handled by CM2).

---

### Phase CM1: Extend Settings with Tool Credentials (~30 min)

**Goal:** Settings are currently stubbed — the GET endpoint returns hardcoded defaults and PUT doesn't persist. No `user_settings` table exists. This phase creates the settings persistence layer, extends the schema with tool credential fields and LLM provider/model selection, and wires the frontend to display credential configuration.

**Spec refs:** SPEC.md §11.1 (secret categories), §24 (cost control budgets), §12 (tool definitions — which tools need keys)

**Depends on:** F2 (database), F4 (auth), WM3 (settings endpoints exist)
**Blocks:** CM2 (keychain bootstrap needs settings schema), LP1-LP5 (LLM providers need configured keys)

**Deliverables:**
1. `user_settings` table in Postgres via Alembic migration
2. SQLAlchemy ORM model for UserSettings (one row per user)
3. Settings repository layer (get, upsert)
4. Settings endpoints wired to database (replace stubs)
5. Extended settings schema: tool API keys (Anthropic, OpenAI, Google, Notion, Tavily), LLM provider/model, Ollama base URL
6. Frontend settings page extended with credential fields (masked input for API keys)
7. API key values never returned in full — GET returns masked versions (last 4 chars only)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `alembic/versions/002_user_settings.py` | **CREATE** | Migration: `user_settings` table |
| `src/noa/settings/__init__.py` | **CREATE** | Settings package |
| `src/noa/settings/models.py` | **CREATE** | SQLAlchemy ORM model for UserSettings |
| `src/noa/settings/repository.py` | **CREATE** | Settings CRUD (get_by_user_id, upsert) |
| `src/noa/settings/service.py` | **CREATE** | Settings service with masking logic |
| `src/noa/api/v1/settings.py` | **EDIT** | Wire to real DB via settings service |
| `web/src/api/types.ts` | **EDIT** | Add credential fields to UserSettings type |
| `web/src/pages/Settings.tsx` | **EDIT** | Add API key inputs (masked), LLM provider/model, Ollama URL |
| `tests/unit/test_settings.py` | **CREATE** | Settings persistence + masking tests |

**Database schema (`user_settings`):**

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `user_id` | UUID | FK → users.id, UNIQUE |
| `default_model` | VARCHAR(64) | e.g. "claude-sonnet-4-20250514" |
| `default_provider` | VARCHAR(32) | e.g. "anthropic", "openai", "ollama" |
| `default_privacy_mode` | VARCHAR(16) | "standard" or "external" |
| `budget_daily_usd` | NUMERIC(10,2) | Daily spending limit |
| `budget_monthly_usd` | NUMERIC(10,2) | Monthly spending limit |
| `anthropic_api_key` | VARCHAR(256) | Encrypted at rest (Phase 2: keychain) |
| `openai_api_key` | VARCHAR(256) | Encrypted at rest |
| `google_client_id` | VARCHAR(256) | OAuth2 client ID |
| `google_client_secret` | VARCHAR(256) | OAuth2 client secret |
| `notion_token` | VARCHAR(256) | Integration token |
| `tavily_api_key` | VARCHAR(256) | Search API key |
| `ollama_base_url` | VARCHAR(512) | Default: http://private-worker:11434 |
| `created_at` | TIMESTAMP | Auto-set |
| `updated_at` | TIMESTAMP | Auto-updated |

**Security constraints:**
- API key columns stored as plaintext in DB for now (CM2 adds keychain; encryption-at-rest via Postgres TDE is a Phase 2 concern)
- GET endpoint NEVER returns full API keys — returns masked versions: `"sk-...AbCd"` (last 4 chars)
- PUT endpoint accepts full keys for storage, or `null` to clear
- Secrets never logged, even at debug level (per §11.2)

**Tests (~15):**
- Repository: upsert creates new settings for user
- Repository: upsert updates existing settings
- Repository: get returns None for unknown user
- Service: get_settings returns defaults when no DB row
- Service: get_settings masks API keys (last 4 chars only)
- Service: update_settings persists to DB
- Service: update_settings with null key clears the key
- Service: empty string key treated as null (cleared)
- API: GET /settings returns masked keys
- API: PUT /settings persists and returns masked keys
- API: PUT /settings with partial update preserves other fields
- API: unauthenticated request returns 401
- Masking: short keys still masked safely
- Masking: None/empty keys return null (not masked)

**Test gate:**
```bash
pytest tests/unit/test_settings.py -v
```

---

### Phase CM2: macOS Keychain Bootstrap (~45 min)

**Goal:** API keys stored in Postgres are not production-secure. This phase creates shell scripts for macOS Keychain integration that store secrets in the system keychain and inject them into Docker containers at startup via environment variables.

**Spec refs:** SPEC.md §11.1, §11.2, §11.3

**Depends on:** CM1
**Blocks:** None (downstream phases can use either DB keys or keychain-injected env vars)

**Deliverables:**
1. `tools/keychain_store.sh` — Store/retrieve secrets in macOS Keychain
2. `tools/keychain_bootstrap.sh` — Read all secrets from keychain, write `.env.secrets` for docker-compose
3. Docker-compose env_file wiring for `.env.secrets`
4. Config.py extended to read API keys from env vars (override DB values)
5. Documentation in `tools/README_KEYCHAIN.md`

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `tools/keychain_store.sh` | **CREATE** | CLI to set/get/delete keychain entries |
| `tools/keychain_bootstrap.sh` | **CREATE** | Generate `.env.secrets` from keychain |
| `docker-compose.yml` | **EDIT** | Add env_file: .env.secrets |
| `src/noa/config.py` | **EDIT** | Add optional env vars for all API keys |
| `src/noa/settings/service.py` | **EDIT** | Env var overrides DB values for API keys |
| `tools/README_KEYCHAIN.md` | **CREATE** | Setup instructions |
| `tests/unit/test_keychain_config.py` | **CREATE** | Env var override tests |
| `.gitignore` | **EDIT** | Add .env.secrets |

**Tests (~8):**
- Config: env var API keys parsed correctly
- Config: env var overrides DB-stored key
- Config: missing env var falls back to DB value
- Service: get_effective_key checks env first, then DB
- Bootstrap script: generates valid env file format
- Store script: set/get/delete operations (mocked keychain)

**Test gate:**
```bash
pytest tests/unit/test_keychain_config.py -v
```

---

## Wave 9: LLM Provider Wiring

Replaces stub `_send_request` / `build_request` implementations with real httpx-based HTTP clients for all four LLM providers, then upgrades ProviderRouter into a dispatch hub that instantiates clients and routes `complete()` calls with privacy enforcement. After this wave, every provider can be called over HTTP (mocked in tests, real in production).

---

### Phase LP1: Anthropic Client HTTP (~30 min)

**Goal:** The existing AnthropicClient is a stub — `_send_request` raises `NotImplementedError`. This phase implements real httpx calls to the Anthropic Messages API (`/v1/messages`), including tool_use block support and retry on 429/529 rate limits.

**Spec refs:** SPEC.md §14.1, §14.4

**Depends on:** CM1, CM2
**Blocks:** LP5

**Deliverables:**
1. Real async `_send_request()` using `httpx.AsyncClient` with Bearer auth header
2. Response parsing: extract `content[0].text`, `usage.input_tokens`, `usage.output_tokens`
3. Tool use support: detect `tool_use` content blocks and return them as `tool_calls`
4. Retry logic: exponential backoff on 429 (rate limit) and 529 (overloaded), max 3 retries
5. Proper error mapping: 401→ProviderError("invalid API key"), 400→ProviderError with detail, 5xx→ProviderError

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/external_worker/llm/anthropic.py` | **MODIFY** | Replace stub with real httpx calls |
| `tests/unit/test_llm_anthropic.py` | **CREATE** | Dedicated Anthropic client tests |

**Tests (~8):**
- `_send_request` makes POST to `/v1/messages` with correct headers (x-api-key, anthropic-version)
- Successful response parsed: text content extracted, usage tokens captured
- Tool use blocks in response returned as `tool_calls` list
- 429 response triggers retry with backoff (up to 3 retries)
- 529 response triggers retry
- 401 response raises ProviderError with "invalid API key"
- 400 response raises ProviderError with error detail
- Timeout raises ProviderError

**Test gate:**
```bash
pytest tests/unit/test_llm_anthropic.py -v
```

---

### Phase LP2: OpenAI Client HTTP (~30 min)

**Goal:** The existing OpenAIClient is a stub. This phase implements real httpx calls to the OpenAI Chat Completions API (`/v1/chat/completions`), with tool_calls JSON parsing and retry on 429.

**Spec refs:** SPEC.md §14.1, §14.4

**Depends on:** CM1, CM2
**Blocks:** LP5

**Deliverables:**
1. Real async `_send_request()` using `httpx.AsyncClient` with Bearer Authorization header
2. Response parsing: extract `choices[0].message.content`, `usage.prompt_tokens`, `usage.completion_tokens`
3. Tool calls support: parse `choices[0].message.tool_calls` into normalized `tool_calls` list
4. Retry logic: exponential backoff on 429, max 3 retries
5. Error mapping: 401→ProviderError("invalid API key"), 4xx/5xx→ProviderError

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/external_worker/llm/openai.py` | **MODIFY** | Replace stub with real httpx calls |
| `tests/unit/test_llm_openai.py` | **CREATE** | Dedicated OpenAI client tests |

**Tests (~8):**
- `_send_request` makes POST to `/v1/chat/completions` with Authorization Bearer header
- Successful response parsed: content and usage extracted
- Tool calls in response parsed into normalized format
- 429 triggers retry with backoff
- 401 raises ProviderError with "invalid API key"
- 5xx raises ProviderError
- Timeout raises ProviderError
- `top_p` parameter included in request when set

**Test gate:**
```bash
pytest tests/unit/test_llm_openai.py -v
```

---

### Phase LP3: Google AI Client (New) (~30 min)

**Goal:** No Google AI client exists. This phase creates a new `GoogleAIClient` for the Gemini API via the `generateContent` endpoint, following the same interface pattern as Anthropic/OpenAI clients.

**Spec refs:** SPEC.md §14.1, §14.4

**Depends on:** CM1, CM2
**Blocks:** LP5

**Deliverables:**
1. New `GoogleAIClient` class with `__init__(api_key, model)` constructor
2. `build_request()` formats messages into Gemini `contents` format (role mapping: user→user, assistant→model)
3. Real async `_send_request()` via httpx POST to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}`
4. Response parsing: extract `candidates[0].content.parts[0].text`, usage from `usageMetadata`
5. Function call support: detect `functionCall` parts and return as `tool_calls`
6. Error mapping: 403→ProviderError("invalid API key"), 429→retry, 5xx→ProviderError

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/external_worker/llm/google_ai.py` | **CREATE** | Google AI (Gemini) client |
| `src/noa/external_worker/llm/__init__.py` | **MODIFY** | Export GoogleAIClient |
| `tests/unit/test_llm_google_ai.py` | **CREATE** | Google AI client tests |

**Tests (~8):**
- `build_request` maps messages to Gemini `contents` format (role mapping)
- `_send_request` POSTs to correct generateContent URL with API key param
- Successful response parsed: text and usage extracted
- Function call parts returned as `tool_calls`
- 403 raises ProviderError with "invalid API key"
- 429 triggers retry with backoff
- 5xx raises ProviderError
- Timeout raises ProviderError

**Test gate:**
```bash
pytest tests/unit/test_llm_google_ai.py -v
```

---

### Phase LP4: Ollama Client HTTP (~20 min)

**Goal:** The existing OllamaClient uses `/api/generate` (completion-style). This phase upgrades it to use `/api/chat` (chat-style), adds real async httpx calls, and enforces model manifest approval per §8.1.

**Spec refs:** SPEC.md §8.1, §14.1

**Depends on:** CM1, CM2
**Blocks:** LP5

**Deliverables:**
1. Switch from `/api/generate` to `/api/chat` endpoint (chat messages format)
2. Real async `_send_request()` using `httpx.AsyncClient` (no auth needed — local service)
3. `complete()` method matching the same interface as external clients (messages, max_tokens, temperature)
4. Model manifest enforcement: reject unapproved models before sending request
5. Response parsing: extract `message.content`, eval_count/prompt_eval_count for usage

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/private_worker/ollama_client.py` | **MODIFY** | Real httpx calls to /api/chat |
| `tests/unit/test_llm_ollama.py` | **CREATE** | Ollama client tests |

**Tests (~7):**
- `build_request` formats messages for `/api/chat` endpoint
- `complete()` sends POST to `{base_url}/api/chat`
- Successful response parsed: content and usage extracted
- Unapproved model rejected before request sent (raises ProviderError)
- Approved model passes manifest check
- Connection error (Ollama not running) raises ProviderError
- Timeout raises ProviderError

**Test gate:**
```bash
pytest tests/unit/test_llm_ollama.py -v
```

---

### Phase LP5: ProviderRouter as Dispatch Hub (~30 min)

**Goal:** The existing ProviderRouter only does `select()` — it returns a provider name string. This phase upgrades it to instantiate real clients from settings, dispatch `complete()` calls, and enforce privacy invariants (private→Ollama only).

**Spec refs:** SPEC.md §14.2, §14.3, §14.4

**Depends on:** LP1, LP2, LP3, LP4
**Blocks:** CP1 (Wave 10)

**Deliverables:**
1. `from_settings(settings)` class method: creates router with client instances from UserSettings credentials
2. Async `complete(messages, max_tokens, privacy_mode, provider, model, **kwargs)` dispatch method
3. Privacy enforcement: `private` mode → always route to Ollama client, never external
4. Provider/model override: user-selected provider used if compatible with privacy mode
5. Normalized response: all clients return `{"content": str, "tool_calls": list, "usage": {"input_tokens": int, "output_tokens": int}, "provider": str, "model": str}`

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/external_worker/llm/router.py` | **MODIFY** | Add from_settings, complete(), dispatch |
| `tests/unit/test_llm_router.py` | **CREATE** | Router dispatch tests |

**Tests (~9):**
- `from_settings` creates router with Anthropic client when key present
- `from_settings` creates router with OpenAI client when key present
- `from_settings` creates router with Google AI client when key present
- `from_settings` creates Ollama client from base_url setting
- `complete()` dispatches to correct provider client
- `complete()` with `privacy_mode="private"` routes to Ollama only
- `complete()` with `privacy_mode="private"` + external provider raises PrivacyViolationError
- `complete()` with user-selected provider overrides default
- Response includes normalized fields (content, tool_calls, usage, provider, model)

**Test gate:**
```bash
pytest tests/unit/test_llm_router.py -v
```

---

## Wave 10: End-to-End Chat Pipeline

Connects all existing pieces into a working chat pipeline: LLM invocation through ProviderRouter, orchestrator graph execution with SSE event streaming, real chat endpoint with DB persistence, and app startup wiring. After this wave, a user can send a chat message and receive a real LLM response streamed back via SSE.

---

### Phase CP1: Wire invoke_llm to ProviderRouter (~30 min)

**Goal:** The `invoke_llm()` function in `agent_node` raises `NotImplementedError`. This phase replaces it with an async function that calls `ProviderRouter.complete()`, bridging the orchestrator graph to real LLM backends.

**Spec refs:** SPEC.md §2.2, §14.2, §14.3

**Depends on:** LP5 (Wave 9)
**Blocks:** CP2, CP3

**Deliverables:**
1. Module-level `_router: ProviderRouter | None` with `set_router()` / `get_router()` in agent module
2. Async `invoke_llm(model, messages, privacy_mode, max_tokens)` that calls `ProviderRouter.complete()`
3. `agent_node` becomes async to support the async `invoke_llm`
4. Response adapter: ProviderRouter returns `dict` → agent_node expects object with `.content` / `.tool_calls` — create a simple `LLMResponse` dataclass wrapper
5. Existing tests remain green (they patch `invoke_llm`)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/orchestrator/nodes/agent.py` | **MODIFY** | Replace stub, add set_router, async invoke_llm, LLMResponse |
| `tests/unit/test_cp1_invoke_llm.py` | **CREATE** | Tests for wired invoke_llm |

**Tests (~10):**
- `set_router` / `get_router` stores and retrieves ProviderRouter
- `invoke_llm` raises RuntimeError when no router configured
- `invoke_llm` calls `router.complete()` with correct args
- `invoke_llm` returns LLMResponse with `.content` and `.tool_calls`
- `invoke_llm` passes `privacy_mode` through to router
- `invoke_llm` passes `max_tokens` (default 4096) through to router
- `agent_node` (async) returns tool_calls from LLM response
- `agent_node` (async) returns response when no tool_calls
- `agent_node` (async) enforces MAX_TOOL_CALLS cap
- `agent_node` (async) appends assistant message to conversation

**Test gate:**
```bash
pytest tests/unit/test_cp1_invoke_llm.py -v
```

---

### Phase CP2: OrchestratorRunner + Event Types (~45 min)

**Goal:** No runner exists to execute the graph and produce SSE events. This phase creates `OrchestratorRunner` that compiles the graph, runs it with an input state, emits structured SSE events during execution, and records events via `RunService`.

**Spec refs:** SPEC.md §2.1, §22.1, §22.2, §22.4

**Depends on:** CP1
**Blocks:** CP3

**Deliverables:**
1. `OrchestratorRunner` class in `src/noa/orchestrator/runner.py`
2. `run()` async generator method: takes user message + config, yields SSE event dicts
3. Events emitted: `message_received`, `classification_done`, `step_started`, `token_stream` (for response), `tool_called`, `tool_result`, `result_ready`, `error`
4. Each event also appended to Run via RunService
5. Run status transitions: pending → running → completed/failed

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/orchestrator/runner.py` | **CREATE** | OrchestratorRunner class |
| `tests/unit/test_cp2_runner.py` | **CREATE** | Runner tests |

**Tests (~12):**
- Runner initializes with compiled graph
- `run()` yields `message_received` event first
- `run()` yields `classification_done` after router node
- `run()` yields `step_started` before agent node
- `run()` yields `tool_called` for each tool call
- `run()` yields `tool_result` for each tool result
- `run()` yields `result_ready` with final response
- `run()` yields `error` event on exception
- All yielded events have correct shape (event_type, payload, timestamp)
- Run status transitions from pending → running → completed
- Run status transitions to failed on error
- Events are appended to RunService

**Test gate:**
```bash
pytest tests/unit/test_cp2_runner.py -v
```

---

### Phase CP3: Chat Endpoint → Real Pipeline (~45 min)

**Goal:** The `/api/v1/chat` endpoint is a stub returning a run_id. This phase wires it to create a real Conversation + Run in the database, invoke `OrchestratorRunner`, and stream SSE events back to the client.

**Spec refs:** SPEC.md §22.4, §25.1

**Depends on:** CP2
**Blocks:** CP4

**Deliverables:**
1. Chat endpoint creates Conversation (or reuses existing thread_id)
2. Chat endpoint creates Run with RunService
3. Chat endpoint persists user Message
4. Response is SSE `StreamingResponse` that yields events from OrchestratorRunner
5. Error handling: LLM failures produce `error` event, Run set to `failed`
6. Existing SSE endpoint (`/runs/{run_id}/events`) now reads real events from DB

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/api/v1/chat.py` | **MODIFY** | Wire to real pipeline with SSE streaming |
| `src/noa/api/v1/runs.py` | **MODIFY** | SSE endpoint reads real events from DB |
| `tests/unit/test_cp3_chat_endpoint.py` | **CREATE** | Chat endpoint integration tests |

**Tests (~10):**
- POST `/api/v1/chat` returns StreamingResponse (SSE)
- Response includes `run_id` and `thread_id` in initial event
- New thread created when `thread_id` is null
- Existing thread reused when `thread_id` provided
- User message persisted in DB
- Run created with correct privacy_mode
- SSE stream includes `message_received` event
- SSE stream includes `result_ready` event with response
- Error in pipeline produces `error` SSE event
- GET `/runs/{run_id}/events` returns persisted events

**Test gate:**
```bash
pytest tests/unit/test_cp3_chat_endpoint.py -v
```

---

### Phase CP4: App Startup Wiring (~30 min)

**Goal:** The app lifespan only initializes DB engine and health checker. This phase wires ProviderRouter, ToolRegistry, and OrchestratorRunner into the lifespan so they're available for the chat pipeline.

**Spec refs:** SPEC.md §4.1, §14.2

**Depends on:** CP3
**Blocks:** Wave 11

**Deliverables:**
1. Build `ProviderRouter.from_settings(settings)` in lifespan
2. Store router in `app_state` (new `set_provider_router` / `get_provider_router`)
3. Call `set_router()` on agent module so `invoke_llm` works
4. Build `ToolRegistry` from available tools, call `set_registry()` on tools module
5. Store `OrchestratorRunner` in `app_state` for chat endpoint access
6. Graceful degradation: if no LLM keys configured, log warning but don't crash

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/api/app.py` | **MODIFY** | Wire ProviderRouter, ToolRegistry, Runner in lifespan |
| `src/noa/api/app_state.py` | **MODIFY** | Add provider_router and runner getters/setters |
| `tests/unit/test_cp4_startup.py` | **CREATE** | Startup wiring tests |

**Tests (~9):**
- `app_state` has `set_provider_router` / `get_provider_router`
- `app_state` has `set_runner` / `get_runner`
- Lifespan builds ProviderRouter from settings
- Lifespan calls `set_router()` on agent module
- Lifespan calls `set_registry()` on tools module
- Lifespan creates OrchestratorRunner
- Lifespan stores runner in app_state
- Missing LLM keys don't crash startup (graceful degradation)
- Shutdown disposes resources cleanly

**Test gate:**
```bash
pytest tests/unit/test_cp4_startup.py -v
```

---

## Wave 11: Tool Gateway + Tavily

Builds the transport-agnostic tool execution layer between the orchestrator and external APIs. After this wave, the LLM can request a web search and get real Tavily results back through the gateway — with governance (idempotency, rate limiting, dry-run previews) and telemetry baked in.

---

### Phase TG1: ToolRequest/ToolResponse + ToolGateway (~30 min)

**Goal:** Tool execution currently goes through the `ToolRegistry.dispatch()` method which calls tools directly. This phase introduces a transport-agnostic gateway layer with standardized request/response types, governance enforcement, and telemetry hooks — making it ready for both direct API calls (Wave 11) and MCP adapters (Wave 12).

**Spec refs:** SPEC.md §19.1 (idempotency), §19.2 (dry-run previews), §19.3 (rate limits), §2.1 (deterministic outer shell)

**Depends on:** CP4 (app startup wiring), TI6 (tool governance)
**Blocks:** TG2, TG3

**Deliverables:**
1. `ToolRequest` dataclass — tool name, function, args, idempotency_key, privacy_mode, caller metadata
2. `ToolResponse` dataclass — result data, error, latency_ms, provider, cached flag
3. `ToolGateway` class — central dispatch hub that:
   - Resolves tool name → adapter (DirectApiAdapter, McpAdapter, etc.)
   - Enforces governance via existing `GovernanceWrapper` (idempotency, rate limits, dry-run)
   - Records telemetry per call (latency, status, tool name, function)
   - Validates tool is in allowlist before execution
4. `ToolAdapter` protocol — interface that adapters implement (`execute(request) → response`)
5. Integration: `tool_node` in orchestrator dispatches through `ToolGateway` instead of `ToolRegistry`

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/gateway.py` | **CREATE** | ToolRequest, ToolResponse, ToolAdapter protocol, ToolGateway class |
| `src/noa/orchestrator/nodes/tools.py` | **MODIFY** | Dispatch through ToolGateway when available |
| `tests/unit/test_tg1_gateway.py` | **CREATE** | ToolGateway unit tests |

**Tests (~12):**
- ToolRequest can be created with all required fields
- ToolResponse can be created with result data
- ToolResponse can be created with error
- ToolGateway registers adapter by tool name
- ToolGateway dispatches to correct adapter by tool name
- ToolGateway rejects tool not in allowlist
- ToolGateway records telemetry (latency_ms, status)
- ToolGateway passes idempotency_key through to governance
- ToolGateway respects rate limits via governance wrapper
- ToolGateway supports dry-run mode (returns preview, no execution)
- tool_node dispatches through ToolGateway when set
- tool_node falls back to legacy ToolRegistry when no gateway

**Test gate:**
```bash
pytest tests/unit/test_tg1_gateway.py -v
```

---

### Phase TG2: DirectApiAdapter (~20 min)

**Goal:** The ToolGateway needs adapters to actually execute tools. This phase creates `DirectApiAdapter` — an adapter that calls tool functions directly via HTTP (for tools like Tavily, Google APIs that are plain REST calls from the external container).

**Spec refs:** SPEC.md §8.2 (external container egress), §12.4 (web search)

**Depends on:** TG1
**Blocks:** TG3

**Deliverables:**
1. `DirectApiAdapter` class implementing `ToolAdapter` protocol
2. Wraps an existing `ToolInterface` implementation (e.g., `WebSearchTool`)
3. Converts `ToolRequest` → tool's `execute()` call → `ToolResponse`
4. Captures latency and error details in response
5. Handles async execution correctly

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/adapters/__init__.py` | **CREATE** | Adapters package |
| `src/noa/tools/adapters/direct.py` | **CREATE** | DirectApiAdapter wrapping ToolInterface |
| `tests/unit/test_tg2_direct_adapter.py` | **CREATE** | DirectApiAdapter unit tests |

**Tests (~8):**
- DirectApiAdapter implements ToolAdapter protocol
- DirectApiAdapter wraps a ToolInterface and forwards execute calls
- DirectApiAdapter converts ToolRequest args to tool execute() kwargs
- DirectApiAdapter wraps tool result in ToolResponse
- DirectApiAdapter captures latency_ms in response
- DirectApiAdapter captures errors in ToolResponse (no exception leak)
- DirectApiAdapter sets provider field to "direct"
- DirectApiAdapter passes function name correctly to underlying tool

**Test gate:**
```bash
pytest tests/unit/test_tg2_direct_adapter.py -v
```

---

### Phase TG3: Tavily HTTP Client + Registration (~30 min)

**Goal:** The Tavily search provider has a stub `_send_request()` that raises `NotImplementedError`. This phase implements real HTTP calls to the Tavily API and registers the web_search tool in the ToolGateway at app startup, completing the end-to-end tool execution path.

**Spec refs:** SPEC.md §12.4 (web search tool), §19.3 (rate limits: 30/hour for web_search)

**Depends on:** TG2
**Blocks:** Wave 12

**Deliverables:**
1. Real `_TavilyClient._send_request()` using `httpx.AsyncClient`
2. Proper error handling: API errors, timeouts, invalid API key
3. Response parsing: extract `results[]` with title, url, content fields
4. Registration in `wire_llm_pipeline()`: create WebSearchTool → DirectApiAdapter → register in ToolGateway
5. ToolGateway stored in app_state, accessible from tool_node

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/search_providers/tavily.py` | **MODIFY** | Real httpx calls to Tavily API |
| `src/noa/api/app.py` | **MODIFY** | Register WebSearchTool in ToolGateway at startup |
| `src/noa/api/app_state.py` | **MODIFY** | Add gateway getter/setter |
| `src/noa/orchestrator/nodes/tools.py` | **MODIFY** | Import gateway from app_state |
| `tests/unit/test_tg3_tavily.py` | **CREATE** | Tavily client + registration tests |

**Tests (~10):**
- TavilyClient sends POST to /search endpoint
- TavilyClient includes API key in request body
- TavilyClient parses results with title, url, content
- TavilyClient handles 401 (invalid key) gracefully
- TavilyClient handles 429 (rate limited) gracefully
- TavilyClient handles network timeout gracefully
- TavilyClient respects max_results parameter
- wire_llm_pipeline registers web_search tool when TAVILY_API_KEY is set
- wire_llm_pipeline skips web_search when no TAVILY_API_KEY
- End-to-end: ToolGateway dispatches web_search through DirectApiAdapter to Tavily

**Test gate:**
```bash
pytest tests/unit/test_tg3_tavily.py -v
```

---

## Wave 12: Google + Notion Tools

Wires real HTTP clients for Google Calendar, Gmail, and Notion APIs. The existing tool wrappers (`CalendarTool`, `GmailTool`, `NotionTool`) already exist with validation logic — this wave provides the `api_client` implementations they delegate to, adds OAuth token exchange for Google, and registers all three tools in the ToolGateway at startup.

---

### Phase GT1: Google OAuth Token Exchange + Storage (~30 min)

**Goal:** The `GoogleAuthClient` class exists but has no actual token exchange — `set_tokens()` must be called manually. This phase adds real HTTP token exchange (authorization code → access/refresh tokens), token refresh, and persistent storage of refresh tokens in the DB (encrypted column per §11.1).

**Spec refs:** SPEC.md §11.1 (Google OAuth2 refresh token → Postgres encrypted column), §11.2 (secrets never logged), §11.3 (refresh tokens rotate on use)

**Depends on:** TG3 (gateway infrastructure), CM1 (settings/credentials storage)
**Blocks:** GT2

**Deliverables:**
1. `GoogleAuthClient.exchange_code(code)` — POST to Google token endpoint, returns access+refresh tokens
2. `GoogleAuthClient.refresh_access_token()` — uses refresh token to get new access token
3. Token persistence: `google_refresh_token` column on `UserSettings` model
4. OAuth callback endpoint: `GET /auth/google/callback?code=...&state=...` exchanges code, stores tokens
5. OAuth initiation endpoint: `GET /auth/google/authorize` returns auth URL with combined scopes
6. Alembic migration for `google_refresh_token` column

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/google_auth.py` | **MODIFY** | Add exchange_code(), refresh_access_token() with real httpx calls |
| `src/noa/settings/models.py` | **MODIFY** | Add google_refresh_token column |
| `src/noa/api/v1/google_oauth.py` | **CREATE** | OAuth authorize + callback endpoints |
| `src/noa/api/app.py` | **MODIFY** | Mount google_oauth router |
| `alembic/versions/add_google_refresh_token.py` | **CREATE** | Migration adding column |
| `tests/unit/test_gt1_google_oauth.py` | **CREATE** | Google OAuth tests |

**Tests (~12):**
- exchange_code sends POST to token endpoint with correct params
- exchange_code returns access_token + refresh_token from response
- exchange_code raises on 400/401 error response
- exchange_code never logs token values (§11.2)
- refresh_access_token sends POST with refresh_token grant_type
- refresh_access_token updates access_token in-place
- refresh_access_token raises on invalid/expired refresh token
- /auth/google/authorize returns auth URL with calendar+gmail scopes
- /auth/google/callback exchanges code and stores refresh token
- /auth/google/callback rejects missing code parameter
- google_refresh_token column exists on UserSettings model
- GoogleAuthClient.is_authenticated reflects token state correctly

**Test gate:**
```bash
pytest tests/unit/test_gt1_google_oauth.py -v
```

---

### Phase GT2: Google Calendar + Gmail HTTP Clients (~30 min)

**Goal:** `CalendarTool` and `GmailTool` wrappers exist but need real `api_client` implementations that make actual HTTP calls to Google APIs. This phase creates `GoogleCalendarClient` and `GmailClient` — httpx-based async clients using OAuth2 bearer tokens from `GoogleAuthClient`.

**Spec refs:** SPEC.md §12.1 (Calendar API functions), §12.2 (Gmail API functions), §8.2 (external container egress)

**Depends on:** GT1 (OAuth token exchange)
**Blocks:** GT3 (only in dependency ordering; GT3 is independent work)

**Deliverables:**
1. `GoogleCalendarClient` — real httpx calls to Google Calendar API v3
2. `GmailClient` — real httpx calls to Gmail API v1
3. Both clients use `GoogleAuthClient` for bearer tokens and auto-refresh on 401
4. Registration functions in `registration.py` for calendar + gmail tools
5. Both tools registered in ToolGateway at startup when credentials are set

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/google_calendar_client.py` | **CREATE** | Real Calendar API v3 httpx client |
| `src/noa/tools/google_gmail_client.py` | **CREATE** | Real Gmail API v1 httpx client |
| `src/noa/tools/registration.py` | **MODIFY** | Add _register_calendar(), _register_gmail() |
| `tests/unit/test_gt2_google_clients.py` | **CREATE** | Calendar + Gmail client tests |

**Tests (~14):**
- GoogleCalendarClient.list_events sends GET to /calendars/primary/events
- GoogleCalendarClient.list_events passes timeMin/timeMax as RFC3339
- GoogleCalendarClient.create_event sends POST with event body
- GoogleCalendarClient.update_event sends PATCH to /events/{id}
- GoogleCalendarClient sets Authorization: Bearer header
- GoogleCalendarClient retries once on 401 after token refresh
- GoogleCalendarClient raises CalendarAPIError on 4xx/5xx
- GmailClient.search_emails sends GET to /messages with q= parameter
- GmailClient.read_email sends GET to /messages/{id}?format=full
- GmailClient.send_email sends POST to /messages/send with base64-encoded message
- GmailClient.draft_email sends POST to /drafts
- GmailClient raises GmailAPIError on 4xx/5xx
- _register_calendar registers tool when GOOGLE_CLIENT_ID + refresh token set
- _register_gmail registers tool when GOOGLE_CLIENT_ID + refresh token set

**Test gate:**
```bash
pytest tests/unit/test_gt2_google_clients.py -v
```

---

### Phase GT3: Notion HTTP Client + Registration (~30 min)

**Goal:** `NotionTool` exists with sanitization logic but needs a real `api_client` that makes HTTP calls to the Notion API. This phase creates `NotionClient` using the Notion integration token (simple bearer auth, no OAuth needed).

**Spec refs:** SPEC.md §12.3 (Notion tool functions), §11.1 (Notion integration token → macOS Keychain)

**Depends on:** TG3 (gateway infrastructure)
**Blocks:** None (GT4 is independent)

**Deliverables:**
1. `NotionClient` — real httpx calls to Notion API v1 (api.notion.com)
2. Search pages via POST /v1/search
3. Read page content via GET /v1/blocks/{id}/children (recursive)
4. Create page via POST /v1/pages
5. Update page via PATCH /v1/blocks/{id}/children
6. Registration function in `registration.py`
7. Notion-version header (2022-06-28) on all requests

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/notion_client.py` | **CREATE** | Real Notion API v1 httpx client |
| `src/noa/tools/registration.py` | **MODIFY** | Add _register_notion() |
| `tests/unit/test_gt3_notion_client.py` | **CREATE** | Notion client tests |

**Tests (~12):**
- NotionClient.search_pages sends POST to /v1/search with query
- NotionClient.search_pages returns list of {id, title, url}
- NotionClient.read_page sends GET to /v1/blocks/{id}/children
- NotionClient.read_page converts block results to markdown-like text
- NotionClient.create_page sends POST to /v1/pages with parent + properties
- NotionClient.create_page returns {id, url}
- NotionClient.update_page sends PATCH to /v1/blocks/{id}/children
- NotionClient sets Authorization: Bearer {token} header
- NotionClient sets Notion-Version: 2022-06-28 header
- NotionClient raises NotionAPIError on 401 (invalid token)
- NotionClient raises NotionAPIError on 404 (page not found)
- _register_notion registers tool when NOTION_TOKEN is set

**Test gate:**
```bash
pytest tests/unit/test_gt3_notion_client.py -v
```

---

### Phase GT4: McpRemoteAdapter Stub (~10 min)

**Goal:** Phase 2 (multi-machine deployment) will need MCP adapters that communicate over a network transport (HTTP+SSE or WebSocket) to MCP servers running in isolated containers. This phase creates an interface stub so the adapter protocol is defined, but no implementation is needed yet.

**Spec refs:** SPEC.md §8.2 (external container isolation), §20 (network architecture)

**Depends on:** TG2 (DirectApiAdapter pattern)
**Blocks:** None (Phase 2 only)

**Deliverables:**
1. `McpRemoteAdapter` class with `execute()` signature matching `DirectApiAdapter`
2. `execute()` raises `NotImplementedError("Phase 2: MCP remote transport")`
3. Configuration dataclass for remote MCP connection params (url, auth)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/adapters/mcp_remote.py` | **CREATE** | McpRemoteAdapter stub |
| `tests/unit/test_gt4_mcp_remote.py` | **CREATE** | Stub tests |

**Tests (~4):**
- McpRemoteAdapter has execute(request) method signature
- McpRemoteAdapter.execute raises NotImplementedError
- McpRemoteConfig dataclass has url, auth_token fields
- McpRemoteAdapter accepts McpRemoteConfig in constructor

**Test gate:**
```bash
pytest tests/unit/test_gt4_mcp_remote.py -v
```

---

## Wave 13: MVP Completion

Closes all remaining blockers to a working, testable end-to-end system. AuthService becomes real (DB-backed), memory persists across restarts, every tool call is audited and telemetry-persisted, per-tool permissions are enforced, Docker Compose is hardened, and the LangGraph orchestrator gets per-node model routing and conditional edges for cost/latency optimization. The web frontend is already complete (App.tsx + React Router + Tailwind + shadcn/ui) — no frontend work needed.

---

### Phase MR1: Real Auth + First-Run Registration (~30 min)

**Goal:** Three auth endpoints use `_mock_session()` (an `AsyncMock`) instead of a real DB session, so login/refresh/logout do nothing to the database. `AuthService` has three stub methods that return `None` unconditionally. This phase replaces the mock with a real `get_db_session` dependency, implements the three DB query methods, adds a `register()` method, and exposes `POST /api/v1/auth/register`. Also fixes the logout JTI/session-ID mismatch by adding a `sid` claim to the access token.

**Spec refs:** SPEC.md §5.1, §5.2, §5.3, §5.4

**Depends on:** None (within this wave)
**Blocks:** MR3, MR4, MR5, MR7

**Deliverables:**
1. `_mock_session()` removed from `api/v1/auth.py`; all endpoints use `Depends(get_db_session)` via `app_state.get_session_factory()`
2. `AuthService._get_user_by_email()` — real `select(User).where(User.email == email)`
3. `AuthService._get_session_by_refresh_token()` — `select(AuthSession).where(AuthSession.refresh_token_hash == self._hash_token(token))`
4. `AuthService._get_session_by_id()` — `select(AuthSession).where(AuthSession.id == session_id)`
5. `AuthService.register()` — validates no duplicate email, calls `hash_password()`, inserts `User` row
6. `POST /api/v1/auth/register` — public endpoint (no auth required)
7. Logout fix: `create_access_token()` gets `session_id` param → emits `sid` claim; logout reads `payload["sid"]`

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/auth/jwt.py` | **EDIT** | Add `session_id` param to `create_access_token()`, emit as `sid` claim |
| `src/noa/auth/service.py` | **EDIT** | Implement 3 stub methods with `select()` queries; add `register()` |
| `src/noa/api/v1/auth.py` | **EDIT** | Remove `_mock_session()`; use `Depends(get_db_session)`; add `POST /register`; logout reads `sid` |
| `tests/unit/test_mr1_auth.py` | **CREATE** | Auth + registration tests |

**Tests (~14):**
- register() calls session.add() with User whose password_hash != plain password
- register() rejects duplicate email with AuthError
- POST /register returns 201 with user_id
- POST /register rejects duplicate returns 409
- _get_user_by_email returns None for missing user
- _get_user_by_email returns user for known email
- _get_session_by_refresh_token returns None when not found
- _get_session_by_refresh_token looks up by hashed token
- _get_session_by_id returns None for unknown id
- _get_session_by_id returns session for known id
- create_access_token with session_id includes "sid" claim
- logout reads payload["sid"] not payload["jti"]
- login endpoint uses real db session (not _mock_session)
- register endpoint does not require auth

**Test gate:**
```bash
pytest tests/unit/test_mr1_auth.py -v
```

---

### Phase MR2: Memory Persistence (~25 min)

**Goal:** `MemoryStore` keeps all facts in a Python dict that vanishes on container restart. The `private-data` Docker volume at `/data` is already mounted but nothing writes to it. This phase adds JSON-file-per-fact persistence: write on `store()`, remove on `delete()`, rewrite on `update_status()`, load all `.json` files on `__init__`.

**Spec refs:** SPEC.md §13.2, §9.1

**Depends on:** None (within this wave)
**Blocks:** MR7

**Deliverables:**
1. `MemoryStore.__init__(data_dir: Path | None = None)` — loads all `*.json` files at startup
2. `store()` writes `{data_dir}/{fact_id}.json`
3. `delete()` removes the file
4. `update_status()` rewrites the file
5. `handlers.py` singleton uses `data_dir=Path("/data/memory")`
6. No `data_dir` → pure in-memory (backward compat for existing tests)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/private_worker/memory_store.py` | **EDIT** | Add `data_dir` param; `_load_from_disk()`, `_persist()`, `_remove_file()` helpers |
| `src/noa/private_worker/handlers.py` | **EDIT** | `_memory_store = MemoryStore(data_dir=Path("/data/memory"))` |
| `tests/unit/test_mr2_memory_persistence.py` | **CREATE** | Persistence tests using `tmp_path` fixture |

**Tests (~12):**
- init without data_dir works (in-memory only)
- store writes JSON file to data_dir
- stored file contains correct fact data
- delete removes JSON file
- update_status rewrites file with new status
- load from disk on init restores facts
- load ignores invalid JSON files
- creates data_dir if missing
- deduplication works after reload
- list_all includes loaded facts
- recall works after reload
- handlers singleton uses /data/memory path

**Test gate:**
```bash
pytest tests/unit/test_mr2_memory_persistence.py -v
```

---

### Phase MR3: Tool Call Audit Trail (~25 min)

**Goal:** Every tool call through `ToolGateway.dispatch()` should produce an `AuditLog` entry. Currently `ToolGateway` has zero imports from `noa.audit`. This phase adds audit logging via an async callback pattern — keeps the gateway DB-free and highly testable.

**Spec refs:** SPEC.md §28.1, §28.2, §2.1

**Depends on:** MR1 (needs real user context)
**Blocks:** MR7

**Deliverables:**
1. `ToolRequest` — add `user_id`, `session_id`, `trace_id` optional UUID fields
2. `ToolGateway.__init__` — add optional `audit_callback` parameter
3. `dispatch()` calls callback after execution on every path (ok, error, cached, rate_limited, dry_run)
4. Callback skipped if `request.user_id` is None; errors logged but don't fail dispatch
5. `AuditService.create_entry_async()` — async variant accepting `AsyncSession`
6. `app.py` wires audit callback closure in `wire_llm_pipeline()`

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/gateway.py` | **EDIT** | Add user context to `ToolRequest`; add `audit_callback` to gateway; call after dispatch |
| `src/noa/audit/service.py` | **EDIT** | Add `async create_entry_async()` |
| `src/noa/api/app.py` | **EDIT** | Wire audit callback closure in `wire_llm_pipeline()` |
| `tests/unit/test_mr3_tool_audit.py` | **CREATE** | Audit trail tests |

**Tests (~12):**
- ToolRequest has optional user_id, session_id, trace_id fields
- ToolRequest defaults are None
- dispatch calls audit callback on success
- dispatch calls audit callback on error
- dispatch calls audit callback on rate limit
- dispatch skips audit when no callback
- dispatch skips audit when no user_id
- create_entry_async writes to session
- create_entry_async chains hash
- create_entry_async flushes not commits
- dry_run calls audit with dry_run status
- cached response calls audit with cached status

**Test gate:**
```bash
pytest tests/unit/test_mr3_tool_audit.py -v
```

---

### Phase MR4: Tool Call Telemetry to DB (~30 min)

**Goal:** `ToolGateway` records telemetry in `self.telemetry: list[dict]` — an in-process list lost on restart. This phase introduces a `ToolCallLog` DB model, replaces the in-memory list with DB persistence (with fallback), and adds a `/health/tools` endpoint for per-tool statistics.

**Spec refs:** SPEC.md §28.4, §28.5, §19.3

**Depends on:** MR1 (session factory pattern)
**Blocks:** MR7

**Deliverables:**
1. `ToolCallLog` model: id (UUID), tool, function, latency_ms, status, cached, timestamp, user_id
2. Alembic migration `003_tool_call_log.py`
3. `ToolGateway` gets `session_factory` kwarg; persists to DB when set, fallback to list
4. `GET /health/tools` — per-tool p50/p95 latency, error_rate, call_count (last 24h)
5. Existing `test_tg1_gateway.py` still passes (no factory = list mode)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/db/models/tool_call_log.py` | **CREATE** | `ToolCallLog` SQLAlchemy model |
| `alembic/versions/003_tool_call_log.py` | **CREATE** | Migration |
| `src/noa/tools/gateway.py` | **EDIT** | Add `session_factory` to init; DB-backed telemetry with list fallback |
| `src/noa/api/v1/health.py` | **EDIT** | Add `GET /health/tools` endpoint |
| `src/noa/api/app.py` | **EDIT** | Pass `session_factory` to `ToolGateway()` |
| `tests/unit/test_mr4_tool_telemetry.py` | **CREATE** | Telemetry tests |

**Tests (~13):**
- ToolCallLog instantiation with required fields
- ToolCallLog timestamp auto-set
- Migration creates tool_call_logs table
- Telemetry fallback to list without factory
- session_factory stored in init
- DB write called on dispatch
- DB error does not fail dispatch
- /health/tools returns 200
- /health/tools returns per-tool stats
- /health/tools shows error_rate
- /health/tools shows latency percentiles
- /health/tools empty when no calls
- Existing gateway tests still pass

**Test gate:**
```bash
pytest tests/unit/test_mr4_tool_telemetry.py -v
```

---

### Phase MR5: Capability-Based Tool Permissions (~30 min)

**Goal:** Currently any authenticated user can invoke any registered tool. This phase adds a per-tool capability system (`search.read`, `calendar.write`, `gmail.send`, etc.) with DB-backed grants, hooks it into `dispatch()`, and exposes enable/disable endpoints per SPEC §34.

**Spec refs:** SPEC.md §19, §34, §2.1

**Depends on:** MR1 (permissions are per-user)
**Blocks:** MR7

**Deliverables:**
1. `ToolCapability` model: id, user_id, tool_name, capability, granted_at, granted_by
2. Alembic migration `004_tool_capabilities.py`
3. `TOOL_CAPABILITIES` static dict mapping tool names to required capabilities
4. `CapabilityChecker` protocol + `DbCapabilityChecker` implementation
5. Capability check in `dispatch()` between allowlist and dry-run
6. `POST /api/v1/tools/{name}/enable` and `DELETE /api/v1/tools/{name}` endpoints
7. No checker or no user_id → dispatch proceeds (backward compat)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/db/models/tool_capability.py` | **CREATE** | `ToolCapability` model |
| `alembic/versions/004_tool_capabilities.py` | **CREATE** | Migration with index on (user_id, tool_name) |
| `src/noa/tools/capabilities.py` | **CREATE** | `TOOL_CAPABILITIES` dict, `CapabilityChecker` protocol, `DbCapabilityChecker` |
| `src/noa/tools/gateway.py` | **EDIT** | Add capability check in `dispatch()` |
| `src/noa/api/v1/tools.py` | **CREATE** | Enable/disable endpoints |
| `src/noa/api/app.py` | **EDIT** | Register tools router, wire checker |
| `tests/unit/test_mr5_tool_permissions.py` | **CREATE** | Permission tests |

**Tests (~14):**
- ToolCapability model instantiation
- ToolCapability required fields
- All registered tools have capabilities in TOOL_CAPABILITIES
- Capability strings use dot notation (r"^\w+\.\w+$")
- dispatch allowed when checker not set
- dispatch allowed when user_id None
- dispatch blocked when capability denied
- dispatch allowed when capability granted
- capability check before dry_run (denied even in dry_run)
- POST /tools/{name}/enable exists (non-404)
- POST /tools/{name}/enable requires auth
- POST /tools/{name}/enable grants capability
- DELETE /tools/{name} exists
- DELETE /tools/{name} revokes capability

**Test gate:**
```bash
pytest tests/unit/test_mr5_tool_permissions.py -v
```

---

### Phase MR6: Docker Compose Hardening (~20 min)

**Goal:** `docker-compose.yml` lacks healthchecks for `noa-api` and `private-worker`, has no resource limits, and `noa-api` is missing container hardening flags. This phase brings the compose file up to SPEC §30 requirements.

**Spec refs:** SPEC.md §30, §8.1, §20.1

**Depends on:** None (within this wave)
**Blocks:** MR7

**Deliverables:**
1. `noa-api` healthcheck: `curl -f http://localhost:8000/health` (interval 10s, timeout 5s, retries 5, start_period 30s)
2. `private-worker` healthcheck: `curl -f http://localhost:8001/health` (interval 10s, timeout 5s, retries 5)
3. Resource limits: noa-api 2CPU/2GB, external-worker 2CPU/4GB, postgres 1CPU/2GB
4. `noa-api` hardening: `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `tmpfs: [/tmp:size=256M]`
5. `noa-api` `depends_on`: add `private-worker: condition: service_healthy`

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | **EDIT** | Healthchecks, resource limits, hardening, depends_on |
| `tests/unit/test_mr6_compose_hardening.py` | **CREATE** | YAML-parsing tests |

**Tests (~10):**
- noa-api has healthcheck defined
- noa-api healthcheck uses curl and /health
- private-worker has healthcheck defined
- noa-api has CPU limit (2.0)
- noa-api has memory limit (2g)
- external-worker has memory limit (4g)
- postgres has resource limits
- noa-api is read_only
- noa-api drops all caps
- noa-api waits for private-worker healthy

**Test gate:**
```bash
pytest tests/unit/test_mr6_compose_hardening.py -v
```

---

### Phase MR7: Integration Smoke Test (~25 min)

**Goal:** End-to-end test validating the full auth flow (register → login → authenticated access → refresh → logout) against a fully wired ASGI app with SQLite in-memory — no Docker required.

**Spec refs:** SPEC.md §25.1, §28.1, §5.3

**Depends on:** MR1, MR2, MR3, MR4, MR5, MR6, MR8, MR9
**Blocks:** None

**Deliverables:**
1. `tests/integration/test_mr7_smoke.py` — pytest tests using `httpx.AsyncClient` with ASGI transport
2. `tools/smoke_test.sh` — optional Docker-based end-to-end script

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `tests/integration/test_mr7_smoke.py` | **CREATE** | Full integration smoke test |
| `tools/smoke_test.sh` | **CREATE** | Optional Docker smoke script |

**Tests (~10):**
- POST /register creates new user → 201
- POST /login returns access_token and refresh_token
- POST /login with wrong password → 401
- GET /health returns 200 (no auth)
- GET /settings without token → 401
- GET /settings with valid token → 200
- POST /refresh rotates token pair
- POST /logout invalidates session
- GET /health/tools returns 200
- POST /tools/{name}/enable with valid token → 200

**Test gate:**
```bash
pytest tests/integration/test_mr7_smoke.py -v
```

---

### Phase MR8: Per-Node Model Routing (~25 min)

**Goal:** The LangGraph nodes currently use a single model selected by `router_node` (hardcoded `_EXTERNAL_MODEL = "anthropic/claude-haiku"`). Different nodes have different intelligence requirements: the router just classifies (cheap model fine), the agent does reasoning (needs frontier model), the responder just formats (no LLM needed). This phase adds a `ModelConfig` so each node can specify its preferred model, cutting token costs ~40-60%.

**Spec refs:** SPEC.md §14.4, §2.1

**Depends on:** None (within this wave)
**Blocks:** MR7

**Deliverables:**
1. `ModelConfig` dataclass mapping node names to model identifiers with defaults
2. `AgentState` gets `model_config: dict[str, str]` field
3. `router_node` returns `model_config` in state update based on privacy mode
4. `agent_node` reads `model_config["agent"]` (fallback to `selected_model` for backward compat)
5. Default: `{"router": "none", "agent": "anthropic/claude-sonnet-4-20250514", "responder": "none"}`
6. Private mode: `{"agent": "ollama/llama3.1"}` — privacy enforcement still in `ProviderRouter.select()`

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/orchestrator/model_config.py` | **CREATE** | `ModelConfig` dataclass with per-node model defaults |
| `src/noa/orchestrator/state.py` | **EDIT** | Add `model_config: dict[str, str]` to `AgentState` |
| `src/noa/orchestrator/nodes/router.py` | **EDIT** | Return `model_config` in state update |
| `src/noa/orchestrator/nodes/agent.py` | **EDIT** | Read `model_config["agent"]` with fallback to `selected_model` |
| `tests/unit/test_mr8_model_routing.py` | **CREATE** | Model routing tests |

**Tests (~10):**
- ModelConfig has correct default values
- ModelConfig private mode returns ollama for agent
- router_node returns model_config in state update
- agent_node uses model_config["agent"] when present
- agent_node falls back to selected_model when model_config absent
- model_config respects privacy_mode=private override
- ModelConfig.from_settings reads user preferences
- Per-node model can be overridden via ChatRequest
- router and responder have model="none" (no LLM cost)
- Full graph run with model_config passes agent the correct model

**Test gate:**
```bash
pytest tests/unit/test_mr8_model_routing.py -v
```

---

### Phase MR9: Conditional Graph Edges (~25 min)

**Goal:** The graph topology is fixed linear: `router → agent → tools → responder`. Every request executes the tool node even when the agent returns no tool calls. This phase adds conditional edges so the graph skips tools when unnecessary and supports multi-turn tool use with a loop cap, reducing latency and cost.

**Spec refs:** SPEC.md §2.1 (topology is fixed, but edges can be conditional)

**Depends on:** None (within this wave)
**Blocks:** MR7

**Deliverables:**
1. Conditional edge: `agent → tools` (if tool_calls) or `agent → responder` (if no tool_calls)
2. Conditional edge: `tools → agent` (for follow-up) or `tools → responder` (if done)
3. `MAX_TOOL_ROUNDS = 3` — caps `tools → agent` loop (§2.1 cost limits)
4. `AgentState` gets `tool_rounds: int` counter
5. All existing tests pass — same 4 nodes, smarter routing

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/orchestrator/graph.py` | **EDIT** | Replace fixed edges with `add_conditional_edges()` + routing functions |
| `src/noa/orchestrator/state.py` | **EDIT** | Add `tool_rounds: int` field |
| `src/noa/orchestrator/nodes/tools.py` | **EDIT** | Increment `tool_rounds` in return dict |
| `tests/unit/test_mr9_conditional_edges.py` | **CREATE** | Conditional edge tests |

**Tests (~10):**
- Graph compiles without error
- Graph has 4 nodes
- No tool_calls → skips tools, goes agent → responder
- With tool_calls → goes agent → tools → agent (loop)
- tool_rounds incremented after each tools pass
- MAX_TOOL_ROUNDS=3 enforced — tools → responder after 3 rounds
- Pure text response produces correct final response
- Tool-using response produces correct tool_results
- Backward compat: existing graph tests still pass
- tool_rounds defaults to 0

**Test gate:**
```bash
pytest tests/unit/test_mr9_conditional_edges.py -v
```

---

## Dependency Graph

```
Wave 1: Foundation
  F1 ──► F2 ──► F3 ──► F4

Wave 2: Orchestration
  F2,F3 ──► OC1 ──► OC2
  F2 ──► OC3
  F4,OC1,OC3 ──► OC4

Wave 3: Domain Workers
  F1,OC1 ──► DW1 ──► DW3
  F1,OC1 ──► DW2 ──► DW3
  OC1,DW1,DW2 ──► DW4

Wave 4: Tools
  DW1 ──► TI1
  DW2 ──► TI2 ──► TI3
  DW2 ──► TI4
  DW2 ──► TI5
  OC4,TI1-TI5 ──► TI6

Wave 5: Advanced
  OC1,OC3 ──► AB1
  OC1,DW1,DW2 ──► AB2
  OC4 ──► AB3 ──► AB4
  DW2 ──► AB5

Wave 6: Web Client
  OC2 ──► WC1 ──► WC2, WC3, WC4, WC5, WC6, WC7

Wave 8: Credential Management
  F2,F4,WM3 ──► CM1 ──► CM2

Wave 9: LLM Provider Wiring
  CM1,CM2 ──► LP1 (Anthropic)
  CM1,CM2 ──► LP2 (OpenAI)
  CM1,CM2 ──► LP3 (Google AI)
  CM1,CM2 ──► LP4 (Ollama)
  LP1,LP2,LP3,LP4 ──► LP5 (ProviderRouter)

Wave 10: End-to-End Chat Pipeline
  LP5 ──► CP1 (invoke_llm wiring)
  CP1 ──► CP2 (OrchestratorRunner)
  CP2 ──► CP3 (Chat Endpoint)
  CP3 ──► CP4 (App Startup)

Wave 11: Tool Gateway + Tavily
  CP4,TI6 ──► TG1 (ToolGateway)
  TG1 ──► TG2 (DirectApiAdapter)
  TG2 ──► TG3 (Tavily HTTP + Registration)

Wave 12: Google + Notion Tools
  TG3,CM1 ──► GT1 (Google OAuth)
  GT1 ──► GT2 (Calendar + Gmail HTTP Clients)
  TG3 ──► GT3 (Notion HTTP Client)
  TG2 ──► GT4 (McpRemoteAdapter Stub)

Wave 13: MVP Completion
  MR1 (Real Auth)        ──┬── MR3 (Audit Trail)  ──┐
                            ├── MR4 (Telemetry DB)  ──┤
                            └── MR5 (Permissions)   ──┤
  MR2 (Memory Persist)   ─────────────────────────────┼── MR7 (Smoke Test)
  MR6 (Docker Hardening) ─────────────────────────────┤
  MR8 (Model Routing)    ─────────────────────────────┤
  MR9 (Conditional Edges) ────────────────────────────┘

Wave 14: Operations & Go-Live
  OP1 (Backup) ──┐
  OP2 (Logs)     ├── OP5 (Runbook)
  OP3 (Health)   ┤
  OP4 (Postgres) ┘
```

---

## Wave 14: Operations & Go-Live

Delivers operational infrastructure for running Noa reliably in production: automated backups, log management, health monitoring, database maintenance, and a runbook for the operator. After this wave, the system is ready for daily use.

**Spec refs:** §10.5, §28.2, §28.7, §30, §31

**Depends on:** Wave 13 (all MVP phases complete)

---

### Phase OP1: Backup Infrastructure (~30 min)

**Goal:** Implement automated Postgres backup with encryption and restore verification, per SPEC.md §10.5.

**Spec refs:** §10.5 (Backup Strategy)

**Depends on:** Wave 13 complete
**Blocks:** OP5

**Deliverables:**
1. `pg_dump` backup script with GPG encryption to local storage
2. Restore verification script that validates backup integrity
3. Backup scheduling via cron-compatible entrypoint (daily)
4. Docker volume for encrypted backups
5. Private domain data backup to separate encrypted volume

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `scripts/backup.sh` | **CREATE** | pg_dump → gzip → GPG encrypt → `/backups/` volume |
| `scripts/restore.sh` | **CREATE** | Decrypt → decompress → pg_restore with verification SELECT |
| `scripts/backup_private.sh` | **CREATE** | Tar + encrypt private-data volume to `/backups/` |
| `docker-compose.yml` | **MODIFY** | Add `backups` named volume, backup sidecar service |
| `docker/backup/Dockerfile` | **CREATE** | Alpine + pg_client + gpg + cron |
| `docker/backup/crontab` | **CREATE** | Daily 02:00 pg_dump, weekly 03:00 restore test |

**Tests (~6):**
- Backup script creates encrypted dump file
- Encrypted file is valid GPG (header check)
- Restore script recovers data correctly
- Backup fails gracefully on DB unreachable
- Private data backup creates encrypted archive
- Crontab syntax is valid

**Test gate:**
```bash
pytest tests/unit/test_backup.py -v
```

---

### Phase OP2: Log Persistence + Rotation (~25 min)

**Goal:** Configure Docker log drivers for persistence, schedule audit log retention purge (90-day default per §28.7), and ensure structured JSON logging across all services.

**Spec refs:** §28.3 (Structured Logging), §28.7 (Data Retention)

**Depends on:** Wave 13 complete
**Blocks:** OP5

**Deliverables:**
1. Docker log driver config (json-file with rotation) for all services
2. Scheduled audit log purge task (calls existing `purge_expired()`)
3. Tool transcript cleanup after session ends
4. Structured JSON log formatter for all Python services

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | **MODIFY** | Add `logging:` config with json-file driver, max-size 50m, max-file 5 |
| `src/noa/logging_config.py` | **CREATE** | Structured JSON formatter with trace_id, no PII |
| `src/noa/maintenance/retention.py` | **CREATE** | Scheduled purge task: audit logs (90d), tool transcripts (session end) |
| `src/noa/api/app.py` | **MODIFY** | Register retention task in lifespan (daily schedule) |

**Tests (~5):**
- JSON log formatter produces valid structured output
- No PII/secrets in formatted log output
- Retention purge deletes entries older than 90 days
- Retention purge preserves entries within retention window
- Tool transcript cleanup removes session-scoped data

**Test gate:**
```bash
pytest tests/unit/test_log_rotation.py tests/unit/test_retention.py -v
```

---

### Phase OP3: Health Checks + Compose Fixes (~20 min)

**Goal:** Add missing health checks (external-worker), add missing resource limits (private-worker), and ensure all containers have proper restart policies per §30 and §31.

**Spec refs:** §28.5 (Health Endpoints), §30 (Resource Management), §31 (Failure Handling)

**Depends on:** Wave 13 complete
**Blocks:** OP5

**Deliverables:**
1. External-worker health check in docker-compose.yml
2. Private-worker resource limits (remaining CPU, up to 32 GB RAM per spec)
3. Readiness probe for all services (DB dependency check where applicable)
4. Service dependency chain verified (`depends_on: service_healthy`)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | **MODIFY** | Add external-worker healthcheck, private-worker resource limits |
| `src/noa/external_worker/app.py` | **MODIFY** | Enhance `/health` with readiness info |

**Tests (~4):**
- Docker compose config validates (docker compose config)
- All services have healthcheck defined
- All services have resource limits defined
- External worker health endpoint returns proper status

**Test gate:**
```bash
pytest tests/unit/test_compose_health.py -v
```

---

### Phase OP4: Postgres Maintenance (~20 min)

**Goal:** Implement database maintenance scheduling (VACUUM/ANALYZE), connection pool tuning, and index maintenance per §30.

**Spec refs:** §30 (Resource Management), §10.4 (Database)

**Depends on:** Wave 13 complete
**Blocks:** OP5

**Deliverables:**
1. Connection pool tuning (pool_size, max_overflow, pool_recycle)
2. Scheduled VACUUM ANALYZE via maintenance task
3. Index health check query
4. Connection pool monitoring endpoint

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/db/engine.py` | **MODIFY** | Add pool_size=10, max_overflow=20, pool_recycle=1800 |
| `src/noa/maintenance/db_maintenance.py` | **CREATE** | VACUUM ANALYZE scheduler, index bloat check |
| `src/noa/api/v1/health.py` | **MODIFY** | Add pool stats to /health/metrics |
| `src/noa/api/app.py` | **MODIFY** | Register DB maintenance in lifespan |

**Tests (~5):**
- Engine creates with correct pool parameters
- VACUUM ANALYZE executes without error
- Index bloat check returns valid stats
- Pool stats endpoint returns connection counts
- Pool recycle works (connections older than threshold are replaced)

**Test gate:**
```bash
pytest tests/unit/test_db_maintenance.py -v
```

---

### Phase OP5: Operational Runbook (~20 min)

**Goal:** Create a comprehensive operational runbook covering pre-flight checks, failure recovery, capacity planning, and daily operations.

**Spec refs:** §31 (Failure Handling), §10.5 (Backup), §28 (Logging)

**Depends on:** OP1, OP2, OP3, OP4
**Blocks:** None (final phase)

**Deliverables:**
1. Pre-flight checklist for initial deployment
2. Daily operations guide (monitoring, backup verification)
3. Failure recovery procedures (per §31 scenarios)
4. Capacity planning guidelines
5. Troubleshooting guide for common issues

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `docs/RUNBOOK.md` | **CREATE** | Full operational runbook |
| `scripts/preflight.sh` | **CREATE** | Automated pre-flight checks (env vars, volumes, connectivity) |

**Tests (~3):**
- Preflight script exits 0 on valid config
- Preflight script exits 1 on missing required env vars
- Preflight script validates Docker prerequisites

**Test gate:**
```bash
pytest tests/unit/test_preflight.py -v
```

---

_Nach jeder abgeschlossenen Phase wird hier ein kurzer Bericht ergänzt: was lief gut, was nicht, welche Entscheidungen getroffen wurden, und was für spätere Phasen relevant ist._

### Template

```markdown
### Phase {ID}: {Title} — Report

**Dauer:** {Actual} (geschätzt: {Est.})
**Status:** Complete | Partial | Blocked

**Was wurde geliefert:**
- {Deliverable 1}
- {Deliverable 2}

**Entscheidungen:**
- {Entscheidung + Begründung}

**Probleme & Lösungen:**
- {Problem → Lösung}

**Learnings:**
- {Was wir für spätere Phasen mitnehmen}

**Abweichungen vom Plan:**
- {Was anders lief als geplant, und warum}
```

---

## Wave 14B: Quality & Cleanup

Comprehensive quality wave addressing all 49 findings from the full codebase audit (FINDINGS.md, 2026-03-07). Organized in priority order: fix crashes first, then security, then correctness, then polish. All finding IDs (C1, H2, M3, UI-C1, A1, etc.) reference FINDINGS.md sections.

**Dependency graph:**
```
QC1 (Runtime Fixes) ─┬─→ QC4 (Domain Isolation)
                      └─→ QC8 (Architecture)
QC2 (Security) ──────── independent
QC3 (Error Handling) ─→ QC8 (Architecture)
QC5 (Database) ──────── independent
QC6 (Frontend Critical) → QC7 (Frontend Polish)
QC4, QC8 are the heaviest phases; all others can run in parallel where staffing allows.
```

---

### Phase QC1: Critical Runtime Fixes (~30 min)

**Goal:** Fix all crash-causing bugs so the core pipeline can execute without runtime errors.

**Findings:** C1, C4, C5, A3, H3

**Deliverables:**
1. **C1** — Fix async/sync mismatch in tool dispatch: make `tool_node` async and `await` the executor result, or switch to synchronous dispatch. Ensure `_dispatch_registry()` and `_dispatch_gateway()` return `dict`, not `Future`.
2. **C4** — Create migration `005_schema_drift_fix.py` adding `Approval.domain` column and `UsageStats.task_id` column.
3. **C5** — Remove `or ""` fallback from JWT secret in `middleware.py:33`. Raise `RuntimeError` at startup if `secret_key` is unset.
4. **A3** — Initialize all `AgentState` fields (`model_config`, `tool_rounds`) in `OrchestratorRunner.initial_state`.
5. **H3** — Replace `AuditService.__new__(AuditService)` with proper `AuditService()` instantiation in `app.py:80`.

**Files:**

| File | Action | Findings |
|------|--------|----------|
| `src/noa/orchestrator/nodes/tools.py` | **MODIFY** | C1: fix async dispatch, return dict not Future |
| `alembic/versions/005_schema_drift_fix.py` | **CREATE** | C4: add missing `domain`, `task_id` columns |
| `src/noa/auth/middleware.py` | **MODIFY** | C5: remove empty secret fallback, fail-fast |
| `src/noa/orchestrator/runner.py` | **MODIFY** | A3: initialize all AgentState fields |
| `src/noa/api/app.py` | **MODIFY** | H3: proper AuditService instantiation |

---

### Phase QC2: Security Hardening (~45 min)

**Goal:** Close all identified security vulnerabilities before any user-facing deployment.

**Findings:** C3, C6, H6, H7, H10, M2, M4

**Deliverables:**
1. **C3** — Add `SELECT ... FOR UPDATE` (pessimistic lock) when reading the latest audit entry before inserting a new one, in both sync and async `create_entry()`.
2. **C6** — Move access/refresh tokens from `localStorage` to httpOnly, Secure, SameSite=Strict cookies. API sets cookies on login response; frontend sends credentials via `fetch(..., {credentials: "include"})`.
3. **H6** — Add email address validation in `gmail.py:send_email()`: parse format, reject multi-recipient injection, reject empty/malformed addresses.
4. **H7** — Change `TOOL_CAPABILITIES` default from allow to deny. Tools not explicitly registered are blocked.
5. **H10** — Replace regex-based HTML sanitization in `notion.py` with `nh3` (or `bleach`). Strip all dangerous attributes and tags.
6. **M2** — Add CSRF token generation and validation for state-changing requests. Tighten CORS from `*` to configured origins.
7. **M4** — Add Content-Security-Policy headers to API responses (or Nginx config for production).

**Files:**

| File | Action | Findings |
|------|--------|----------|
| `src/noa/audit/service.py` | **MODIFY** | C3: pessimistic locking on hash chain |
| `web/src/auth/tokens.ts` | **MODIFY** | C6: remove localStorage, use cookies |
| `web/src/api/client.ts` | **MODIFY** | C6: add `credentials: "include"` |
| `src/noa/auth/middleware.py` | **MODIFY** | C6: set httpOnly cookies on login |
| `src/noa/tools/gmail.py` | **MODIFY** | H6: validate email recipients |
| `src/noa/tools/capabilities.py` | **MODIFY** | H7: default deny |
| `src/noa/tools/notion.py` | **MODIFY** | H10: use nh3 for HTML sanitization |
| `src/noa/api/app.py` | **MODIFY** | M2: CSRF + CORS tightening, M4: CSP headers |
| `pyproject.toml` | **MODIFY** | Add nh3 dependency |

---

### Phase QC3: Error Handling & Observability (~30 min)

**Goal:** Replace all silent error swallowing with specific exception handling, structured logging, and proper error responses.

**Findings:** H4, H5, M8, M11, M13

**Deliverables:**
1. **H4** — Remove `commit()` from `SettingsRepository.upsert()`. Let service/endpoint layer control transaction boundaries.
2. **H5** — Replace bare `except Exception: pass` blocks across the codebase (`app.py`, `chat.py`, `cost.py`, `health.py`, etc. — at least 15 locations) with specific exception types, structured logging with `trace_id`, and appropriate error responses.
3. **M8** — Fix cost endpoint to return HTTP 500 on database errors instead of HTTP 200 with empty data.
4. **M11** — Create a typed `AuthUser` dataclass. Parse user identity once in `require_auth`, pass structured object to all endpoints. Eliminate the three different `user.get("user_id", user.get("sub", ""))` patterns.
5. **M13** — Add `check=True` to backup subprocess call. Filter environment variables before passing to subprocess (whitelist only needed vars).

**Files:**

| File | Action | Findings |
|------|--------|----------|
| `src/noa/settings/repository.py` | **MODIFY** | H4: remove commit() |
| `src/noa/api/app.py` | **MODIFY** | H5: replace bare excepts |
| `src/noa/api/v1/chat.py` | **MODIFY** | H5, M11: specific excepts + AuthUser |
| `src/noa/api/v1/cost.py` | **MODIFY** | H5, M8, M11: excepts + 500 on error + AuthUser |
| `src/noa/api/v1/settings.py` | **MODIFY** | H5, M11: specific excepts + AuthUser |
| `src/noa/maintenance/backup.py` | **MODIFY** | M13: check=True + env whitelist |
| `src/noa/auth/middleware.py` | **MODIFY** | M11: add AuthUser dataclass + parse once |

---

### Phase QC4: Domain Isolation & Worker Wiring (~45 min)

**Goal:** Enforce dual-domain separation per SPEC.md and make workers functional with real endpoints.

**Findings:** C2, H1, H9

**Deliverables:**
1. **C2** — Move `OllamaClient` from `noa.private_worker.ollama_client` to a shared `noa.llm.providers` module. Move `MAX_N_RESULTS` to `noa.constants`. Remove all cross-domain imports between `external_worker` and `private_worker`.
2. **H1** — Wire real endpoints into both workers:
   - External worker: `POST /v1/complete` endpoint using `ProviderRouter`
   - Private worker: `POST /rpc` endpoint dispatching to memory/DLP handlers
3. **H9** — Add synthetic `"id": uuid.uuid4().hex` to Google AI tool call parser so downstream code can match results.

**Files:**

| File | Action | Findings |
|------|--------|----------|
| `src/noa/llm/providers/__init__.py` | **CREATE** | C2: shared provider module |
| `src/noa/constants.py` | **CREATE** | C2: shared constants (MAX_N_RESULTS) |
| `src/noa/external_worker/llm/router.py` | **MODIFY** | C2: import from shared module |
| `src/noa/tools/memory.py` | **MODIFY** | C2: import from constants |
| `src/noa/external_worker/app.py` | **MODIFY** | H1: add POST /v1/complete endpoint |
| `src/noa/private_worker/app.py` | **MODIFY** | H1: add POST /rpc endpoint |
| `src/noa/external_worker/llm/google_ai.py` | **MODIFY** | H9: add synthetic tool call id |

---

### Phase QC5: Database & Data Integrity (~30 min)

**Goal:** Add performance indexes, fix data integrity issues, and clean up async/sync inconsistencies in the data layer.

**Findings:** H2, M3, M6, M9, M12

**Deliverables:**
1. **H2** — Create migration `006_performance_indexes.py` adding indexes on: `audit_log(timestamp)`, `audit_log(user_id)`, `audit_log(trace_id)`, `messages(thread_id)`, `run_events(run_id)`, `usage_stats(user_id, timestamp)`, `task_queue(status, queued_at)`.
2. **M3** — Fix retention scheduler: make `purge_expired()` async or run via a background thread with a sync session. Remove the `_PurgeProxy` workaround that always skips.
3. **M6** — Wire `expire_stale()` into the retention scheduler or a periodic background task so pending approvals are cleaned up.
4. **M9** — Fix `ContractViolationTracker.violation_count` to filter violations within the 24-hour window instead of counting all-time total.
5. **M12** — Standardize service layer on async. Convert `RunService` to accept `AsyncSession`. Remove sync methods from `AuditService` (keep async only).

**Files:**

| File | Action | Findings |
|------|--------|----------|
| `alembic/versions/006_performance_indexes.py` | **CREATE** | H2: add 7 indexes |
| `src/noa/api/app.py` | **MODIFY** | M3: fix purge scheduler |
| `src/noa/audit/service.py` | **MODIFY** | M3, M12: async purge, drop sync methods |
| `src/noa/policy/approval.py` | **MODIFY** | M6: wire expire_stale into scheduler |
| `src/noa/private_worker/rpc.py` | **MODIFY** | M9: fix 24h violation window |
| `src/noa/orchestrator/runner.py` | **MODIFY** | M12: async RunService |

---

### Phase QC6: Frontend Critical & High Fixes (~30 min)

**Goal:** Fix all broken UI behaviors that prevent core features from working correctly.

**Findings:** UI-C1, UI-C2, UI-C3, UI-H1, UI-H2, UI-H3, UI-H4, UI-H5

**Deliverables:**
1. **UI-C1** — Change `sse.ts` BASE_URL default from `"http://localhost:8000"` to `""` to match `client.ts` (fixes CORS in dev).
2. **UI-C2** — Add `"meta"` case in `handleSSEEvent` that calls `setCurrentRunId(event.data.run_id)`.
3. **UI-C3** — Import `useQueryClient` and call `queryClient.clear()` on logout in `AuthContext.tsx`.
4. **UI-H1** — Fix provider dropdown: change `"google"` to `"google_ai"` and add `"google_ai"` to the `Provider` type.
5. **UI-H2** — Filter model dropdown based on selected provider. Group models by provider.
6. **UI-H3** — Add `min="0"` and `step="0.01"` to budget inputs. Validate daily <= monthly before save.
7. **UI-H4** — Add React error boundary at `ProtectedRoute` level with "Something went wrong" message and retry button.
8. **UI-H5** — Add `AlertDialog` confirmation before memory fact deletion.

**Files:**

| File | Action | Findings |
|------|--------|----------|
| `web/src/api/sse.ts` | **MODIFY** | UI-C1: fix BASE_URL default |
| `web/src/pages/Chat.tsx` | **MODIFY** | UI-C2: handle meta event, set currentRunId |
| `web/src/auth/AuthContext.tsx` | **MODIFY** | UI-C3: clear React Query cache on logout |
| `web/src/pages/Settings.tsx` | **MODIFY** | UI-H1, UI-H2, UI-H3: provider/model/budget fixes |
| `web/src/api/types.ts` | **MODIFY** | UI-H1: add `"google_ai"` to Provider type |
| `web/src/App.tsx` | **MODIFY** | UI-H4: wrap routes in ErrorBoundary |
| `web/src/components/ErrorBoundary.tsx` | **CREATE** | UI-H4: error boundary component |
| `web/src/pages/Memory.tsx` | **MODIFY** | UI-H5: delete confirmation AlertDialog |

---

### Phase QC7: Frontend Polish & UX (~45 min)

**Goal:** Improve frontend usability, performance, and completeness.

**Findings:** UI-M1, UI-M2, UI-M3, UI-M4, UI-M5, UI-M6, UI-M7, UI-M8, UI-M9, UI-M10

**Deliverables:**
1. **UI-M1** — Delete `web/src/pages/Index.tsx` (dead code, never routed to).
2. **UI-M2** — Add cursor-based or offset pagination to Runs, Artifacts, and Cost pages using backend `limit`/`offset` params.
3. **UI-M3** — Add runtime validation of SSE event types before processing. Log unknown types instead of unsafe `as` cast.
4. **UI-M4** — On `result_ready`, immediately invalidate messages query (or append assistant message to local state) to eliminate the disappearing-text flash.
5. **UI-M5** — Auto-generate thread title from first message content (truncated to ~50 chars).
6. **UI-M6** — Add Tools page: fetch from `/api/v1/tools`, show name, description, risk tier, enabled status. Add sidebar link.
7. **UI-M7** — Add loading skeletons and "No data yet" empty states to Cost charts.
8. **UI-M8** — Use settings query data directly in Chat instead of copying to local state on mount, or invalidate cache on navigation.
9. **UI-M9** — Fetch pending approval/queue counts and show badges on sidebar items.
10. **UI-M10** — Add `React.lazy()` + `Suspense` for route-level code splitting. Lazy-load Cost (recharts) and other heavy pages.

**Files:**

| File | Action | Findings |
|------|--------|----------|
| `web/src/pages/Index.tsx` | **DELETE** | UI-M1: dead code |
| `web/src/pages/Runs.tsx` | **MODIFY** | UI-M2: add pagination |
| `web/src/pages/Artifacts.tsx` | **MODIFY** | UI-M2: add pagination |
| `web/src/pages/Cost.tsx` | **MODIFY** | UI-M2, UI-M7: pagination + empty states |
| `web/src/api/sse.ts` | **MODIFY** | UI-M3: validate event types |
| `web/src/pages/Chat.tsx` | **MODIFY** | UI-M4, UI-M5, UI-M8: streaming + thread names + settings |
| `web/src/pages/Tools.tsx` | **CREATE** | UI-M6: tools management page |
| `web/src/components/layout/AppSidebar.tsx` | **MODIFY** | UI-M6, UI-M9: tools link + notification badges |
| `web/src/App.tsx` | **MODIFY** | UI-M6, UI-M10: tools route + lazy loading |

---

### Phase QC8: Architecture & Robustness (~60 min)

**Goal:** Address remaining architectural issues and medium-priority items for long-term code health.

**Findings:** A1, A2, A4, A5, H8, M1, M5, M7, M10, M14

**Deliverables:**
1. **A1** — Replace module-level globals (`app_state.py`, `nodes/agent.py`, `nodes/tools.py`) with FastAPI `app.state` and dependency injection via `Depends()`.
2. **A2** — Refactor `ProviderRouter.from_settings()`: inject pre-built clients via `dict[str, LLMClient]` instead of creating them internally.
3. **A4** — Implement `Checkpointer` backed by Postgres (`run_checkpoints` table) per SPEC.md S10.1. Persist and restore orchestrator state on crash.
4. **A5** — Create a `@transactional` async context manager for unit-of-work pattern. Apply to service methods that need atomic operations.
5. **H8** — Replace in-memory rate limiting with database-backed rate limiting keyed by `(user_id, action)`. Survives restarts and multi-process deployment.
6. **M1** — Wire idempotency key extraction into endpoints. Check for duplicate requests before processing.
7. **M5** — Send `Last-Event-ID` header on SSE reconnection. Add backend event replay API for missed events.
8. **M7** — Enforce step-up auth: check `requires_step_up_auth()` result and require re-authentication for high-risk actions.
9. **M10** — Persist Google refresh tokens to the database instead of in-memory storage.
10. **M14** — Add `AbortController` with configurable timeout to all `fetch()` calls in the frontend API client.

**Files:**

| File | Action | Findings |
|------|--------|----------|
| `src/noa/api/app.py` | **MODIFY** | A1: use app.state instead of globals |
| `src/noa/api/dependencies.py` | **CREATE** | A1: DI providers via Depends() |
| `src/noa/orchestrator/nodes/agent.py` | **MODIFY** | A1: remove module-level globals |
| `src/noa/orchestrator/nodes/tools.py` | **MODIFY** | A1: remove module-level globals |
| `src/noa/external_worker/llm/router.py` | **MODIFY** | A2: accept injected clients |
| `src/noa/orchestrator/checkpointer.py` | **MODIFY** | A4: implement Postgres checkpointer |
| `alembic/versions/007_run_checkpoints.py` | **CREATE** | A4: run_checkpoints table |
| `src/noa/db/transaction.py` | **CREATE** | A5: @transactional context manager |
| `src/noa/auth/service.py` | **MODIFY** | H8: DB-backed rate limiting |
| `src/noa/tools/rate_limiter.py` | **MODIFY** | H8: key by (user_id, action) |
| `src/noa/api/middleware.py` | **MODIFY** | M1: wire idempotency checks |
| `web/src/api/sse.ts` | **MODIFY** | M5: Last-Event-ID on reconnect |
| `src/noa/api/v1/runs.py` | **MODIFY** | M5: event replay endpoint |
| `src/noa/policy/engine.py` | **MODIFY** | M7: enforce step-up auth |
| `src/noa/tools/google_auth.py` | **MODIFY** | M10: persist refresh tokens to DB |
| `web/src/api/client.ts` | **MODIFY** | M14: AbortController timeout |

---

## Wave 15: Native iOS Client (SwiftUI)

Implements SPEC.md §36 Phase 3: a native SwiftUI thin client for iOS with push notifications, voice, biometric auth, offline queue, and VPN integration. All intelligence stays server-side — the app handles UI + auth + push + voice.

**Project:** `ios/Noa/` in monorepo, iOS 17+, MVVM, Swift Package Manager, no external HTTP dependencies.

**Dependency graph:**
```
iOS1 (APNs Backend) ──────────────────────────→ iOS6 (Push Client) ─→ iOS7 (Biometric/Approvals)
iOS2 (Voice Backend) ─────────────────────────→ iOS8 (Voice)              ↑
iOS3 (Scaffold) → iOS4 (Auth/Keychain) → iOS5 (Chat/SSE) ───────────────┘
    ├→ iOS9 (Offline Queue)                         └─→ iOS8 (Voice)
    └→ iOS10 (VPN/Pinning)
All ──→ iOS11 (Integration/Polish)
```

---

### Phase iOS1: APNs Push Notification Backend (~45 min)

**Goal:** No push notification infrastructure exists on the backend. This phase adds device token registration, an APNs HTTP/2 push service, and hooks into approval/run events.

**Spec refs:** SPEC.md §29.5, §23.2, §29.6

**Depends on:** None (Wave 14 complete)
**Blocks:** iOS6

**Deliverables:**
1. `device_push_tokens` DB table (user_id, device_id, platform, push_token, created_at, updated_at)
2. Alembic migration `005_device_push_tokens.py`
3. `POST /api/v1/devices/push-token` endpoint to register/update device push tokens
4. `DELETE /api/v1/devices/push-token` endpoint to unregister on logout
5. `APNsService` class using HTTP/2 to `api.push.apple.com` with JWT-based auth
6. Push payload per §29.5: only notification_type, request_id, risk_tier (no private data)
7. Approval batcher: 30-second window per §23.2
8. Integration hooks in approval service and run service for push triggers

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/db/models/device_token.py` | **CREATE** | DevicePushToken SQLAlchemy model |
| `alembic/versions/005_device_push_tokens.py` | **CREATE** | Migration for device_push_tokens table |
| `src/noa/push/__init__.py` | **CREATE** | Push notification package |
| `src/noa/push/apns.py` | **CREATE** | APNsService: HTTP/2 client, JWT-based auth to APNs |
| `src/noa/push/schemas.py` | **CREATE** | PushPayload, DeviceTokenRequest Pydantic schemas |
| `src/noa/push/batcher.py` | **CREATE** | ApprovalBatcher: 30-second window batching per §23.2 |
| `src/noa/api/v1/devices.py` | **CREATE** | Device push token registration endpoints |
| `src/noa/config.py` | **MODIFY** | Add APNS_KEY_ID, APNS_TEAM_ID, APNS_KEY_PATH, APNS_BUNDLE_ID |
| `src/noa/policy/approval.py` | **MODIFY** | Hook push notification on approval_requested events |
| `src/noa/runs/service.py` | **MODIFY** | Hook push notification on run_completed/run_failed |
| `tests/unit/test_ios1_apns.py` | **CREATE** | APNs service and endpoint tests |

**Tests (~14):**
- Device token registration: valid token stored, duplicate update works
- Device token deletion: token removed on unregister
- APNs payload construction: only type + request_id + risk_tier (no private data)
- APNs HTTP/2 client: mock sends, error handling for expired/invalid tokens
- Approval batching: events within 30s window batched into single notification
- Approval batching: events outside window sent separately
- Push trigger on approval_requested, run_completed, run_failed events
- No push sent for low-risk auto-approved actions
- Auth required: unauthenticated requests rejected with 401

**Test gate:**
```bash
pytest tests/unit/test_ios1_apns.py -v
```

---

### Phase iOS2: Voice Upload Endpoint (~30 min)

**Goal:** No voice/audio endpoint exists. This phase adds an audio upload endpoint that accepts recorded audio, transcribes via Whisper API, and optionally pipes into the chat pipeline.

**Spec refs:** SPEC.md §29.3, §36.3 item 3

**Depends on:** None
**Blocks:** iOS8

**Deliverables:**
1. `POST /api/v1/voice/transcribe` endpoint accepting multipart/form-data audio (m4a, wav, mp3)
2. Audio validation: max 25MB, allowed MIME types
3. `TranscriptionService` using OpenAI Whisper API (reuses existing httpx infrastructure)
4. Optional mode: feed transcription directly into chat pipeline (returns SSE stream)
5. Artifact storage for original audio file

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/voice/__init__.py` | **CREATE** | Voice package |
| `src/noa/voice/transcription.py` | **CREATE** | TranscriptionService: Whisper API client via httpx |
| `src/noa/voice/schemas.py` | **CREATE** | VoiceUploadResponse, TranscriptionResult schemas |
| `src/noa/api/v1/voice.py` | **CREATE** | Voice endpoint: multipart upload, transcribe, optional chat |
| `src/noa/config.py` | **MODIFY** | Add WHISPER_MODEL, MAX_AUDIO_SIZE_MB settings |
| `tests/unit/test_ios2_voice.py` | **CREATE** | Voice endpoint and transcription tests |

**Tests (~10):**
- Audio upload: valid m4a file accepted, returns transcription
- Audio validation: file exceeding 25MB rejected with 413
- Audio validation: unsupported MIME type rejected with 415
- Transcription service: mock Whisper API call, parse response
- Transcription with chat: transcribed text routed to chat pipeline, returns SSE
- Transcription-only mode: returns JSON with transcription text
- Error handling: Whisper API failure returns proper error envelope
- Auth required, idempotency, artifact creation

**Test gate:**
```bash
pytest tests/unit/test_ios2_voice.py -v
```

---

### Phase iOS3: Xcode Project Scaffold & Networking Layer (~60 min)

**Goal:** No iOS project exists. This phase creates the Xcode project, MVVM structure, and core networking layer with API client, SSE parser, and shared model types.

**Spec refs:** SPEC.md §29.1, §25.3

**Depends on:** None (backend API already exists)
**Blocks:** iOS4, iOS5, iOS6, iOS7, iOS8, iOS9, iOS10

**Deliverables:**
1. Xcode project at `ios/Noa/` with SwiftUI app target and test targets
2. MVVM directory structure: Models, Views, ViewModels, Services, Utilities
3. `APIClient` class: generic request with `ApiResponse<T>` decoding, auth header injection, 401 retry with refresh, idempotency key generation
4. `SSEClient` class: streaming line parser using `URLSession.bytes(for:)`, reconnection with backoff [1s, 2s, 5s, 10s]
5. `NoaEnvironment` configuration (base URL, environment switching)
6. Shared model types mirroring backend schemas (Thread, Message, Run, RunEvent, Approval, etc.)
7. `DeviceID` utility — persistent UUID in Keychain

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Noa.xcodeproj/` | **CREATE** | Xcode project file |
| `ios/Noa/Noa/NaoApp.swift` | **CREATE** | SwiftUI App entry point |
| `ios/Noa/Noa/Configuration/Environment.swift` | **CREATE** | Base URL, environment enum |
| `ios/Noa/Noa/Models/ApiResponse.swift` | **CREATE** | Generic ApiResponse<T>, ApiError matching §25.3 |
| `ios/Noa/Noa/Models/AuthModels.swift` | **CREATE** | LoginRequest, AuthTokens, RefreshRequest |
| `ios/Noa/Noa/Models/ChatModels.swift` | **CREATE** | Thread, Message, ChatRequest, SSEEvent |
| `ios/Noa/Noa/Models/RunModels.swift` | **CREATE** | Run, RunEvent, RunStatus, RiskTier, PrivacyMode |
| `ios/Noa/Noa/Models/ApprovalModels.swift` | **CREATE** | Approval, ApprovalDecision |
| `ios/Noa/Noa/Services/APIClient.swift` | **CREATE** | HTTP client: generic request, auth injection, 401 retry |
| `ios/Noa/Noa/Services/SSEClient.swift` | **CREATE** | SSE streaming parser, reconnection with backoff |
| `ios/Noa/Noa/Services/Protocols/` | **CREATE** | Protocols for DI in tests |
| `ios/Noa/Noa/Utilities/DeviceID.swift` | **CREATE** | Persistent device ID (UUID in Keychain) |
| `ios/Noa/NaoTests/` | **CREATE** | Test targets |

**Tests (~18):**
- APIClient: GET/POST encoding, auth header, 401 retry, 429 handling, network error
- SSEParser: `data:` frame parsing, malformed line handling, multi-line, reconnection, run_id capture
- Model decoding: all types from JSON
- DeviceID: generated once, persisted across calls
- Idempotency key: unique per write request

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16'
```

---

### Phase iOS4: Keychain Storage & Auth Flow (~45 min)

**Goal:** Implement Keychain-based token storage, login screen, and token refresh lifecycle.

**Spec refs:** SPEC.md §29.3 item 5, §5.1–5.4

**Depends on:** iOS3
**Blocks:** iOS5, iOS6, iOS7

**Deliverables:**
1. `KeychainService` wrapping Security framework (SecItemAdd/Update/Delete/CopyMatching)
2. Token storage with `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`
3. `AuthService` handling login, refresh, logout with Keychain persistence
4. `AuthViewModel` (`@Observable`) managing auth state
5. `LoginView` SwiftUI screen with email/password form
6. `AuthGuard` view modifier redirecting to login when unauthenticated
7. Automatic token refresh on app foreground (if access token near expiry)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Noa/Services/KeychainService.swift` | **CREATE** | Keychain CRUD wrapper |
| `ios/Noa/Noa/Services/AuthService.swift` | **CREATE** | Login/refresh/logout, Keychain persistence |
| `ios/Noa/Noa/ViewModels/AuthViewModel.swift` | **CREATE** | Auth state, login action, auto-refresh |
| `ios/Noa/Noa/Views/Auth/LoginView.swift` | **CREATE** | Email + password form |
| `ios/Noa/Noa/Views/Auth/AuthGuard.swift` | **CREATE** | Auth check view modifier |
| `ios/Noa/Noa/NaoApp.swift` | **MODIFY** | Inject AuthViewModel, wrap in AuthGuard |

**Tests (~16):**
- KeychainService: CRUD, access level enforcement
- AuthService: login stores tokens, failure clears, refresh rotates, logout clears
- AuthViewModel: state transitions, auto-refresh, error display

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:NaoTests/KeychainServiceTests -only-testing:NaoTests/AuthServiceTests -only-testing:NaoTests/AuthViewModelTests
```

---

### Phase iOS5: Chat UI with SSE Streaming (~60 min)

**Goal:** Build the primary chat screen with message composition, SSE streaming responses, and thread management.

**Spec refs:** SPEC.md §29.2, §22.2, §36.3 item 1

**Depends on:** iOS3, iOS4
**Blocks:** iOS7, iOS8

**Deliverables:**
1. `ChatView` with message list, composer bar, and real-time streaming display
2. `ChatViewModel` managing SSE connection lifecycle and token accumulation
3. `ThreadListView` and `ThreadListViewModel` for thread management
4. `NavigationSplitView` layout (thread list + chat detail)
5. Inline indicators: tool calls, approval requests, classification, step progress
6. Model/privacy mode selectors in composer

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Noa/Services/ChatService.swift` | **CREATE** | POST /chat with SSE, thread CRUD |
| `ios/Noa/Noa/ViewModels/ChatViewModel.swift` | **CREATE** | SSE lifecycle, token accumulation |
| `ios/Noa/Noa/ViewModels/ThreadListViewModel.swift` | **CREATE** | Thread list loading, creation |
| `ios/Noa/Noa/Views/Chat/ChatView.swift` | **CREATE** | Message list + composer + streaming |
| `ios/Noa/Noa/Views/Chat/MessageBubble.swift` | **CREATE** | Individual message rendering |
| `ios/Noa/Noa/Views/Chat/ComposerBar.swift` | **CREATE** | Text input, send button, selectors |
| `ios/Noa/Noa/Views/Chat/ToolCallCard.swift` | **CREATE** | Inline tool call display |
| `ios/Noa/Noa/Views/Chat/ThreadListView.swift` | **CREATE** | Thread sidebar |
| `ios/Noa/Noa/Views/MainTabView.swift` | **CREATE** | Tab navigation (Chat, Runs, Settings) |

**Tests (~14):**
- SSE events: meta, token_stream accumulation, result_ready, error propagation
- Tool/approval event display
- Thread CRUD and message history loading

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:NaoTests/ChatViewModelTests -only-testing:NaoTests/ChatServiceTests
```

---

### Phase iOS6: Push Notifications (APNs Client) (~45 min)

**Goal:** Integrate APNs, register device token with backend, handle notification display and deep linking.

**Spec refs:** SPEC.md §29.5, §23.2, §36.3 item 2

**Depends on:** iOS1 (backend), iOS4 (auth)
**Blocks:** iOS7

**Deliverables:**
1. APNs entitlement and capability in Xcode project
2. `PushNotificationService` handling UNUserNotificationCenter registration
3. Device token registration with backend (`POST /api/v1/devices/push-token`)
4. Token unregistration on logout
5. Notification handling: approval_requested, run_completed, run_failed
6. Deep linking: tapping notification opens relevant approval or run detail
7. Notification categories with inline Approve/Deny actions (medium-risk)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Noa/Noa.entitlements` | **CREATE** | Push notification entitlement |
| `ios/Noa/Noa/Services/PushNotificationService.swift` | **CREATE** | UNUserNotificationCenter, token registration, deep link routing |
| `ios/Noa/Noa/Services/DeviceService.swift` | **CREATE** | POST/DELETE /devices/push-token API calls |
| `ios/Noa/Noa/NaoApp.swift` | **MODIFY** | AppDelegate for push token callback, notification categories |
| `ios/Noa/Noa/Utilities/DeepLinkRouter.swift` | **CREATE** | Notification-based deep linking |

**Tests (~12):**
- Authorization grant/deny, token registration/unregistration, notification display per type, deep link navigation, inline actions

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:NaoTests/PushNotificationServiceTests
```

---

### Phase iOS7: Biometric Step-Up Auth & Approval Flow (~45 min)

**Goal:** Add Face ID/Touch ID step-up for high-risk approvals and the full approval review UI with batch support.

**Spec refs:** SPEC.md §29.3 item 4, §29.6, §23.2, §36.3 item 4

**Depends on:** iOS5, iOS6
**Blocks:** None

**Deliverables:**
1. `BiometricService` wrapping LocalAuthentication (LAContext)
2. Face ID / Touch ID evaluation with passcode fallback
3. `ApprovalListView` showing pending approvals with dry-run previews
4. `ApprovalDetailView` with approve/deny actions
5. Biometric gate: high-risk approvals require Face ID before submission
6. Batch approval UI per §23.2: approve/deny individual or all
7. NSFaceIDUsageDescription in Info.plist

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Noa/Services/BiometricService.swift` | **CREATE** | LAContext evaluation, capability check |
| `ios/Noa/Noa/Services/ApprovalService.swift` | **CREATE** | GET pending, POST decide API calls |
| `ios/Noa/Noa/ViewModels/ApprovalListViewModel.swift` | **CREATE** | Pending approvals, batch state |
| `ios/Noa/Noa/ViewModels/ApprovalDetailViewModel.swift` | **CREATE** | Single approval, biometric gate |
| `ios/Noa/Noa/Views/Approvals/ApprovalListView.swift` | **CREATE** | Pending approvals list |
| `ios/Noa/Noa/Views/Approvals/ApprovalDetailView.swift` | **CREATE** | Approval detail with approve/deny |
| `ios/Noa/Noa/Views/Approvals/BatchApprovalBar.swift` | **CREATE** | Batch controls |
| `ios/Noa/Noa/Info.plist` | **MODIFY** | NSFaceIDUsageDescription |

**Tests (~14):**
- Biometric success/failure/fallback, approval fetch/submit, risk tier gating, batch operations, deep link integration

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:NaoTests/BiometricServiceTests -only-testing:NaoTests/ApprovalViewModelTests
```

---

### Phase iOS8: Voice Recording & Playback (~60 min)

**Goal:** Add voice recording via AVFoundation, upload to backend voice endpoint, display transcription. Backend supports two transcription providers selectable in Settings: OpenAI Whisper API and local whisper.cpp (host-side service via Metal/Apple Silicon).

**Spec refs:** SPEC.md §29.3 item 3, §36.3 item 3

**Depends on:** iOS2 (backend), iOS5 (chat)
**Blocks:** None

**Architecture — Dual Transcription Provider:**
```
iOS → POST /api/v1/voice/transcribe (Docker) → TranscriptionService
                                                  ├─ OpenAIWhisperProvider  → api.openai.com/v1/audio/transcriptions
                                                  └─ WhisperCppProvider     → http://host.docker.internal:8001/transcribe
```

Settings: `transcription_provider` = `openai` | `whisper_cpp` (stored in DB user settings)
- OpenAI: uses `OPENAI_API_KEY` env var
- whisper.cpp: uses `WHISPER_CPP_URL` env var (default: `http://host.docker.internal:8001`); runs large-v3 Q5 with Metal on Mac host

**Deliverables:**

*Backend:*
1. `TranscriptionProvider` ABC with `transcribe(audio_data, filename, mime_type)` contract
2. `OpenAIWhisperProvider` — existing logic extracted from `TranscriptionService`
3. `WhisperCppProvider` — POSTs audio to `WHISPER_CPP_URL/transcribe`, parses `{"text": "..."}` response
4. `TranscriptionService` updated to dispatch to selected provider based on user setting
5. `voice.py` updated: reads provider from user settings, no longer hard-requires `OPENAI_API_KEY`
6. `tools/whisper-service/` — standalone Python FastAPI host service wrapping whisper.cpp binary
   - `server.py`: accepts multipart audio, calls `whisper` CLI, returns `{"text": "..."}`
   - `README.md`: setup instructions (model: large-v3 Q5, Metal acceleration)
7. Settings: `transcription_provider` field added to user settings schema + API

*iOS:*
8. `AudioRecorderService` using AVAudioRecorder for m4a recording
9. `AudioPlayerService` using AVAudioPlayer for playback
10. Microphone permission handling (NSMicrophoneUsageDescription)
11. Voice button in ComposerBar: tap-and-hold or toggle recording
12. Recording waveform/timer visualization
13. Upload to `POST /api/v1/voice/transcribe`, auto-send to chat option
14. Max 10 min recording duration
15. Settings UI: transcription provider picker (OpenAI / Local whisper.cpp)

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/voice/transcription.py` | **MODIFY** | Extract provider ABC, add WhisperCppProvider, dispatch by setting |
| `src/noa/api/v1/voice.py` | **MODIFY** | Read provider setting, remove hard OPENAI_API_KEY check |
| `tools/whisper-service/server.py` | **CREATE** | Host-side FastAPI wrapper for whisper.cpp binary |
| `tools/whisper-service/README.md` | **CREATE** | Setup: install whisper.cpp, large-v3 Q5, Metal |
| `ios/Noa/Sources/Noa/Services/AudioRecorderService.swift` | **CREATE** | AVAudioRecorder wrapper |
| `ios/Noa/Sources/Noa/Services/AudioPlayerService.swift` | **CREATE** | AVAudioPlayer wrapper |
| `ios/Noa/Sources/Noa/Services/VoiceService.swift` | **CREATE** | Upload to /voice/transcribe (multipart, no envelope) |
| `ios/Noa/Sources/Noa/ViewModels/VoiceViewModel.swift` | **CREATE** | Recording state, upload, transcription |
| `ios/Noa/Sources/Noa/Views/Chat/VoiceRecordButton.swift` | **CREATE** | Record button with waveform |
| `ios/Noa/Sources/Noa/Views/Chat/ComposerBar.swift` | **MODIFY** | Add voice button |
| `ios/Noa/Sources/Noa/Views/Settings/TranscriptionProviderView.swift` | **CREATE** | Provider picker in Settings |
| `ios/Noa/Noa/Info.plist` | **MODIFY** | NSMicrophoneUsageDescription |

**Note:** `voice.py` returns a flat JSON response (not `{ok, data, error}` envelope). `VoiceService` must use a raw URLSession decode path, not `APIClient.request<T>()`.

**Tests (~15):**
- Recording start/stop, permission handling, upload multipart, transcription receipt (both providers), provider switching, auto-send mode, cancel/discard, max duration
- Python: `WhisperCppProvider` HTTP call, provider dispatch by setting

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:NaoTests/VoiceViewModelTests -only-testing:NaoTests/AudioRecorderServiceTests
```

---

### Phase iOS9: Offline Request Queue with Idempotency (~45 min)

**Goal:** Persistent queue for offline requests with idempotency keys, auto-drain on connectivity resume.

**Spec refs:** SPEC.md §29.3 item 6, §25.4, §36.3 item 6

**Depends on:** iOS3
**Blocks:** None

**Deliverables:**
1. `OfflineQueueService` with file-based persistent FIFO storage
2. `NetworkMonitorService` via NWPathMonitor
3. Auto-drain on connectivity restored with idempotency keys
4. Retry with exponential backoff (1s, 2s, 4s, 8s, 16s), max 5 retries
5. APIClient integration: write requests queue when offline instead of failing
6. UI offline indicator with queue count badge

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Noa/Services/OfflineQueueService.swift` | **CREATE** | Persistent queue, drain logic |
| `ios/Noa/Noa/Services/NetworkMonitorService.swift` | **CREATE** | NWPathMonitor wrapper |
| `ios/Noa/Noa/Models/QueuedRequest.swift` | **CREATE** | Codable model for persisted requests |
| `ios/Noa/Noa/Services/APIClient.swift` | **MODIFY** | Intercept writes when offline |
| `ios/Noa/Noa/Views/Shared/OfflineIndicator.swift` | **CREATE** | Offline banner + queue count |

**Tests (~14):**
- Enqueue/dequeue, persistence across restart, idempotency preservation, retry backoff, max retries, FIFO order, APIClient integration, network state detection

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:NaoTests/OfflineQueueServiceTests -only-testing:NaoTests/NetworkMonitorServiceTests
```

---

### Phase iOS10: VPN Auto-Connect & Certificate Pinning (~30 min)

**Goal:** Certificate pinning on all API connections (mandatory §29.4) and VPN status detection with auto-connect prompt.

**Spec refs:** SPEC.md §29.4, §36.3 item 7

**Depends on:** iOS3
**Blocks:** None

**Deliverables:**
1. `CertificatePinningDelegate` — URLSessionDelegate with public key (SPKI) pinning
2. Pin hashes embedded in app bundle, configurable for rotation
3. `VPNService` — NEVPNManager status detection
4. Auto-connect prompt when off-LAN and VPN disconnected
5. Launch Tailscale/WireGuard via URL scheme
6. APIClient uses pinning delegate for all sessions

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Noa/Services/CertificatePinningDelegate.swift` | **CREATE** | URLSessionDelegate with SPKI pinning |
| `ios/Noa/Noa/Services/VPNService.swift` | **CREATE** | NEVPNManager, URL scheme launch |
| `ios/Noa/Noa/Configuration/PinnedCertificates.swift` | **CREATE** | Embedded pin hashes |
| `ios/Noa/Noa/Services/APIClient.swift` | **MODIFY** | Use pinning delegate |
| `ios/Noa/Noa/Views/Shared/VPNStatusBanner.swift` | **CREATE** | VPN connect prompt |

**Tests (~10):**
- Valid/invalid/expired/self-signed cert, multi-pin rotation, VPN state detection, URL scheme launch, on-LAN skip

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16' -only-testing:NaoTests/CertificatePinningTests -only-testing:NaoTests/VPNServiceTests
```

---

### Phase iOS11: Integration Tests & Polish (~45 min)

**Goal:** End-to-end integration tests, accessibility, dark mode, error states, app icon and launch screen.

**Spec refs:** SPEC.md §37 (adapted for iOS)

**Depends on:** iOS3–iOS10 (all previous iOS phases)
**Blocks:** None

**Deliverables:**
1. Mock API server via URLProtocol for integration tests
2. E2E tests: login, chat+SSE, approval+biometric, offline queue drain
3. Accessibility: VoiceOver labels, Dynamic Type, contrast ratios
4. Dark mode verification
5. App icon, launch screen, error/empty state views

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/NaoTests/Integration/MockURLProtocol.swift` | **CREATE** | URLProtocol-based mock server |
| `ios/Noa/NaoTests/Integration/LoginFlowTests.swift` | **CREATE** | E2E login flow |
| `ios/Noa/NaoTests/Integration/ChatFlowTests.swift` | **CREATE** | E2E chat + SSE |
| `ios/Noa/NaoTests/Integration/ApprovalFlowTests.swift` | **CREATE** | E2E approval + biometric |
| `ios/Noa/NaoTests/Integration/OfflineQueueFlowTests.swift` | **CREATE** | E2E offline drain |
| `ios/Noa/Noa/Views/Shared/ErrorView.swift` | **CREATE** | Reusable error state |
| `ios/Noa/Noa/Views/Shared/EmptyStateView.swift` | **CREATE** | Reusable empty state |
| `ios/Noa/Noa/Assets.xcassets/` | **MODIFY** | App icon, accent color |

**Tests (~16):**
- E2E: login, chat streaming, approval+biometric, offline queue, token refresh, logout
- Accessibility, Dynamic Type, dark mode, error states

**Test gate:**
```bash
xcodebuild test -project ios/Noa/Noa.xcodeproj -scheme Noa -destination 'platform=iOS Simulator,name=iPhone 16'
```

---

### Key Technical Decisions

1. **No external HTTP library** — URLSession async/await + `bytes(for:)` handles SSE natively on iOS 17
2. **Keychain with `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`** — tokens available for background push but not transferable
3. **Public key (SPKI) pinning** — survives certificate rotation
4. **VPN via URL scheme** — launches Tailscale/WireGuard app, no Network Extension needed
5. **File-based offline queue** — simpler than SwiftData for FIFO of serialized requests
6. **APNs JWT auth** (server-side) — Apple's recommended approach
7. **Whisper API for voice transcription** — reuses existing OpenAI httpx infrastructure

---

## Wave 16: Playwright E2E Testing

Browser-level end-to-end tests for the web frontend using Playwright. Covers auth flows, SSE chat streaming, settings persistence, and navigation. Runs against mock mode (`VITE_USE_MOCKS=true`) for deterministic, backend-independent execution.

**Critical discovery:** The app's mock mode only intercepts `apiRequest()` calls. The `SSEClient` in `sse.ts` uses raw `fetch()` directly, so mock mode does **not** cover SSE streaming. Chat tests use Playwright's `page.route()` to intercept and simulate SSE responses at the network level.

**Environment contract:**
- Mock mode activated via `webServer.env: { VITE_USE_MOCKS: "true" }` in Playwright config
- Vite dev server auto-started by Playwright on port 5173
- Chromium only (headless), single browser to minimize install size
- CI: retries=2, trace on first retry, screenshot + video on failure, `github` reporter
- Local: retries=0, reuse existing dev server, `html` reporter

**Auth fixture strategy:**
- Reusable `storageState`-based fixture: login via UI → save tokens to `e2e/.auth/state.json` → reuse across tests
- No direct localStorage injection — validates real login path

**Selector conventions:**
1. Role-based selectors first: `getByRole('button', { name: 'Sign in' })`, `getByLabel('Email')`
2. `data-testid` only when role/label is ambiguous (chat input, send button, streaming area, message list)
3. Never CSS classes (brittle with Tailwind), never DOM structure selectors

---

### Phase PW1: Playwright Setup & Auth Tests (~30 min)

**Goal:** Install Playwright, create config with CI defaults, build auth fixture, and write auth/route-guard tests.

**Findings addressed:** UI-C3 (logout doesn't clear cache — verified by logout test)

**Deliverables:**
1. Install `@playwright/test` as dev dependency, install Chromium browser
2. Create `web/playwright.config.ts` with webServer (auto-start Vite + mock mode), Chromium project, CI/local defaults (retries, traces, screenshots, video)
3. Create `web/e2e/fixtures.ts` with reusable `authenticatedPage` fixture using `storageState`
4. Create `web/e2e/auth.spec.ts` with 6 tests:
   - Login page renders with email + password fields
   - Successful login redirects to chat
   - Invalid credentials show error message (via `page.route()` intercept returning error)
   - Unauthenticated user redirected to `/login`
   - Logout clears session and redirects to login
   - Register page renders with form fields
5. Add npm scripts: `test:e2e`, `test:e2e:ui`, `test:e2e:report`
6. Add Playwright artifacts to `web/.gitignore`

**Files:**

| File | Action |
|------|--------|
| `web/package.json` | EDIT — add `@playwright/test`, npm scripts |
| `web/playwright.config.ts` | CREATE |
| `web/e2e/fixtures.ts` | CREATE |
| `web/e2e/auth.spec.ts` | CREATE |
| `web/.gitignore` | EDIT — add `test-results/`, `playwright-report/`, `playwright/.cache/`, `e2e/.auth/` |

**Spec refs:** S23 (authentication), S25 (session management)

**Tests (verify green):**
- `npm run test:e2e -- --grep auth` — 6 auth tests pass
- Verify trace file generated on intentional failure

---

### Phase PW2: Chat E2E with SSE Simulation (~30 min)

**Goal:** Test the core chat journey end-to-end including SSE streaming simulation and failure handling.

**Deliverables:**
1. Create `web/e2e/helpers/sse-mock.ts` — helper that intercepts `/api/v1/chat` POST via `page.route()` and responds with a `ReadableStream` of controlled SSE events (`token_stream`, `result_ready`, `error`)
2. Add `data-testid` attributes to `Chat.tsx`: `chat-input`, `chat-send`, `streaming-content`, `message-list`
3. Create `web/e2e/chat.spec.ts` with 6 tests:
   - Authenticated user sees chat input and send button
   - Send message → user message appears in UI
   - Send message → SSE tokens stream incrementally into view
   - Send message → stream completes → final message visible
   - SSE error → error state shown, input re-enabled
   - Send button disabled while streaming

**Files:**

| File | Action |
|------|--------|
| `web/e2e/helpers/sse-mock.ts` | CREATE |
| `web/e2e/chat.spec.ts` | CREATE |
| `web/src/pages/Chat.tsx` | EDIT — add 4 `data-testid` attributes |

**Spec refs:** S10 (orchestrator SSE), S11 (run events)

**Tests (verify green):**
- `npm run test:e2e -- --grep chat` — 6 chat tests pass

---

### Phase PW3: Settings & Navigation Tests (~20 min)

**Goal:** Test settings save/load flow and navigation correctness (routing, 404, sidebar).

**Deliverables:**
1. Create `web/e2e/settings.spec.ts` with 3 tests:
   - Authenticated user sees settings form with populated fields
   - Change provider → save → success toast appears
   - Change budget values → save → values persist on reload (mock returns updated values)
2. Create `web/e2e/navigation.spec.ts` with 3 tests:
   - Unknown route shows 404 page
   - Sidebar links navigate to correct pages
   - Auth-protected pages redirect when unauthenticated

**Files:**

| File | Action |
|------|--------|
| `web/e2e/settings.spec.ts` | CREATE |
| `web/e2e/navigation.spec.ts` | CREATE |

**Spec refs:** S24 (user settings), S23.3 (route protection)

**Tests (verify green):**
- `npm run test:e2e` — all 18 tests pass
- `npm run test:e2e:report` — HTML report generates correctly

---

## Changelog

### Phase QC6: Frontend Critical & High Fixes (~45 min)

**Goal:** Fix 3 Critical and 5 High frontend findings that break core functionality or create security/UX issues.

**Findings:** UI-C1, UI-C2, UI-C3, UI-H1, UI-H2, UI-H3, UI-H4, UI-H5

**Changes:**

| Finding | File(s) | Change |
|---------|---------|--------|
| UI-C1 | `web/src/api/sse.ts` | Change BASE_URL default from `"http://localhost:8000"` to `""` |
| UI-C2 | `web/src/pages/Chat.tsx`, `web/src/api/types.ts` | Add `"meta"` to SSEEventType, add meta case in handleSSEEvent to capture run_id, invalidate messages on result_ready |
| UI-C3 | `web/src/auth/AuthContext.tsx` | Import useQueryClient, call queryClient.clear() on logout |
| UI-H1 | `web/src/api/types.ts`, `web/src/pages/Settings.tsx` | Add `"google_ai"` to Provider type, fix dropdown value |
| UI-H2 | `web/src/pages/Settings.tsx` | Define PROVIDER_MODELS map, filter model dropdown by selected provider |
| UI-H3 | `web/src/pages/Settings.tsx` | Add min="0" step="0.01", validate daily <= monthly before save |
| UI-H4 | `web/src/components/ErrorBoundary.tsx` (CREATE), `web/src/App.tsx` | Class component error boundary, wrap ProtectedRoute children |
| UI-H5 | `web/src/pages/Memory.tsx` | AlertDialog confirmation before delete, using existing AlertDialog component |

**Tests:** ~10 tests in `web/src/test/qc6-fixes.test.tsx`

**Dependencies:** UI-H1 (Provider type) must precede UI-H2 (model filtering). All others independent.

---

### Phase QC8: Architecture & Robustness (~90 min)

**Goal:** Pragmatic fixes for architecture and robustness findings. Large items (full DI, checkpointer) deferred.

**Findings:** A1 (cleanup only), A2, A4 (stub only), A5, H8 (simplified), M1, M5 (simplified), M7, M10, M14

**Scope Decisions:**
- **DEFER:** A1 (full DI migration — too large, touches every module), A4 (full checkpointer — needs new table, LangGraph integration)
- **SIMPLIFY:** H8 (per-user in-memory, not DB-backed), M5 (frontend Last-Event-ID + backend replay endpoint)
- **INCLUDE:** A2, A5, M1, M7, M10, M14

**Changes:**

| Finding | File(s) | Change |
|---------|---------|--------|
| A1 (cleanup) | `src/noa/api/app_state.py` | Add reset_all() for tests, type hints on getters |
| A2 | `src/noa/external_worker/llm/router.py` | Extract build_llm_clients() factory, ProviderRouter accepts injected clients dict |
| A4 (stub) | `src/noa/orchestrator/checkpointer.py` | Add NoOpCheckpointer with NotImplementedError, startup warning |
| A5 | `src/noa/db/transaction.py` (CREATE) | Async transactional context manager with commit/rollback |
| H8 | `src/noa/tools/rate_limiter.py`, `src/noa/tools/gateway.py` | Key by (user_id, action) tuple, pass user_id from gateway |
| M1 | `src/noa/api/middleware.py`, `src/noa/api/v1/chat.py` | Wire idempotency key via ContextVar, LRU cache for duplicate detection |
| M5 | `web/src/api/sse.ts`, `src/noa/api/v1/runs.py` | Send Last-Event-ID on reconnect, add event replay endpoint |
| M7 | `src/noa/tools/gateway.py`, `src/noa/policy/engine.py` | Enforce step-up gate in gateway dispatch |
| M10 | `src/noa/tools/google_auth.py`, `src/noa/tools/registration.py` | Persistence callback for refresh token, load from DB at startup |
| M14 | `web/src/api/client.ts` | AbortController with 30s timeout on fetch calls |

**Tests:** ~17 tests in `tests/unit/test_qc8_architecture.py`

**Risk:** A2 refactor keeps from_settings() as wrapper for backward compat. M7 step-up defaults to allow if no PolicyEngine injected.

---

## Wave 18: Tool Management & Credentials

**Goal:** Transform the basic tool toggle page into a full tool management dashboard with health checks, credential setup via UI (stored in Keychain), per-function permissions, and the ability to add custom tools. Bridges to MCP in the final phase.

**Architecture decisions:**
- Credentials stored in **macOS Keychain** (consistent with existing secret management), never in DB
- DB stores only metadata: tool name, configured=true/false, last health check timestamp
- Per-function permissions extend the existing `ToolCapability` model
- MCP adapter wires into existing `ToolGateway` → `ToolAdapter` protocol chain

**Dependencies:** Builds on Wave 4 (tool implementations), Wave 8 (credential management), Wave 11-12 (tool gateway + adapters), Wave 13/MR5 (capability permissions).

---

### TM1: Tool Health-Check Endpoint & Credential Status (~45 min)

**Goal:** Backend knows which tools have credentials configured and can probe each tool's API to verify they work.

**Changes:**

| Component | File(s) | Change |
|-----------|---------|--------|
| Credential status | `src/noa/tools/registration.py` | Check Keychain for each tool's required secrets, return configured/missing status |
| Health probe | `src/noa/tools/health.py` (NEW) | Lightweight probe per tool: Tavily → search "test", Calendar → list 0 events, Gmail → list 1 email, Notion → search empty. Timeout 5s. |
| Credential store endpoint | `src/noa/api/v1/tools.py` | `POST /api/v1/tools/{name}/credentials` — accepts API key/token, stores in Keychain, returns masked value. `GET` returns only masked. |
| Health endpoint | `src/noa/api/v1/tools.py` | `POST /api/v1/tools/{name}/health` — triggers probe, returns green/red + error message |
| Tool list enrichment | `src/noa/api/v1/tools.py` | `GET /api/v1/tools` now includes `credential_status: "configured" | "missing"` and `health: "ok" | "error" | "unchecked"` |

**Tests:** ~15 tests — health probe mocking, credential masking, Keychain read/write, endpoint responses.

---

### TM2: Tools API Enrichment — Functions, Permissions, Metadata (~45 min)

**Goal:** The API exposes the full structure of each tool: its functions, descriptions, parameter schemas, risk tier per function, domain assignment, and per-function capability grants.

**Changes:**

| Component | File(s) | Change |
|-----------|---------|--------|
| Rich tool schema | `src/noa/tools/definitions.py` | Add `risk_tier` and `domain` per function (e.g. `gmail.send_email` = high, `gmail.search_emails` = medium) |
| Per-function capabilities | `src/noa/tools/capabilities.py` | Extend `TOOL_CAPABILITIES` to function-level: `gmail__send_email`, `gmail__read_email` etc. |
| DB model | `src/noa/db/models/tool_capability.py` | Add `function_name` column (nullable for backward compat, NULL = all functions) |
| API response | `src/noa/api/v1/tools.py` | `GET /api/v1/tools` returns nested `functions[]` with name, description, parameters, risk_tier, enabled, domain |
| Grant/revoke per function | `src/noa/api/v1/tools.py` | `POST /api/v1/tools/{name}/{function}/enable`, `DELETE /api/v1/tools/{name}/{function}` |

**Tests:** ~15 tests — per-function grant/revoke, backward compat (NULL function = all), risk tier exposure.

---

### TM3: Tools UI Redesign — Dashboard & Health (~60 min)

**Goal:** Replace the flat toggle table with an interactive tool management dashboard.

**UI design:**

Each tool is an **expandable card** showing:
- **Header row:** Tool name, domain badge (private/external), overall status (green/red/unconfigured), master toggle
- **Expanded section:**
  - **Credentials:** Status indicator + "Configure" button → modal with API key input or "Connect with Google" OAuth button. Shows masked value if configured.
  - **Health:** Last check timestamp, "Test Connection" button → spinner → green checkmark or red X with error
  - **Functions table:** Name, description, risk tier badge (low/medium/high), individual enable/disable toggle
  - **Info:** Tool description, parameter schemas (collapsible)

**Changes:**

| Component | File(s) | Change |
|-----------|---------|--------|
| Tool card component | `web/src/pages/Tools.tsx` | Full rewrite: expandable cards, health indicators, credential setup |
| Credential modal | `web/src/components/tools/CredentialModal.tsx` (NEW) | API key input, OAuth redirect trigger, masked display |
| Health probe trigger | `web/src/pages/Tools.tsx` | "Test Connection" button calls `POST /tools/{name}/health` |
| Function toggles | `web/src/pages/Tools.tsx` | Per-function enable/disable via new endpoints |

**Tests:** ~12 tests — card expand/collapse, credential modal, health check states, function toggles.

---

### TM4: Per-Task Tool Permissions & Context Scoping (~45 min)

**Goal:** When the orchestrator runs a task, it only gets the tools relevant to that task's context — not everything the user has enabled globally.

**Changes:**

| Component | File(s) | Change |
|-----------|---------|--------|
| Task tool allowlist | `src/noa/policy/approval.py` | Approval rules can specify `allowed_tools: ["gmail__read_email", "gmail__draft_email"]` |
| Orchestrator filter | `src/noa/orchestrator/nodes/tools.py` | Before building tool list for LLM, intersect: user capabilities ∩ task allowlist |
| Default scopes | `src/noa/tools/scopes.py` (NEW) | Predefined scopes: `email_draft` (gmail read + draft), `research` (web_search + notion read), `scheduling` (calendar + gmail read) |
| UI display | `web/src/pages/Tools.tsx` | Show which tasks/scopes use each function (informational) |

**Tests:** ~12 tests — scope filtering, intersection logic, approval rule with tool allowlist.

---

### TM5: Tool Registry — Add Custom Tools via UI (~45 min)

**Goal:** Users can register new tools without code changes. Tool definitions stored in DB alongside the code-defined ones.

**Changes:**

| Component | File(s) | Change |
|-----------|---------|--------|
| DB model | `src/noa/db/models/custom_tool.py` (NEW) | CustomTool: name, description, base_url, auth_type, functions (JSONB), domain, created_by |
| Registration API | `src/noa/api/v1/tools.py` | `POST /api/v1/tools` — register new tool with JSON schema functions |
| Runtime registration | `src/noa/tools/registration.py` | On startup + on creation: load custom tools from DB, register adapters |
| Custom adapter | `src/noa/tools/adapters/http_tool.py` (NEW) | Generic HTTP adapter: calls `base_url/{function}` with JSON body, configurable auth header |
| UI form | `web/src/components/tools/AddToolModal.tsx` (NEW) | Name, base URL, auth type (API key/bearer/none), function schema editor |

**Tests:** ~15 tests — custom tool CRUD, runtime registration, HTTP adapter dispatch, schema validation.

---

### TM6: MCP Server Connector — Phase 2 Bridge (~60 min)

**Goal:** Wire the existing `McpRemoteAdapter` stub with real MCP protocol support. Connect to MCP servers, auto-discover their tools/functions, and route calls through the existing gateway.

**Changes:**

| Component | File(s) | Change |
|-----------|---------|--------|
| MCP client | `src/noa/tools/adapters/mcp_remote.py` | Replace NotImplementedError with real HTTP+SSE MCP client (using `mcp` package) |
| Auto-discovery | `src/noa/tools/mcp_discovery.py` (NEW) | Connect to MCP server, call `tools/list`, convert to internal `ToolInterface` registrations |
| MCP server config | `src/noa/api/v1/tools.py` | `POST /api/v1/tools/mcp-servers` — register MCP server URL + auth |
| Domain routing | `src/noa/tools/registration.py` | MCP servers assigned to private/external domain; calls routed to correct container network |
| UI | `web/src/components/tools/McpServerModal.tsx` (NEW) | Add MCP server: URL, auth token, domain assignment. Auto-discovers functions on connect. |
| pyproject.toml | `pyproject.toml` | Add `mcp` package dependency |

**Tests:** ~15 tests — MCP client connect/disconnect, tool discovery, domain routing, gateway integration.

---

## Wave 19: Production Readiness Cleanup

---

### Phase PR1: Backend Critical Fixes — Data Integrity (~60 min)

**Goal:** Three critical/high backend defects prevent the app from functioning correctly in production: (1) the runs list/detail endpoints return hardcoded zeros for cost, tokens, and model instead of joining UsageStats; (2) memory fact endpoints call `store.list_all()` with no user scoping, leaking facts across users; (3) RunService uses the legacy sync `.query()` ORM API on an async session, causing silent failures.

**Spec refs:** SPEC.md §22.1, §22.2, §13.2

**Depends on:** TM6
**Blocks:** PR6

**Deliverables:**
1. `list_runs` and `get_run` endpoints join `usage_stats` table and return real cost/token/model data
2. All memory fact endpoints filter by `user_id` from the authenticated user
3. `RunService` async rewrite — all methods use `await db.execute(select(...))` pattern

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/api/v1/runs.py` | **EDIT** | Join `UsageStats` in list_runs and get_run; populate model, provider, tokens_in/out, cost_usd |
| `src/noa/api/v1/memory.py` | **EDIT** | Pass `user_id` to all MemoryStore calls; fix `_persist()` → public `persist()` usage |
| `src/noa/private_worker/memory_store.py` | **EDIT** | Add `user_id` parameter support to `list_all`, `get_by_id`, `update_status`, `delete`; add public `persist()` method |
| `src/noa/runs/service.py` | **EDIT** | Rewrite all methods as async using `await db.execute(select(...))` |
| `tests/unit/test_pr1_backend_fixes.py` | **CREATE** | Tests for real cost data in runs response, user-scoped memory, async RunService |

**Tests (~18):**
- Runs data: list_runs returns real cost/token/model from joined UsageStats
- Runs data: get_run returns real data, returns zeros when no UsageStats row
- Memory scoping: list_facts filters by user_id (no cross-user leak)
- Memory scoping: approve/update/delete only affects facts owned by that user
- RunService async: create_run, get_run, list_runs, update_status, append_event all work with async session
- RunService async: update_status rejects invalid transitions
- RunService async: list_runs with thread_id, user_id, status filters

**Test gate:**
```bash
pytest tests/unit/test_pr1_backend_fixes.py -v
```

---

_Entries added after each phase completion._

| Date | Phase | Summary |
|------|-------|---------|
| — | — | Plan created |

---

## Wave 20: Deployment & Reliability + Google OAuth2

---

### Phase DE1: CI/CD Pipeline (~60 min)

**Goal:** Every pull request and merge to main runs the full test suite automatically, and merges to main build and push a versioned Docker image to the registry — so deployment is a single-command image pull, not a manual build.

**Spec refs:** SPEC.md §34 (Testing Requirements), §10.4 (Schema Migrations), §36 (Build Phases)

**Depends on:** PR7
**Blocks:** None

**Deliverables:**
1. `.github/workflows/ci.yml` — ruff + mypy + pytest on every PR/push
2. `.github/workflows/cd.yml` — Docker image build + push to ghcr.io on merge to main
3. `web` CI job: `npm run build` + `npm test` (Vitest) on every PR
4. iOS CI job: `swift test` for the SPM package on every PR
5. Wave 16 E2E gate: `npm run test:e2e` (Playwright) wired into CI
6. `tests/unit/test_de1_ci_gates.py` — validates gate scripts locally

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `.github/workflows/ci.yml` | **CREATE** | Python CI: checkout, setup-python, pip install, ruff check, mypy, pytest |
| `.github/workflows/cd.yml` | **CREATE** | Docker build on `main` push: build-push-action to ghcr.io, tag with short SHA + `latest` |
| `.github/workflows/web-ci.yml` | **CREATE** | Node CI: npm ci, build, test, test:e2e (headless) |
| `.github/workflows/ios-ci.yml` | **CREATE** | iOS CI: swift test in `ios/Noa/` |
| `tests/unit/test_de1_ci_gates.py` | **CREATE** | Local gate validator: ruff, mypy, import sanity, alembic check |

**Tests (~15):**
- Gate validator: ruff check passes on `src/noa/` with zero errors
- Gate validator: mypy passes on `src/noa/` with zero errors
- Gate validator: all top-level `src/noa` modules importable
- Gate validator: `alembic check` finds no pending schema drift
- Gate validator: pytest collects >0 tests from `tests/unit/`
- Workflow schema: `ci.yml` contains `ruff`, `mypy`, `pytest` steps
- Workflow schema: `cd.yml` contains `docker/build-push-action` and SHA tag
- Workflow schema: `web-ci.yml` contains `test:e2e` step
- Workflow schema: `ios-ci.yml` contains `swift test`
- CI env guard: workflows reject missing required secrets
- Coverage gate: pytest-cov configured, threshold ≥60%
- Image tag: CD produces `ghcr.io/${{ github.repository }}/noa-api:${{ github.sha }}`
- Branch protection: CI triggers on `pull_request` and `push` to `main`
- Dependency cache: pip and npm cached by lockfile hash
- Parallel jobs: web and Python jobs run in parallel

**Test gate:**
```bash
pytest tests/unit/test_de1_ci_gates.py -v
```

---

### Phase DE2: TLS & Reverse Proxy (~60 min)

**Goal:** All traffic to the Noa API is served over HTTPS with automatic TLS certificate management, so OAuth2 redirect URIs are valid (Google requires HTTPS) and iOS certificate pinning works against a real domain. Caddy terminates TLS and forwards to `noa-api:8000` on the internal Docker network.

**Spec refs:** SPEC.md §29.4 (Connection Security — HTTPS over LAN/VPN), §7.1 (Phase 1 network topology), §20.1 (Docker network isolation)

**Depends on:** DE1
**Blocks:** GO1, GO2, GO3

**Deliverables:**
1. `docker/caddy/Caddyfile` — HTTPS with automatic Let's Encrypt, HTTP→HTTPS redirect, HSTS
2. `docker-compose.yml` updated — `caddy` service added, `noa-api` port restricted to internal network
3. `src/noa/api/app.py` — CORS origins updated to accept `NOA_DOMAIN` env var
4. `docs/TLS_SETUP.md` — operator runbook: DNS setup, Tailscale variant, dev self-signed fallback

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `docker/caddy/Caddyfile` | **CREATE** | `{$NOA_DOMAIN}` block: `reverse_proxy noa-api:8000`, HSTS header, `tls internal` for dev |
| `docker-compose.yml` | **EDIT** | Add `caddy` service (caddy:2-alpine), ports 80+443, caddy-data volume; remove host port from noa-api |
| `src/noa/api/app.py` | **EDIT** | Read `NOA_DOMAIN` env var; add `https://{NOA_DOMAIN}` to CORS allow_origins |
| `docs/TLS_SETUP.md` | **CREATE** | Step-by-step DNS + Caddy setup; Tailscale variant; dev with `tls internal` |
| `tests/unit/test_de2_tls.py` | **CREATE** | Validate Caddyfile directives, CORS config, compose service shape |

**Tests (~10):**
- Caddyfile contains `reverse_proxy noa-api:8000`
- Caddyfile contains `Strict-Transport-Security` header directive
- Caddyfile uses `{$NOA_DOMAIN}` placeholder (not hardcoded domain)
- CORS config accepts `https://{NOA_DOMAIN}` when env var is set
- CORS config does not allow `*` in production mode
- docker-compose `caddy` service uses `caddy:2-alpine` image
- docker-compose `caddy` service mounts `caddy-data` volume
- docker-compose `noa-api` no longer exposes port directly to host
- HTTP→HTTPS redirect documented in Caddyfile or docs
- `docs/TLS_SETUP.md` exists and is non-empty

**Test gate:**
```bash
pytest tests/unit/test_de2_tls.py -v
```

---

### Phase DE3: Worker Container Hardening (~45 min)

**Goal:** Private and external worker containers have explicit restart policies, resource limits, and health checks per SPEC §8.1/§8.2 — the system recovers automatically from worker crashes and the orchestrator never silently uses a degraded worker.

**Spec refs:** SPEC.md §8.1 (Private Container hardening), §8.2 (External Container hardening), §30 (Resource Management), §31 (Failure Handling)

**Depends on:** DE1
**Blocks:** None

**Deliverables:**
1. `docker-compose.yml` — resource limits for private-worker and external-worker per §30
2. `docker/private-worker/Dockerfile` — `HEALTHCHECK` instruction added
3. `docker/external-worker/Dockerfile` — same
4. `src/noa/api/app.py` — startup probe: logs WARNING and sets `app.state.workers_degraded` if worker unreachable

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `docker-compose.yml` | **EDIT** | private-worker: `cpus: "4.0"`, `memory: 32g`, `restart: unless-stopped`, `start_period: 60s`; external-worker: `cpus: "2.0"`, `memory: 4g`, same restart |
| `docker/private-worker/Dockerfile` | **EDIT** | Add `HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8001/health` |
| `docker/external-worker/Dockerfile` | **EDIT** | Add `HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8002/health` |
| `src/noa/api/app.py` | **EDIT** | Lifespan startup: probe worker health endpoints; log WARNING and set `app.state.workers_degraded = True` if unreachable |
| `tests/unit/test_de3_hardening.py` | **CREATE** | Parse compose YAML; validate limits, restart policies, healthcheck start_period; test degraded-mode flag |

**Tests (~10):**
- private-worker has `cpus: "4.0"` and `memory: 32G` resource limits
- private-worker has `restart: unless-stopped`
- private-worker healthcheck has `start_period` ≥30s
- external-worker has `cpus: "2.0"` and `memory: 4g` resource limits
- external-worker has `restart: unless-stopped`
- external-worker healthcheck has `start_period` ≥30s
- private-worker Dockerfile contains `HEALTHCHECK` instruction
- external-worker Dockerfile contains `HEALTHCHECK` instruction
- Startup probe: `app.state.workers_degraded = True` when worker returns 503
- Startup proceeds (no exception) when worker is unreachable

**Test gate:**
```bash
pytest tests/unit/test_de3_hardening.py -v
```

---

### Phase DE4: Backup Verification Automation (~45 min)

**Goal:** The backup container not only writes encrypted dumps but also periodically verifies that the most recent backup can be fully restored — satisfying SPEC §10.5 "weekly restore test to ensure backup integrity." A `GET /health/backup` endpoint exposes the last verify result for monitoring.

**Spec refs:** SPEC.md §10.5 (Backup Strategy — weekly restore test), §34 (Testing Requirements — verify Postgres backup and restore)

**Depends on:** DE1
**Blocks:** None

**Deliverables:**
1. `docker/backup/verify_backup.sh` — restore latest backup to temp Postgres, run schema/row-count check, write `verify_status.json`
2. `docker/backup/Dockerfile` — adds verify script and weekly cron entry
3. `src/noa/api/v1/health.py` — `GET /health/backup` endpoint reads `verify_status.json` from volume mount
4. `docker-compose.yml` — mounts `backups` volume into `noa-api` read-only for health endpoint

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `docker/backup/verify_backup.sh` | **CREATE** | Find latest `.gpg`, decrypt to tmpfs, pg_restore into temp DB, row-count check, write verify_status.json |
| `docker/backup/Dockerfile` | **EDIT** | COPY verify script; add cron: `0 3 * * 0 /verify_backup.sh` |
| `src/noa/api/v1/health.py` | **EDIT** | Add `GET /health/backup`: read `/backups/verify_status.json`, return `{last_backup, last_verify, status, backup_age_hours}` |
| `docker-compose.yml` | **EDIT** | Mount `backups` volume into `noa-api` as read-only at `/backups` |
| `tests/unit/test_de4_backup_verify.py` | **CREATE** | Health endpoint with mocked status file (ok/failed/missing); verify script logic; cron schedule in Dockerfile |

**Tests (~12):**
- Health endpoint returns `status: "ok"` when verify_status.json reports ok
- Health endpoint returns `status: "failed"` when verify_status.json reports failure
- Health endpoint returns `status: "never_run"` when verify_status.json is absent
- Health endpoint returns HTTP 200 in all cases
- verify_backup.sh: finds most recent `.gpg` file by mtime
- verify_backup.sh: exits non-zero when pg_restore fails
- verify_backup.sh: writes verify_status.json with `timestamp` field after success
- verify_backup.sh: writes `status: "failed"` to verify_status.json on restore failure
- Dockerfile cron entry: `0 3 * * 0` weekly schedule
- docker-compose: `noa-api` mounts `backups` volume read-only
- Schema check: verify script includes table-count check (not just pg_restore exit code)
- Backup age: health endpoint includes `backup_age_hours`; >25h triggers `status: "stale"`

**Test gate:**
```bash
pytest tests/unit/test_de4_backup_verify.py -v
```

---

### Phase GO1: Google OAuth2 Backend (~75 min)

**Goal:** Users can connect their Google account via OAuth2 consent. The resulting tokens are persisted encrypted in the `google_credentials` table. Calendar and Gmail tools automatically switch from env-var tokens to DB-stored OAuth tokens, so authorization survives container restarts.

**Spec refs:** SPEC.md §12.1 (Google Calendar — OAuth2 scopes), §12.2 (Gmail — OAuth2 scopes), §11.1 (Google OAuth2 refresh token in Postgres encrypted column), §11.3 (refresh tokens rotate on each use), §5.3 (Authentication Flow)

**Depends on:** DE2 (HTTPS required for Google OAuth2 redirect URIs)
**Blocks:** GO2, GO3

**Deliverables:**
1. `GET /api/v1/auth/google/authorize` — returns `{"auth_url": "..."}` with Calendar+Gmail scopes; requires JWT auth
2. `GET /api/v1/auth/google/callback` — exchanges code, persists encrypted tokens, redirects to `{NOA_DOMAIN}/settings?google=connected`; also supports `noaapp://` redirect scheme for iOS
3. `GET /api/v1/auth/google/status` — returns `{"connected": bool, "scopes": [...]}`
4. `DELETE /api/v1/auth/google/disconnect` — deletes `google_credentials` row, clears live client
5. `src/noa/tools/registration.py` updated — loads tokens from DB first, falls back to env var; fixes `uuid.UUID(int=0)` placeholder
6. CSRF protection: state parameter round-trip on authorize/callback

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/api/v1/auth.py` | **EDIT** | Add 4 OAuth routes: `GET /google/authorize`, `GET /google/callback`, `GET /google/status`, `DELETE /google/disconnect` |
| `src/noa/tools/registration.py` | **EDIT** | Load Google tokens from `google_credentials` DB table by user_id at startup; fix `uuid.UUID(int=0)` placeholder |
| `src/noa/tools/google_auth.py` | **EDIT** | Add `load_tokens_from_db(session, user_id)` coroutine |
| `tests/unit/test_go1_oauth_backend.py` | **CREATE** | Full test coverage of all 4 endpoints + token loading logic |

**Tests (~20):**
- `GET /google/authorize` returns 200 with `auth_url` containing `accounts.google.com`
- `GET /google/authorize` requires valid JWT (401 without token)
- `GET /google/authorize` includes calendar + gmail scopes
- `GET /google/authorize` sets `access_type=offline` and `prompt=consent`
- `GET /google/callback` with valid code: persists encrypted tokens to `google_credentials`
- `GET /google/callback` with valid code: redirects to `{NOA_DOMAIN}/settings?google=connected`
- `GET /google/callback` with invalid code: returns 400
- `GET /google/callback` with `?error=access_denied`: returns 400
- `GET /google/status` returns `{"connected": true}` after successful exchange
- `GET /google/status` returns `{"connected": false}` when no row exists
- `DELETE /google/disconnect` removes `google_credentials` row
- `DELETE /google/disconnect` clears tokens from live GoogleAuthClient
- `DELETE /google/disconnect` returns 404 when no credentials to disconnect
- Token persistence: row stores encrypted tokens (not plaintext)
- `load_tokens_from_db` decrypts and calls `set_tokens()` on the client
- `load_tokens_from_db` falls back gracefully when DB row is absent
- Token rotation: new refresh token overwrites DB row
- Registration startup loads DB tokens before falling back to env var
- Multi-user safety: status/disconnect scoped to authenticated `user_id`
- CSRF: state parameter generated on authorize, verified on callback

**Test gate:**
```bash
pytest tests/unit/test_go1_oauth_backend.py -v
```

---

### Phase GO2: Web UI — Connect Google (~45 min)

**Goal:** The Settings page shows Google connection status and lets the user connect or disconnect with a single click. Connecting opens the OAuth consent flow; the callback page closes the loop and refreshes status.

**Spec refs:** SPEC.md §12.1, §12.2 (Calendar/Gmail OAuth2), §29.2 (Web UI)

**Depends on:** GO1
**Blocks:** None

**Deliverables:**
1. `web/src/pages/Settings.tsx` — "Google Account" section: status badge, "Connect Google" button, "Disconnect" button
2. `web/src/pages/GoogleCallback.tsx` — new page at `/auth/google/callback`: shows success/error, auto-redirects to `/settings`
3. `web/src/App.tsx` — route `/auth/google/callback` added

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `web/src/pages/Settings.tsx` | **EDIT** | Add Google section: query status, show badge, connect/disconnect buttons |
| `web/src/pages/GoogleCallback.tsx` | **CREATE** | Reads URL params, shows success/error, redirects to `/settings` after 2s |
| `web/src/App.tsx` | **EDIT** | Add `<Route path="/auth/google/callback" element={<GoogleCallback />} />` |
| `web/src/test/go2-google-connect.test.tsx` | **CREATE** | Vitest/RTL tests for Settings Google section and callback page |

**Tests (~12):**
- Settings renders "Not connected" when status returns `connected: false`
- Settings renders "Connected" badge when status returns `connected: true`
- "Connect Google" button calls authorize endpoint and navigates to `auth_url`
- "Connect Google" shows loading state during fetch
- "Disconnect" button calls disconnect endpoint
- "Disconnect" only shown when connected
- After disconnect, status refreshes to "Not connected"
- GoogleCallback shows success message when `?google=connected` in URL
- GoogleCallback shows error when `?error=access_denied` in URL
- GoogleCallback redirects to `/settings` after 2s
- Route `/auth/google/callback` renders GoogleCallback
- Settings Google section is within existing Settings page layout

**Test gate:**
```bash
cd web && npm test -- go2-google-connect
```

---

### Phase GO3: iOS — OAuth2 via ASWebAuthenticationSession (~60 min)

**Goal:** iOS users can connect their Google account from the app's Settings tab. The consent flow runs in `ASWebAuthenticationSession` (no app switching). The backend (GO1) handles token persistence; iOS stores nothing sensitive — only the Noa JWT is in Keychain.

**Spec refs:** SPEC.md §29.3 (Mobile Access — OAuth2 device flow + biometric unlock), §11.1 (credentials in Keychain/Postgres), §12.1, §12.2

**Depends on:** GO1
**Blocks:** None

**Redirect flow:** `ASWebAuthenticationSession` uses the backend callback URL. Backend (GO1) persists tokens then redirects to `noaapp://auth/google/connected` (custom scheme). Session intercepts `noaapp://` and completes. iOS re-fetches status to confirm.

**Deliverables:**
1. `ios/Noa/Sources/Noa/Services/GoogleAuthService.swift` — actor; `connect()` starts `ASWebAuthenticationSession`; `disconnect()` calls DELETE endpoint; `getStatus()` calls status endpoint
2. `ios/Noa/Sources/Noa/ViewModels/SettingsViewModel.swift` — `@Observable`; `googleStatus`, `connectGoogle()`, `disconnectGoogle()`
3. `ios/Noa/Sources/Noa/Views/Settings/SettingsView.swift` — Google section with status badge, connect (biometric guard for medium-risk action), disconnect confirmation
4. `ios/Noa/Sources/Noa/Views/MainTabView.swift` — Settings tab added

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Sources/Noa/Services/GoogleAuthService.swift` | **CREATE** | Actor: connect via ASWebAuthenticationSession, disconnect, getStatus |
| `ios/Noa/Sources/Noa/ViewModels/SettingsViewModel.swift` | **CREATE** | @Observable: googleStatus, connect/disconnect/loadStatus |
| `ios/Noa/Sources/Noa/Views/Settings/SettingsView.swift` | **CREATE** | SwiftUI: Google section, biometric guard on connect, disconnect confirmation sheet |
| `ios/Noa/Sources/Noa/Views/MainTabView.swift` | **EDIT** | Add Settings tab |
| `ios/Noa/Package.swift` | **EDIT** | Register AuthenticationServices framework if not present |
| `ios/Noa/Tests/NaoTests/GoogleAuthServiceTests.swift` | **CREATE** | Protocol-injected ASWebAuthenticationSession for testability |

**Tests (~15):**
- `connect()` calls authorize endpoint to get auth URL
- `connect()` starts ASWebAuthenticationSession with returned URL
- `connect()` uses `noaapp://` as callback scheme
- Completion with `noaapp://auth/google/connected` → status refreshes to `.connected`
- Session cancellation → status remains `.disconnected`, no error
- Session error → user-facing error message shown
- `disconnect()` calls DELETE endpoint
- `disconnect()` sets `googleStatus` to `.disconnected` on success
- `SettingsViewModel` loads status on `init()`
- `SettingsViewModel` exposes `.loading` state during in-flight requests
- `SettingsView` shows "Connected" badge when `.connected`
- `SettingsView` shows "Connect Google" when `.disconnected`
- `SettingsView` shows biometric confirmation before `connect()`
- `SettingsView` shows disconnect confirmation sheet
- Google tokens never stored in iOS Keychain or UserDefaults

**Test gate:**
```bash
cd ios/Noa && swift test --filter GoogleAuthServiceTests
```

---

# Wave 21: Pipeline Excellence & Quality Infrastructure

**Goal:** Close every gap identified in the pipeline evaluation. Consume the full CI backlog, eliminate mypy debt, close all open findings, upgrade test infrastructure to real Postgres, add traceability, and introduce coverage/mutation/flaky detection tooling. Target: pipeline score 9→10.

**Motivation:** The pipeline generates excellent insights (retros, CI analyses, findings) but has accumulated structural debt — 27 unapplied CI proposals, 51 mypy errors, 10 open findings, mock-heavy tests, no coverage metrics. This wave converts diagnosis into action.

---

## QE1: CI Backlog Triage & Process Gate Application

**Spec refs:** Pipeline evaluation §5 (Continuous Improvement), CI-001 through CI-029

**Goal:** Apply, reject, or defer every pending CI proposal. Zero PROPOSED items remaining in IMPROVEMENT_BACKLOG.md.

**Scope:**

Apply (P1 — all 7):
- CI-001/002/003: CLAUDE.md sections (implementation-first bias, canonical output locations, Docker environment awareness)
- CI-013: M5b (Findings Currency) gate → QA_CHECKLIST.md
- CI-016: S5 escalation rule (integration test baseline) → CLAUDE.md
- CI-017: M8b (Cross-Language Field Optionality) gate → QA_CHECKLIST.md
- CI-020: FINDINGS.md drift escalation → CLAUDE.md
- CI-022: L14 already applied by PR7 — mark APPLIED
- CI-025: iOS-backend contract audit — already applied by PR7 — mark APPLIED

Apply (P2 — all 12):
- CI-004: Key directories table → CLAUDE.md
- CI-008: M4b (Mock Interface Accuracy) gate → QA_CHECKLIST.md
- CI-010: S5 escalation rule → QA_CHECKLIST.md
- CI-011: M3b (Write-Path User Scoping check) → QA_CHECKLIST.md
- CI-012: S5b (Frontend Behavioral Coverage) gate → QA_CHECKLIST.md
- CI-014: M2b (Write-Path Test Fidelity) gate → QA_CHECKLIST.md
- CI-015: Findings Sync as mandatory pipeline step → CLAUDE.md (already partially done)
- CI-018: L13 (Default Resolution at API Boundary) → ARCH_INVARIANTS.md
- CI-023: Pre-phase test plan in implement agent → .claude/agents/implement.md
- CI-024: 2x duration multiplier for multi-platform → .claude/skills/phase-planning/SKILL.md
- CI-026: M5c (Related-Issue Scope Completeness) → QA_CHECKLIST.md
- CI-028: M2c (Source-Inspection Test Gate) → QA_CHECKLIST.md

Reject/Defer with rationale (P2/P3):
- CI-005: `/wave` skill — DEFER (low ROI, manual PLAN.md updates work fine)
- CI-006: Docker rebuild reminder — REJECT (write-code skill deleted in Wave 18 overhaul)
- CI-007: Auto-test PostToolUse hook — DEFER (latency concern, revisit after Wave 22)
- CI-019: chat.py SSE handler finding — addressed by QE3
- CI-021: FE-L1 ErrorBoundary — addressed by QE3
- CI-029: S5 audit-fix carve-out — APPLY (simple refinement to CI-016)

**Files modified:**
- `CLAUDE.md`
- `Plan/QA_CHECKLIST.md`
- `Plan/ARCH_INVARIANTS.md`
- `.claude/agents/implement.md`
- `.claude/skills/phase-planning/SKILL.md`
- `Plan/CI/IMPROVEMENT_BACKLOG.md`

**Tests (~15):**
- Parse QA_CHECKLIST.md and verify all new M-gates (M5b, M8b, M4b, M3b, M2b, M2c, M5c) are present
- Parse ARCH_INVARIANTS.md and verify L13, L14 exist
- Parse CLAUDE.md for required sections (implementation-first, Docker env, findings sync gate)
- Parse implement.md for pre-phase test plan step
- Verify IMPROVEMENT_BACKLOG.md has zero PROPOSED items
- Verify all P1 items are APPLIED or REJECTED (none PROPOSED)

**Test gate:**
```bash
docker exec noa-dev python -m pytest tests/unit/test_qe1_ci_backlog.py -v
```

---

## QE2: Mypy Zero & Type Safety Enforcement

**Spec refs:** Pipeline evaluation §3 (Code Quality), Wave 19 retro R3

**Goal:** Zero mypy errors. Enforced in CI as a blocking gate.

**Scope:**

1. Fix all 51 mypy errors across 18 files:
   - `app.py`: APNsService/AuditService/ApprovalService constructor type mismatches
   - `success_envelope`: widen type signature to accept `list | dict`
   - `threads.py`: fix Conversation model attribute access
   - All remaining errors (type annotations, Optional handling, return types)

2. Add mypy to CI pipeline:
   - Update `.github/workflows/ci.yml` to run `mypy src/noa/ --ignore-missing-imports` as blocking step
   - Update `pyproject.toml` mypy config: `warn_return_any = true`, `disallow_untyped_defs = true` for new code
   - Add `# type: ignore[specific-code]` only where genuinely needed (e.g., third-party library gaps), never blanket

3. Update pre-push hook to include mypy check

**Files modified:**
- 18 source files with mypy errors
- `pyproject.toml` (mypy config)
- `.github/workflows/ci.yml` (mypy gate)
- `tools/pre-push-hook.sh`

**Tests (~15):**
- `mypy src/noa/ --ignore-missing-imports` returns 0 errors (meta-test)
- Type annotation correctness for fixed functions (parameterized tests on critical paths)
- CI workflow file contains mypy step
- Pre-push hook contains mypy check

**Test gate:**
```bash
docker exec noa-dev python -m mypy src/noa/ --ignore-missing-imports && echo "PASS: 0 errors"
docker exec noa-dev python -m pytest tests/unit/test_qe2_mypy.py -v
```

---

## QE3: Open Findings Closure

**Spec refs:** FINDINGS.md open items, Pipeline evaluation §3

**Goal:** Close all 10 open findings. FINDINGS.md reaches 0 open.

**Scope:**

| Finding | Fix |
|---------|-----|
| BE-H4 (SSE replay cursor list index) | Replace list-index cursor with `run_event.id` DB offset; client sends `Last-Event-ID`, server resumes from that row |
| BE-H5 (chat.py bypasses RunService state machine) | Route `_update_run_status` through `RunService.update_status()` with state transition validation |
| BE-M1 (cost endpoint raw SQL) | Replace raw SQL with SQLAlchemy ORM query using proper column references |
| BE-M5 (MemoryStore user_id) | Already fixed in PR1 — verify and mark resolved (may be stale tracking) |
| FE-M5 (no unsaved-changes warning) | Add `beforeunload` event listener + `useBlocker` for React Router on Settings page |
| FE-L1 (ErrorBoundary stack exposure) | Replace `error.stack` rendering with generic "Something went wrong" + log stack to console only |
| iOS-L1 (hardcoded dev IP) | Move to `Info.plist` / environment config; `Environment.swift` reads from bundle |
| iOS-L2 (DEBUG disables cert pinning) | Add `#if DEBUG` warning log; keep bypass for dev but add runtime assertion that pinning delegate is configured |
| BE-L1 (chat.py SSE handler str(exc)) | Replace `str(exc)` with generic error message in outer SSE handler |
| W19-M6 (mypy errors) | Handled by QE2 — cross-reference and mark resolved |

**Files modified:**
- `src/noa/api/v1/chat.py` (BE-H4, BE-H5, BE-L1)
- `src/noa/api/v1/cost.py` (BE-M1)
- `web/src/pages/Settings.tsx` (FE-M5)
- `web/src/components/ErrorBoundary.tsx` (FE-L1)
- `ios/Noa/Sources/Noa/Configuration/Environment.swift` (iOS-L1)
- `ios/Noa/Sources/Noa/Services/CertificatePinningDelegate.swift` (iOS-L2)
- `Plan/FINDINGS.md` (all 10 rows → Resolved)

**Tests (~20):**
- BE-H4: SSE replay with `Last-Event-ID` returns correct events (skip=0, skip=N)
- BE-H5: status transition through RunService validates state machine
- BE-M1: cost endpoint returns correct data via ORM (no raw SQL)
- FE-M5: Settings page fires beforeunload on dirty state (Playwright or unit test)
- FE-L1: ErrorBoundary renders generic message, not stack
- BE-L1: SSE error event contains generic message, not exception text
- iOS-L1: Environment reads from config, not hardcoded
- iOS-L2: DEBUG build logs pinning bypass warning

**Test gate:**
```bash
docker exec noa-dev python -m pytest tests/unit/test_qe3_findings.py -v
grep -c "Open" Plan/FINDINGS.md  # should be 0 data rows with Open status
```

---

## QE4: Postgres Integration Tests

**Spec refs:** Pipeline evaluation §3 (S5 at 68% OPEN), CI-016, L8

**Goal:** Critical paths tested against real Postgres. No more SQLite-only test suite for DB-touching code.

**Scope:**

1. **Test infrastructure:**
   - Add `testcontainers[postgres]` to dev dependencies
   - New `tests/integration/conftest.py` with Postgres container fixture (auto-start, auto-teardown)
   - Fixture creates schema via Alembic migrations (tests the real migration chain)
   - Session fixture yields real `AsyncSession` against the container

2. **Convert critical test suites** (new files in `tests/integration/`):
   - `test_auth_integration.py`: register, login, token refresh, session management against real DB
   - `test_threads_integration.py`: create, list, delete threads; create/list messages; user scoping
   - `test_settings_integration.py`: PATCH round-trip, field preservation, credential storage
   - `test_approvals_integration.py`: create approval, list pending, decide, expiry
   - `test_memory_integration.py`: store/recall/delete facts, user scoping
   - `test_tools_integration.py`: capability grants, custom tool registration, tool call logging

3. **CI integration:**
   - `.github/workflows/ci.yml` already has Postgres service container — wire `tests/integration/` to use it
   - Add `pytest tests/integration/` as a separate CI job (parallel with unit tests)
   - Integration tests are NOT run by default in `pytest tests/unit/` — separate directory

4. **Conftest update:**
   - Keep existing SQLite conftest for fast unit tests
   - New integration conftest with `@pytest.fixture(scope="session")` for Postgres container

**Files modified:**
- `pyproject.toml` (testcontainers dependency)
- `tests/integration/__init__.py` (new)
- `tests/integration/conftest.py` (new — Postgres fixture)
- `tests/integration/test_auth_integration.py` (new)
- `tests/integration/test_threads_integration.py` (new)
- `tests/integration/test_settings_integration.py` (new)
- `tests/integration/test_approvals_integration.py` (new)
- `tests/integration/test_memory_integration.py` (new)
- `tests/integration/test_tools_integration.py` (new)
- `.github/workflows/ci.yml` (integration test job)

**Tests (~25):**
- 4-5 tests per suite × 6 suites = ~25 integration tests
- All use real Postgres via testcontainers
- All run Alembic migrations as setup (proves migration chain works)
- All verify user scoping (write as user A, read as user B → empty)

**Test gate:**
```bash
docker exec noa-dev python -m pytest tests/integration/ -v --tb=short
```

---

## QE5: Requirements Traceability Matrix

**Spec refs:** Pipeline evaluation §1 (SPEC → PLAN traceability)

**Goal:** Machine-readable mapping from every SPEC section to the phase(s) and test(s) that cover it. Identify orphaned spec sections.

**Scope:**

1. **Traceability script** (`tools/traceability.py`):
   - Parse all test files for docstring citations (pattern: `SPEC.md §X.Y` or `Phase: XX`)
   - Parse PLAN.md for phase→spec mappings
   - Parse PHASE_DETAILS.md for spec refs in each phase description
   - Output: `Plan/TRACEABILITY.md` — table with columns: SPEC Section | Phase(s) | Test File(s) | Status (Covered/Partial/Orphaned)
   - Output: summary counts (covered/partial/orphaned)

2. **SPEC section inventory:**
   - Parse SPEC.md section headers (§1 through §36+)
   - Cross-reference against traceability data
   - Flag orphaned sections (spec requirements with no phase or test coverage)

3. **CI integration:**
   - Add `python tools/traceability.py --check` to CI — fails if orphaned critical sections exist (§1-§25 must all be covered)
   - Non-critical sections (§26+ future/deferred) can be flagged but not blocking

**Files modified:**
- `tools/traceability.py` (new)
- `Plan/TRACEABILITY.md` (new — generated output)
- `.github/workflows/ci.yml` (traceability check step)

**Tests (~10):**
- Script parses a test file with known docstring → correct extraction
- Script identifies orphaned section → correct flagging
- Script generates valid markdown table
- `--check` mode returns non-zero on orphaned critical section
- End-to-end: run against real codebase, verify no critical orphans (or document known gaps)

**Test gate:**
```bash
docker exec noa-dev python tools/traceability.py --check
docker exec noa-dev python -m pytest tests/unit/test_qe5_traceability.py -v
```

---

## QE6: Test Quality Infrastructure (Coverage, Mutation, Flaky Detection)

**Spec refs:** Pipeline evaluation §10 (What Would Get to 10)

**Goal:** Quantifiable test quality metrics. Coverage baselines, mutation testing on critical paths, flaky test detection.

**Scope:**

1. **Coverage (pytest-cov):**
   - Add `pytest-cov` to dev dependencies
   - Configure in `pyproject.toml`: `--cov=src/noa --cov-report=term-missing --cov-report=html`
   - Set minimum threshold: 70% line coverage (realistic baseline for current state)
   - CI: coverage report uploaded as artifact; fail if below threshold
   - Generate `htmlcov/` (gitignored) for local browsing

2. **Mutation testing (mutmut):**
   - Add `mutmut` to dev dependencies
   - Configure for critical paths only (keep runtime reasonable):
     - `src/noa/auth/` (JWT, middleware)
     - `src/noa/orchestrator/nodes/router.py` (privacy routing)
     - `src/noa/tools/gateway.py` (tool dispatch, rate limiting)
   - Generate baseline mutation score
   - CI: run mutation tests on critical paths only (not full codebase — too slow)
   - Document baseline scores in `Plan/TRACEABILITY.md` alongside coverage

3. **Flaky test detection (pytest-repeat):**
   - Add `pytest-repeat` to dev dependencies
   - CI: nightly job runs `pytest --count=3 tests/unit/` — any test that fails on repeat is flagged
   - Local: `pytest --count=5 tests/unit/test_suspect.py` for targeted investigation

4. **Performance baselines:**
   - Add `pytest-benchmark` for key endpoint response times (optional, low priority)
   - Baseline: `/api/v1/health` < 50ms, `/api/v1/chat` first-byte < 200ms
   - Store baselines in `tests/benchmarks/` (gitignored results, committed config)

**Files modified:**
- `pyproject.toml` (new dev dependencies, coverage config, mutmut config)
- `.github/workflows/ci.yml` (coverage step, nightly flaky job)
- `.gitignore` (htmlcov/, .mutmut-cache/)
- `tests/conftest.py` (coverage plugin registration if needed)
- `mutmut_config.py` (new — paths to mutate)

**Tests (~15):**
- Coverage runs and produces report (meta-test: `pytest --cov=src/noa` succeeds)
- Coverage threshold is enforced (test that `--cov-fail-under=70` is in config)
- mutmut can run on auth module without errors (smoke test)
- pytest-repeat runs 3x on a known-stable test (verify no false positives)
- CI workflow contains coverage and nightly-flaky jobs

**Test gate:**
```bash
docker exec noa-dev python -m pytest tests/unit/ --cov=src/noa --cov-fail-under=70 --tb=short
docker exec noa-dev python -m pytest tests/unit/test_qe6_quality.py -v
```

---

## MS1: Microsoft Outlook Mail + Calendar (OAuth2 + Graph API)

**Spec refs:** SPEC §11 (OAuth2 / credential management), §8.3 (tool integration), §36 (build order)

**Goal:** Add Microsoft Outlook as a mail and calendar provider alongside the existing Google integration. Full OAuth2 flow (Azure AD v2.0), encrypted token storage, HTTP clients for Microsoft Graph API, tool registration, Web UI "Connect Microsoft" section, iOS OAuth via ASWebAuthenticationSession.

**Architecture:** Clone the proven Google OAuth pattern (GO1/GO2/GO3 + GT1/GT2). Same gateway, same encryption, same 401-retry pattern. Microsoft-specific differences handled in dedicated clients.

### Microsoft Graph API Reference

**OAuth2 Endpoints (Azure AD v2.0):**
- Authorize: `https://login.microsoftonline.com/common/oauth2/v2.0/authorize`
- Token: `https://login.microsoftonline.com/common/oauth2/v2.0/token`
- Scopes: `Mail.ReadWrite Mail.Send Calendars.ReadWrite offline_access` (simple strings, NOT full URLs like Google)

**Graph API Base:** `https://graph.microsoft.com/v1.0`

**Mail endpoints:**
- `GET /me/messages` — list messages (`$select`, `$top`, `$skip`, `$search`, `$orderby`)
- `GET /me/messages/{id}` — get full message with body
- `POST /me/sendMail` — send email (returns 202 Accepted, no body)
- `POST /me/mailFolders('drafts')/messages` — create draft

**Calendar endpoints:**
- `GET /me/calendar/calendarView?startDateTime=...&endDateTime=...` — list events in range (handles recurrence)
- `POST /me/calendar/events` — create event
- `PATCH /me/calendar/events/{id}` — update event
- `DELETE /me/calendar/events/{id}` — delete event (204 No Content)

**Key differences from Google:**
| Aspect | Google | Microsoft |
|--------|--------|-----------|
| Scopes | Full URLs (`https://www.googleapis.com/auth/...`) | Simple strings (`Mail.ReadWrite`) |
| Offline access | `access_type=offline` param | `offline_access` scope |
| Refresh token rotation | Rotates on use | Does NOT rotate (90-day inactivity expiry) |
| Pagination | `nextPageToken` param | `@odata.nextLink` URL in response |
| Calendar date range | `timeMin`/`timeMax` params | `startDateTime`/`endDateTime` params |
| Date format | ISO 8601 string | `{"dateTime": "...", "timeZone": "UTC"}` object |
| Token exchange | `application/x-www-form-urlencoded` | Same (form-encoded) |
| API calls | Mixed encoding | Always JSON body for POST/PATCH |
| Error response | `{error, error_description}` | `{error, error_description, error_codes[], timestamp, trace_id}` |

### Scope

**1. Backend: OAuth2 flow (clone GO1 pattern)**
- `src/noa/tools/microsoft_auth.py` — `MicrosoftAuthClient` (authorize URL, code exchange, token refresh)
  - `get_auth_url(scopes)` → authorization URL with CSRF state
  - `exchange_code(code)` → POST to Azure AD token endpoint
  - `refresh_access_token()` → refresh grant (no rotation — check `if "refresh_token" in response`)
  - `on_token_change` callback for DB persistence
- `src/noa/api/v1/auth.py` — 4 new routes:
  - `GET /api/v1/auth/microsoft/authorize` — generate auth URL, CSRF state (10-min TTL)
  - `GET /api/v1/auth/microsoft/callback` — exchange code, encrypt & persist tokens, redirect (iOS: `noaapp://oauth/callback?microsoft=connected`, web: `/settings?microsoft=connected`)
  - `GET /api/v1/auth/microsoft/status` — `{"connected": bool}`
  - `DELETE /api/v1/auth/microsoft/disconnect` — delete credential row, clear live client

**2. Backend: DB model + migration**
- `src/noa/db/models/microsoft_credential.py` — `MicrosoftCredential` (user_id FK, access_token_enc, refresh_token_enc, updated_at)
- `alembic/versions/018_microsoft_credentials.py` — create `microsoft_credentials` table
- Reuse `_token_crypto.py` (Fernet encryption, same `SECRET_KEY`)

**3. Backend: HTTP clients (clone GT2 pattern)**
- `src/noa/tools/outlook_client.py` — `OutlookClient`
  - `list_messages(max_results=50)` — GET `/me/messages` with `$select`, `$top`, `$orderby`
  - `get_message(message_id)` — GET `/me/messages/{id}` (full body)
  - `send_email(to, subject, body, cc=None)` — POST `/me/sendMail`
  - `draft_email(to, subject, body)` — POST `/me/mailFolders('drafts')/messages`
  - `search_emails(query, max_results=50)` — GET `/me/messages?$search="{query}"`
  - 401 auto-retry with `refresh_access_token()`
- `src/noa/tools/outlook_calendar_client.py` — `OutlookCalendarClient`
  - `list_events(start_date, end_date)` — GET `/me/calendar/calendarView`
  - `create_event(title, start, end, description="", attendees=None)` — POST `/me/calendar/events`
  - `update_event(event_id, **changes)` — PATCH `/me/calendar/events/{id}`
  - `delete_event(event_id)` — DELETE `/me/calendar/events/{id}`
  - 401 auto-retry with `refresh_access_token()`

**4. Backend: Tool wrappers + registration**
- `src/noa/tools/outlook_mail.py` — `OutlookMailTool(ToolInterface)` (list_emails, read_email, send_email, draft_email, search_emails)
- `src/noa/tools/outlook_calendar.py` — `OutlookCalendarTool(ToolInterface)` (list_events, create_event, update_event, delete_event)
- `src/noa/tools/registration.py` — `_register_microsoft_tools()`:
  - Check `MICROSOFT_CLIENT_ID` + `MICROSOFT_CLIENT_SECRET` env vars
  - Create `MicrosoftAuthClient` with `on_token_change` callback
  - Load tokens from DB (fire-and-forget async), fallback to `MICROSOFT_REFRESH_TOKEN` env
  - Register `outlook_mail` and `outlook_calendar` tools in gateway
  - Store `app.state.microsoft_auth_client` for live token updates

**5. Web UI: Connect Microsoft (clone GO2 pattern)**
- `web/src/pages/Settings.tsx` — `MicrosoftAuthSection` component:
  - Query `/api/v1/auth/microsoft/status` on mount
  - "Connect Microsoft" / "Disconnect" button
  - Handle `?microsoft=connected` query param
- `web/src/pages/MicrosoftCallback.tsx` — redirect handler page
- Route: `/auth/microsoft/callback`

**6. iOS: OAuth via ASWebAuthenticationSession (clone GO3 pattern)**
- `Noa/Services/MicrosoftAuthService.swift` — actor with `WebAuthSessionProviding` protocol
  - `connect()` → open ASWebAuthenticationSession to `/auth/microsoft/authorize`
  - `disconnect()` → DELETE `/auth/microsoft/disconnect`
  - `checkStatus()` → GET `/auth/microsoft/status`
- `Noa/ViewModels/SettingsViewModel.swift` — add `microsoftConnected`, `connectMicrosoft()`, `disconnectMicrosoft()`
- `Noa/Views/SettingsView.swift` — Microsoft section (connect/disconnect/status)

**7. Environment variables:**
- `MICROSOFT_CLIENT_ID` — Azure AD app registration client ID
- `MICROSOFT_CLIENT_SECRET` — Azure AD client secret
- `MICROSOFT_REDIRECT_URI` — default `http://localhost:8000/api/v1/auth/microsoft/callback`

**Files created:**
- `src/noa/tools/microsoft_auth.py`
- `src/noa/tools/outlook_client.py`
- `src/noa/tools/outlook_calendar_client.py`
- `src/noa/tools/outlook_mail.py`
- `src/noa/tools/outlook_calendar.py`
- `src/noa/db/models/microsoft_credential.py`
- `alembic/versions/018_microsoft_credentials.py`
- `web/src/pages/MicrosoftCallback.tsx`
- `Noa/Services/MicrosoftAuthService.swift`
- `tests/unit/test_ms1_microsoft_oauth.py`
- `tests/unit/test_ms1_outlook_clients.py`
- `tests/unit/test_ms1_outlook_tools.py`

**Files modified:**
- `src/noa/api/v1/auth.py` (add 4 Microsoft routes)
- `src/noa/tools/registration.py` (add `_register_microsoft_tools()`)
- `src/noa/db/models/__init__.py` (export MicrosoftCredential)
- `web/src/pages/Settings.tsx` (add MicrosoftAuthSection)
- `web/src/App.tsx` (add `/auth/microsoft/callback` route)
- `Noa/ViewModels/SettingsViewModel.swift` (add Microsoft state/actions)
- `Noa/Views/SettingsView.swift` (add Microsoft section)

**Tests (~30):**
- OAuth2 code exchange sends correct POST params to Azure AD token endpoint
- Token refresh sends `grant_type=refresh_token`, does NOT expect rotation
- Auth URL contains correct scopes (simple strings, not URLs)
- CSRF state validation (valid, expired, missing)
- Encrypted token persistence to `microsoft_credentials` table
- Token decryption and live client update on callback
- Disconnect deletes DB row and clears live client
- Status endpoint returns `{"connected": true/false}`
- OutlookClient: list_messages returns parsed messages
- OutlookClient: send_email sends correct JSON body, expects 202
- OutlookClient: 401 triggers refresh and retry
- OutlookCalendarClient: list_events with date range (`calendarView`)
- OutlookCalendarClient: create_event with attendees
- OutlookCalendarClient: update_event via PATCH
- OutlookCalendarClient: delete_event expects 204
- OutlookCalendarClient: date format uses `{"dateTime", "timeZone"}` object
- Pagination follows `@odata.nextLink` (not `nextPageToken`)
- Tool registration skipped when env vars missing
- Tool functions have correct capabilities/risk_tier
- Frontend: MicrosoftAuthSection renders status, connect/disconnect
- iOS: MicrosoftAuthService connect/disconnect/checkStatus
- Token values never appear in logs (SPEC §11.2)

**Estimate:** ~3-4 hours (mostly cloning existing Google patterns with Microsoft-specific adjustments)

**Test gate:**
```bash
docker exec noa-dev python -m pytest tests/unit/test_ms1_microsoft_oauth.py tests/unit/test_ms1_outlook_clients.py tests/unit/test_ms1_outlook_tools.py -v
cd web && npm test -- --watchAll=false
```

**Azure AD setup prerequisite (one-time, manual):**
1. Go to portal.azure.com → App registrations → New registration
2. Add redirect URIs: `http://localhost:8000/api/v1/auth/microsoft/callback` (dev), production URL (prod)
3. Certificates & secrets → New client secret
4. API permissions → Add: `Mail.ReadWrite`, `Mail.Send`, `Calendars.ReadWrite`, `offline_access`
5. Copy Client ID + Client Secret → set as env vars

---

## Phase AU1 — Auth Stability: Login That Just Works

**Goal:** Permanently fix the daily "Login failed - Session expired" cycle for a single-user personal system. Four concrete changes: remove login rate limiting, make tokens long-lived, fix error propagation from the login endpoint, add a startup session check. After this phase, you log in once and it works for 7 days with no lockouts and no misleading error messages.

**Findings addressed:** AUTH-H1, AUTH-H2, AUTH-M1, AUTH-M2

**Root cause summary (why it keeps happening):**

1. **Rate limiting locks you out.** 5 wrong password attempts → 30-minute lockout. Single user on a private network — this protects nobody and punishes you.
2. **Tokens expire too quickly.** Access token: 15 minutes. Every 15 minutes the refresh dance fires. If refresh fails for any reason (expired refresh token, container restart invalidated session, network blip) → "Session expired."
3. **Wrong error on login failure.** `apiRequest`'s 401-retry handler fires even for the login endpoint. Wrong password → 401 → retry-refresh → refresh fails → throws "Session expired." The real error ("Invalid email or password") is discarded.
4. **localStorage flag desyncs from cookies.** App loads, localStorage says authenticated, cookies are actually expired → first API call fails → "Session expired" redirect before you've done anything. No startup check verifies the session is real.

**Deliverables:**

1. **Remove login rate limiting** — delete `_check_rate_limit()`, `_record_failed_attempt()`, `_failed_attempts`, `_lockout_until`, and the `AccountLockedError` import from `src/noa/auth/service.py`. Remove the `AccountLockedError` handler from the login endpoint in `auth.py`. Single-user personal system — no lockout needed.

2. **Extend token lifetimes** — in `src/noa/config.py`: change `access_token_expire_minutes` default from `30` to `10080` (7 days). Change `refresh_token_expire_days` default from `7` to `90`. Also update `max_age` in `_set_auth_cookies()` in `auth.py` to match: access cookie `max_age=7*24*3600`, refresh cookie `max_age=90*24*3600`. You now log in once, it works for 7 days minimum.

3. **`GET /api/v1/auth/me` endpoint** — thin authenticated endpoint returning `{"user_id": "...", "email": "..."}`. Returns 200 if session cookies are valid, 401 if not. Uses existing `require_auth` dep.

4. **`AuthProvider` startup session check** — on mount, call `GET /api/v1/auth/me` directly via `fetch` (not `apiRequest` — avoids circular retry logic). If 200: `setIsAuthenticated(true)`. If anything else: clear localStorage flag, `setIsAuthenticated(false)`. Hold `isLoading = true` until the check resolves.

5. **`AuthGuard` loading state** — while `isLoading === true`, render a neutral spinner. Prevents the flash of "authenticated" content before the check completes.

6. **Exempt auth endpoints from the 401-retry in `apiRequest`** — add `skipAuthRetry?: boolean` to `apiRequest` options. When true, a 401 is treated as a normal error: read `detail` from the response body and throw it directly. Pass `skipAuthRetry: true` from `AuthContext.login()` and `ForgotPassword`. Wrong password now shows "Invalid email or password." Expired reset token shows "Invalid or expired reset token."

7. **Remove the localStorage `noa_authenticated` flag** — once the `/auth/me` startup check is the source of truth, the flag is redundant and the source of the desync. Delete it. `tokens.ts` becomes a stub file (or is removed with callers updated). Auth state lives in React state only.

**Files to modify:**
- `src/noa/auth/service.py` — remove rate limiting (deliverable 1)
- `src/noa/auth/service.py` — remove `AccountLockedError`
- `src/noa/config.py` — extend token lifetimes (deliverable 2)
- `src/noa/api/v1/auth.py` — update cookie `max_age`, add `/me` endpoint, remove `AccountLockedError` handler
- `web/src/auth/AuthContext.tsx` — startup `/auth/me` check + `isLoading` state (deliverable 4)
- `web/src/auth/AuthGuard.tsx` — spinner while `isLoading` (deliverable 5)
- `web/src/auth/tokens.ts` — remove localStorage flag (deliverable 7)
- `web/src/api/client.ts` — `skipAuthRetry` option (deliverable 6)
- `web/src/pages/ForgotPassword.tsx` — pass `skipAuthRetry: true`

**Files NOT to modify:**
- `src/noa/auth/jwt.py` — token structure unchanged
- `src/noa/auth/password.py` — bcrypt unchanged
- `src/noa/auth/middleware.py` — cookie reading unchanged

**Tests:**
- Login with wrong password → shows "Invalid email or password" (not "Session expired")
- Login with correct password → `isAuthenticated = true`
- Login after N wrong attempts → still works immediately (no lockout)
- `GET /api/v1/auth/me` with valid session → 200 + user info
- `GET /api/v1/auth/me` without cookies → 401
- App load with stale localStorage + no cookies → clean redirect to `/login`, no error toast
- App load with valid session → stays authenticated
- Logout → next `/auth/me` → 401 → `isAuthenticated = false`
- Access token cookie max_age is 7 days (604800s)
- Refresh token cookie max_age is 90 days

**Test gate:**
```bash
docker exec noa-dev python -m pytest tests/unit/test_au1_auth_stability.py -v
cd web && npm test -- --testPathPattern="au1|auth|AuthContext|AuthGuard|client" --watchAll=false
```

**Estimate:** ~60 min

**Non-goals (explicitly out of scope):**
- iOS auth changes (iOS Keychain + AuthViewModel handles its own session)
- DB-backed rate limiting (removed entirely for single-user)
- Multi-user considerations

---

## Wave 23: Code Quality — Target 9/10

Triggered by codebase audit 2026-03-16 (see `docs/CODEBASE_AUDIT_2026-03-16.md`).
Current scores: Architecture 7, Wiring 5, Hygiene 6, Security 8, Testing 7, Modern Practices 7, Frontend 7.
Target: All dimensions >= 9/10.

Execution order: CQ1+CQ3+CQ4 parallel → CQ2 (after CQ1) → CQ5 (after CQ3) → CQ6 (after CQ4) → CQ7 (after CQ1) → CQ8 (after CQ6) → CQ9 (after CQ8).

---

### Phase CQ1: Wire Unwired Features (~60 min)

**Goal:** Connect the 4 features that are built but not wired into the execution path.

**Depends on:** None
**Blocks:** CQ2, CQ7

**Deliverables:**

1. **Wire `capability_checker` to gateway at startup**
   - Refactor `DbCapabilityChecker.__init__` to accept `session_factory` instead of single `session`.
   - Each `has_capability()` call opens its own session, checks, closes.
   - In `app.py` `wire_llm_pipeline()`, after gateway creation, set `gateway.capability_checker = DbCapabilityChecker(sf)`.

2. **Wire `load_custom_tools()` at startup**
   - Move call to `lifespan()` after `wire_llm_pipeline()` returns (lifespan is async, wire_llm_pipeline is sync).
   - The gateway is available via `get_gateway()` at that point.

3. **Wire `ToolScopeRegistry` into orchestrator tool dispatch**
   - Add `tool_scope` field to `AgentState` TypedDict.
   - In `tool_node()`: if `state.get("tool_scope")` is set, call `filter_tools_by_allowlist()` and reject calls not in the filtered list.
   - Pass scope from `ChatRequest` → runner → state.

4. **Wire `generate_preview()` into approval flow**
   - In `gateway.py` dispatch, when `needs_approval` is true, call `generate_preview()` from `policy/preview.py` and include preview text in the approval response.
   - Wire `requires_preview()` — only generate preview for medium/high risk.

**Files:**
- `src/noa/api/app.py` — startup wiring for capability_checker + custom tools
- `src/noa/tools/capabilities.py` — refactor to session_factory
- `src/noa/tools/gateway.py` — wire preview generation into approval path
- `src/noa/orchestrator/nodes/tools.py` — scope filtering
- `src/noa/orchestrator/state.py` — add `tool_scope` field
- `src/noa/orchestrator/runner.py` — pass scope from request to state
- `src/noa/policy/preview.py` — becomes the single preview implementation

**Tests:**
- Integration test: capability grant → tool call succeeds; no grant → tool call denied
- Integration test: custom tool registered → restart → tool still available
- Integration test: scope set to "email_draft" → web_search call rejected
- Unit test: medium risk tool → preview text included in approval response

---

### Phase CQ2: Delete Dead Governance Stack (~30 min)

**Goal:** Remove ~400 lines of dead code (Stack B). After CQ1 wires preview.py, the rest of Stack B has zero callers.

**Depends on:** CQ1
**Blocks:** None

**Delete entirely:**
- `src/noa/tools/governance.py` — GovernanceWrapper + duplicate generate_preview
- `src/noa/tools/idempotency.py` — IdempotencyStore (gateway has its own)
- `src/noa/tools/rate_limiter.py` — RateLimiter class (gateway has its own)
- `src/noa/tools/mcp_adapter.py` — deprecated MCPToolAdapter stub
- `src/noa/tools/interface.py` lines 42-88 — ToolRegistry class (keep ToolInterface protocol)

**Clean up references:**
- `src/noa/orchestrator/nodes/tools.py` — remove `ToolRegistry` import, `_registry`, `set_registry()`, `get_registry()`, `_dispatch_registry()`, `_dispatch_registry_legacy()`, `TOOL_ALLOWLIST`, `execute_tool()`.

**Delete tests for dead code:**
- `tests/unit/test_tool_governance.py`

**Verification:** `ruff check`, `mypy`, full test suite. No import errors.

---

### Phase CQ3: Delete Frontend Dead Code (~20 min)

**Goal:** Remove unused components and clean up shadcn bloat.

**Depends on:** None
**Blocks:** CQ5

**Delete:**
- `web/src/components/shared/JSONViewer.tsx` — never imported

**Remove unused shadcn/ui components** (verify zero imports first):
- `aspect-ratio.tsx`, `carousel.tsx`, `hover-card.tsx`, `input-otp.tsx`
- `menubar.tsx`, `navigation-menu.tsx`, `pagination.tsx`, `resizable.tsx`
- `toggle-group.tsx`, `context-menu.tsx`, `command.tsx`

**Verification:** `cd web && npm run build` — no import errors.

---

### Phase CQ4: Enums, Config Centralization, Magic Strings (~30 min)

**Goal:** Replace magic strings with Enums, centralize duplicated config.

**Depends on:** None
**Blocks:** CQ6

**Deliverables:**

1. **PrivacyMode Enum** — `src/noa/types.py`, StrEnum with PRIVATE/EXTERNAL. Replace all string comparisons across ~15 files.
2. **RiskTier Enum** — LOW/MEDIUM/HIGH. Replace magic strings in policy/engine.py, gateway.py, approval.py.
3. **Centralize model defaults** — Single DEFAULT_MODELS dict in config.py. model_config.py and llm/router.py read from it.

**Tests:** Existing tests pass unchanged (StrEnum is string-compatible).

---

### Phase CQ5: Split Chat.tsx & Settings.tsx (~45 min)

**Goal:** Break 759-line Chat.tsx into 7 focused modules, Settings.tsx into 4.

**Depends on:** CQ3
**Blocks:** None

**Chat.tsx splits:**
- `hooks/useChatSSE.ts` (~80 lines) — SSE connection, event dispatch, streaming state
- `hooks/useOptimisticMessages.ts` (~40 lines) — Optimistic insert + dedup logic
- `utils/groupMessagesByRun.ts` (~30 lines) — Pure utility function
- `components/chat/ThreadSidebar.tsx` (~120 lines) — Thread list, create/delete/rename
- `components/chat/ChatMessages.tsx` (~80 lines) — Render message groups + streaming content
- `components/chat/ApprovalCard.tsx` (~80 lines) — Inline approval request UI
- `components/chat/ChatComposer.tsx` (~90 lines) — Input + advanced settings
- `pages/Chat.tsx` (~100 lines) — Layout shell, composes children

**Settings.tsx splits:**
- `components/settings/GoogleAuthSection.tsx` (~80 lines)
- `components/settings/SystemPromptSection.tsx` (~60 lines)
- `components/settings/GeneralSettings.tsx` (~100 lines)
- `pages/Settings.tsx` (~60 lines) — Layout, tab container

**Approach:** Extract bottom-up (utilities → hooks → components). No behavior changes.

**Tests:** Existing tests pass. Add 1 unit test per new hook.

---

### Phase CQ6: Strict Types & DI Cleanup (~60 min)

**Goal:** Eliminate `Any` types in public interfaces, replace module-level globals with app.state refs.

**Depends on:** CQ4
**Blocks:** CQ8

**Deliverables:**

1. **Remove `Any` from public function signatures** — chat.py getters, app_state.py, gateway.py attributes. Target: zero `Any` in function signatures outside test files.
2. **Replace module-level globals** — `_router`, `_gateway`, `_registry` globals → pass through `AgentState` context object. Remove `set_*()` / `get_*()` module-level functions.
3. **TypedDict access tightening** — Direct access `state["messages"]` for required fields, `.get()` only for optional. Runtime validation at graph entry point.

**Tests:** `mypy --strict` on modified files. Existing tests pass.

---

### Phase CQ7: Integration Tests for Wired Features (~45 min)

**Goal:** Every feature wired in CQ1 has a non-mocked integration test.

**Depends on:** CQ1
**Blocks:** None

**New tests:**
1. Capability enforcement: grant → succeeds, no grant → denied, revoke → denied (real DB)
2. Custom tool restore: register via API → restart → tool still in gateway (real DB)
3. Scope filtering: "email_draft" scope → web_search rejected; "research" → accepted (ASGI client)
4. Preview generation: medium-risk → preview text in approval; low-risk → no preview (ASGI client)
5. Dead code absence: verify governance.py/idempotency.py/rate_limiter.py/mcp_adapter.py deleted

---

### Phase CQ8: Consistent Error Handling & SSE Contract (~30 min)

**Goal:** Standardize error handling and SSE event shapes.

**Depends on:** CQ6
**Blocks:** CQ9

**Deliverables:**

1. **Error handling** — Audit 71 `except Exception` catches. Keep startup degradation (~15), narrow tool/DB operations to specific types, remove known-type catches. Target <20 broad catches.
2. **SSE event contract** — Typed dicts per event type in `sse_types.py`. Runner emits typed events. Frontend mirrors types in TypeScript, removes `as string` casts.

---

### Phase CQ9: Security Hardening (final) (~20 min)

**Goal:** Close last security gaps from audit.

**Depends on:** CQ8
**Blocks:** None

**Deliverables:**
1. Logging sanitizer unit tests (real-format API keys masked)
2. Structured approval fields — add `tool_name`/`tool_args` columns to Approval model (migration), replace string-split parsing
3. CORS verification integration test (evil origin rejected)
4. Responder node `isinstance(r, dict)` defensive check


---

## Phase VM1 — Private Vector Memory (pgvector + Ollama embeddings) (~60 min)

**Goal:** Replace the stub RAG implementation in the private worker with real semantic search using `nomic-embed-text` (Ollama) for embeddings and pgvector for storage/retrieval.

**Depends on:** DW1 (private worker), QE4 (Postgres integration tests)
**Blocks:** OI6 (Proactive Memory Extraction — needs real recall to be useful)

**Why private only:** The private worker has no internet access by design. It cannot call cloud embedding APIs, so it must generate embeddings locally via Ollama. The external worker offloads reasoning to cloud LLMs and does not store personal facts, so it does not need vector search.

---

### Deliverables

**1. Postgres: pgvector extension + schema migration**
- Migration `020_memory_embeddings.py`: `CREATE EXTENSION IF NOT EXISTS vector`, add `embedding vector(768)` column to `memory_facts` (nomic-embed-text outputs 768-dim vectors), add HNSW index for cosine similarity (`USING hnsw (embedding vector_cosine_ops)`)

**2. Private worker: real embedding generation**
- `src/noa/private_worker/embeddings.py` — `OllamaEmbedder` class: POST `/api/embeddings` to Ollama with model `nomic-embed-text`, returns `list[float]`
- Fallback: if Ollama unreachable, log warning and return `None` (graceful degradation — fact is stored without embedding, excluded from vector search but still retrievable by exact match)

**3. MemoryStore: wire embeddings into persist + recall**
- `persist(fact)`: generate embedding via `OllamaEmbedder`, store in `memory_facts.embedding`
- `recall(query, top_k=5)`: embed query, run `ORDER BY embedding <=> query_vec LIMIT top_k` cosine similarity search; fall back to recency sort if no embeddings present

**4. Private worker RPC handlers: unstub**
- `rag_ingest`: accept `{"text": str, "metadata": dict}`, chunk text (512-token windows, 50-token overlap), embed each chunk, store in memory_facts with `category="rag"`
- `rag_query`: embed query, vector search, return top-k chunks with similarity scores
- `summarize`: send text to Ollama `/api/generate` (llama3.2 or configured model), return summary string
- `search`: keyword + vector hybrid search (OR: BM25-style substring match UNION vector results)

**5. Tests**
- Unit: `OllamaEmbedder` with mocked httpx — returns correct shape, handles 503 gracefully
- Unit: `MemoryStore.recall` with pgvector mock — correct SQL emitted, cosine order preserved
- Integration (Postgres): real pgvector extension, insert 3 facts with embeddings, query returns closest match first (requires `TEST_DATABASE_URL` + pgvector in testcontainer image `ankane/pgvector`)
- RPC handler tests: `rag_ingest` → stored chunks retrievable via `rag_query`

---

### Files

| File | Change |
|------|--------|
| `alembic/versions/020_memory_embeddings.py` | New migration |
| `src/noa/private_worker/embeddings.py` | New — OllamaEmbedder |
| `src/noa/private_worker/memory_store.py` | Wire embeddings into persist + recall |
| `src/noa/private_worker/app.py` | Unstub rag_ingest, rag_query, summarize, search |
| `tests/unit/test_vm1_vector_memory.py` | Unit tests |
| `tests/integration/test_vm1_pgvector.py` | Integration tests (real DB) |

---

### Acceptance criteria

1. `MemoryStore.recall("therapist")` returns the fact "my therapist is Dr. Smith" ranked #1 when that fact is in the store
2. `rag_query` returns non-empty results when facts have been ingested
3. All 4 previously-stubbed RPC handlers return real data (no `[]` stubs)
4. Graceful degradation: if Ollama is down, `persist` stores fact without embedding, `recall` falls back to recency sort — no 500 error
5. Migration 020 applies cleanly, pgvector extension enabled, HNSW index created
6. ≥1 integration test using real Postgres + pgvector passes in CI


---

## Phase LS1 — LLM Token Streaming (~90 min)

**Goal:** Replace buffered LLM responses with real token-by-token streaming. Users see text appearing as it's generated instead of waiting for the full response.

**Fixes:** TECH-H1
**Depends on:** CP1 (ProviderRouter), CQ8 (SSE contract + sse_types.py)
**Blocks:** Nothing

### What changes

**Each provider client gains streaming support:**

| Provider | Streaming API |
|---|---|
| Anthropic | `stream=True` on `/v1/messages`, parse `content_block_delta` events |
| OpenAI | `stream=True` on `/v1/chat/completions`, parse `data: {"choices":[{"delta":...}]}` chunks |
| Google AI | `alt=sse` on `generateContent`, parse `candidates[0].content.parts` chunks |
| Ollama | Already streams by default (`stream=true` in request body) |

**Runner yields `token` SSE events:**
- New `token` event type added to `sse_types.py`: `{"type": "token", "content": "partial text"}`
- `agent_node` collects streaming chunks from provider, yields each as a `token` event
- Final assembled response stored in `AgentState.messages` as before (no change to state shape)

**Frontend:** `useChatSSE.ts` already handles arbitrary SSE event types. Add `token` case: append to `streamingContent` (already exists for the current fake streaming). No frontend logic change beyond the event type name.

### Deliverables
1. `src/noa/external_worker/llm/anthropic.py` — streaming complete()
2. `src/noa/external_worker/llm/openai.py` — streaming complete()
3. `src/noa/external_worker/llm/google_ai.py` — streaming complete()
4. `src/noa/external_worker/llm/ollama.py` — streaming complete() (verify existing)
5. `src/noa/orchestrator/nodes/agent.py` — yield token events from streaming response
6. `src/noa/orchestrator/sse_types.py` — add `TokenEvent` TypedDict
7. `tests/unit/test_ls1_streaming.py` — mock streaming responses for all 4 providers, verify token events emitted

### Acceptance criteria
1. Sending a chat message yields multiple `token` SSE events before `result_ready`
2. All 4 providers tested with mock streaming responses
3. Non-streaming fallback preserved (if provider returns non-chunked response, treat as single token event)
4. `mypy` + `ruff` clean

---

## Phase LS2 — Orchestrator Timeout Watchdog (~30 min)

**Goal:** Prevent hung graph executions from holding requests indefinitely. Apply `timeout_seconds` from user settings to the full orchestrator run.

**Fixes:** TECH-M2
**Depends on:** CP2 (OrchestratorRunner), MVP-fixes (timeout_seconds wired to settings)
**Blocks:** Nothing

### What changes

**`src/noa/orchestrator/runner.py`:**
```python
# In OrchestratorRunner.run():
timeout = settings.timeout_seconds or 120  # default 120s
try:
    async with asyncio.timeout(timeout):
        async for event in graph.astream(...):
            yield event
except asyncio.TimeoutError:
    yield {"type": "error", "message": f"Request timed out after {timeout}s"}
    # mark run as failed via RunService
```

**`src/noa/api/v1/chat.py`:** Ensure the `error` SSE event from timeout reaches the client cleanly (already handled by existing error path).

### Deliverables
1. `src/noa/orchestrator/runner.py` — `asyncio.timeout()` wrapper
2. `tests/unit/test_ls2_timeout.py` — mock slow graph, verify timeout fires, error event emitted, run marked failed

### Acceptance criteria
1. Graph that never completes is cancelled after `timeout_seconds`
2. Client receives `{"type": "error", "message": "Request timed out after Xs"}`
3. Run row status set to `"failed"` in DB
4. Fast runs unaffected (timeout not triggered)
5. `timeout_seconds=0` or `None` → use 120s default

---

## CC1 — Context Window Compaction

### Overview
When conversations approach the LLM context limit (80% of model max), automatically summarize older messages using a cheap LLM call while preserving recent context and key facts.

### Files
- `src/noa/orchestrator/token_budget.py` — Model context window registry, token estimation (chars/3), `needs_compaction()` threshold check
- `src/noa/orchestrator/nodes/compactor.py` — `compact_messages()`: summarizes old messages via cheap LLM, keeps `keep_recent=6` most recent, marks summary with `is_compaction_boundary=True`
- `src/noa/orchestrator/state.py` — Added `is_compaction_boundary: bool` to AgentState
- `src/noa/orchestrator/sse_types.py` — Added `CompactionEvent` TypedDict + `"compaction"` to VALID_SSE_EVENT_TYPES
- `src/noa/orchestrator/runner.py` — Post-execution compaction check, checkpoint save after compaction
- `tests/unit/test_cc1_compaction.py` — 28 tests

### Design decisions
- Token estimation uses chars/3 (conservative) rather than tiktoken dependency
- Compaction runs after graph execution, not mid-stream, to avoid state complexity
- Summary injected as system message so LLM treats it as context, not conversation

---

## OI7 — Cross-Domain Step-Up Approval

### Overview
When in private mode, external tool requests trigger an approval prompt instead of raising PermissionError. User can approve specific cross-domain tool calls without exposing conversation history.

### Files
- `src/noa/tools/gateway.py` — Cross-domain PermissionError replaced with approval_required response (cross_domain=True, risk_tier="high")
- `src/noa/orchestrator/nodes/tools.py` — `privacy_mode` wired through `_dispatch_gateway()` from state
- `src/noa/orchestrator/runner.py` — Approval event payload includes `cross_domain` and `reason` fields
- `tests/unit/test_oi7_cross_domain.py` — 15 tests

### Design decisions
- Cross-domain always classified as "high" risk (requires both approval + step-up auth)
- Only external-from-private triggers approval; private-from-external remains PermissionError (shouldn't happen)
- `approved=True` flag on ToolRequest bypasses the domain check for approved re-execution

---

## OI8 — Smart Domain Redirect

### Overview
Replace 403 DOMAIN_MISMATCH with intelligent redirect: auto-create thread in correct domain, route message there, SSE meta event tells frontend to switch.

### Files
- `src/noa/api/v1/chat.py` — Domain mismatch → new thread_id + run_id in correct domain, meta event includes `redirected`, `original_thread_id`, `redirect_reason`
- `src/noa/orchestrator/sse_types.py` — MetaEvent extended with NotRequired redirect fields
- `web/src/hooks/useChatSSE.ts` — `onDomainRedirect` callback on meta event, toast notification
- `web/src/pages/Chat.tsx` — Passes `onDomainRedirect` to switch activeThread + invalidate queries
- `tests/unit/test_oi8_domain_redirect.py` — 6 tests

### Design decisions
- New thread auto-created via existing `_make_run_service` (no new API needed)
- Frontend uses toast notification for UX clarity when redirect occurs
- Original thread_id preserved in meta event for audit trail

---

## RLS1 — Postgres Row-Level Security

### Overview
Add Postgres RLS policies on all domain-sensitive tables for DB-enforced isolation. Defense-in-depth alongside application-level WHERE clauses.

### Files
- `alembic/versions/025_row_level_security.py` — Migration: RLS on conversations, approvals, memory_facts, audit_log, custom_tools, runs (6 tables). SELECT/INSERT/UPDATE/DELETE policies per table.
- `src/noa/db/rls.py` — `set_domain_context(session, domain)` and `clear_domain_context(session)` helpers. Transaction-local `set_config('noa.domain', ..., true)`. SQLite-safe no-op.
- `tests/unit/test_rls1_row_level_security.py` — 16 tests

### Design decisions
- Empty-string domain = see all rows (backward compatible; callers adopt incrementally)
- Transaction-local `set_config` prevents domain leakage across pool connections
- SQLite dialect skips all RLS SQL (tests unaffected)
- `runs` table uses `privacy_mode` column (functionally equivalent to domain)

---

## SEC1: JWT Token Revocation

**Spec refs:** SPEC §7 (auth), §36 (build order)

**Goal:** Add a token blacklist table so access tokens can be immediately revoked on logout. Resolves TECH-M1 finding.

### Scope

1. `token_blacklist` table: jti (unique indexed), user_id FK, expires_at, revoked_at, reason
2. Migration 026
3. `require_auth()` middleware checks blacklist before accepting token
4. `logout()` inserts current token's jti into blacklist
5. Background sweeper purges expired entries hourly
6. `revoke_all_user_tokens()` for password change scenarios

### Files
- `src/noa/db/models/token_blacklist.py` — TokenBlacklist model
- `alembic/versions/026_token_blacklist.py` — Migration
- `src/noa/auth/service.py` — revoke/check/cleanup methods
- `src/noa/auth/middleware.py` — blacklist check in require_auth
- `src/noa/api/app.py` — periodic cleanup task
- `tests/unit/test_sec1_token_revocation.py`

---

## KM1: Kimi 2.5 LLM Provider (Moonshot AI)

**Spec refs:** SPEC §8 (LLM providers), §36 (build order)

**Goal:** Add Moonshot AI's Kimi 2.5 as an LLM provider. Kimi uses an OpenAI-compatible API (same endpoints, same request/response format).

### API Details
- Base URL: `https://api.moonshot.cn/v1`
- Auth: Bearer token
- Chat completions: `POST /v1/chat/completions` (OpenAI-compatible)
- Models: `kimi-k2` (latest), `moonshot-v1-128k`, `moonshot-v1-32k`, `moonshot-v1-8k`
- Streaming: SSE (same as OpenAI)
- Tool calling: OpenAI function calling format

### Scope

1. `KimiClient` — thin OpenAI-compatible client with Moonshot base URL
2. Router registration — `kimi` provider with `kimi-k2` default
3. Config — `kimi_api_key` env var + DB column
4. Frontend — provider models list + settings API key field
5. Migration for kimi_api_key column in user_settings

### Files
- `src/noa/external_worker/llm/kimi.py` — KimiClient
- `src/noa/external_worker/llm/router.py` — registration
- `src/noa/config.py` — kimi_api_key field
- `src/noa/settings/models.py` — DB column
- `alembic/versions/027_kimi_api_key.py` — Migration
- `web/src/components/settings/providerModels.ts` — frontend models
- `tests/unit/test_km1_kimi_provider.py`
