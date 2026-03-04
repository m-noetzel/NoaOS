# MASTER_PLAN.md — Noa Implementation Plan

## Overview

This plan implements Noa Phase 1 (single-machine deployment) as specified in SPEC.md v5.0. The plan follows the build order defined in SPEC.md §36 and covers Backend Foundation + Web Client (Build Phases 1-2). Native iOS and dual-machine deployment (Build Phases 3-4) are deferred to future planning.

The plan is organized into **waves** — groups of related phases that deliver a cohesive capability. Each wave has a human gate before execution begins.

---

## Phase Status Summary

| ID | Phase | Status | Tests | Branch | Est. | Actual | Notes |
|----|-------|--------|-------|--------|------|--------|-------|
| — | — **WAVE 1: PROJECT FOUNDATION** — | — | — | — | — | — | — |
| **F1** | Project Scaffold & Docker Compose | **Complete** | 17 | agent/f1-scaffold | ~30 min | ~30 min | QA PASS 2026-03-04 |
| **F2** | Postgres Schema & Alembic Migrations | **Complete** | 21 | agent/f2-schema | ~45 min | ~30 min | QA PASS 2026-03-04 |
| **F3** | FastAPI Skeleton & Health Endpoints | **Complete** | 15 | agent/f3-api-skeleton | ~30 min | ~15 min | QA PASS 2026-03-04 |
| **F4** | Authentication & Session Management | **Complete** | 20 | agent/f4-auth | ~45 min | ~30 min | QA PASS_WITH_NOTES 2026-03-04 |
| — | — **WAVE 2: ORCHESTRATION CORE** — | — | — | — | — | — | — |
| **OC1** | LangGraph Orchestrator Skeleton | **Complete** | 26 | agent/oc1-orchestrator | ~45 min | ~40 min | QA PASS 2026-03-04 |
| **OC2** | Run/Event Model & SSE Streaming | **Complete** | 37 | agent/oc2-runs-sse | ~45 min | ~20 min | QA PASS 2026-03-04 |
| **OC3** | Audit Logging with Hash Chain | **Complete** | 18 | agent/oc3-audit | ~30 min | ~20 min | QA PASS_WITH_NOTES 2026-03-04 |
| **OC4** | Policy Engine & Approval Framework | **Complete** | 28 | agent/oc4-policy-engine | ~45 min | ~20 min | QA PASS 2026-03-04 |
| — | — **WAVE 3: DOMAIN WORKERS & ISOLATION** — | — | — | — | — | — | — |
| **DW1** | Private Worker with Ollama & RPC Contract | Pending | ~20 | — | ~45 min | — | — |
| **DW2** | External Worker Skeleton | Pending | ~12 | — | ~30 min | — | — |
| **DW3** | Docker Network Isolation & Verification | Pending | ~10 | — | ~30 min | — | — |
| **DW4** | Privacy Router & Classification | Pending | ~18 | — | ~45 min | — | — |
| — | — **WAVE 4: TOOL INTEGRATIONS** — | — | — | — | — | — | — |
| **TI1** | Memory Tool (Remember/Recall) | Pending | ~15 | — | ~30 min | — | — |
| **TI2** | Google Calendar Tool | Pending | ~15 | — | ~30 min | — | — |
| **TI3** | Gmail Tool | Pending | ~18 | — | ~30 min | — | — |
| **TI4** | Notion Tool | Pending | ~15 | — | ~30 min | — | — |
| **TI5** | Web Search Tool (Tavily) | Pending | ~8 | — | ~20 min | — | — |
| **TI6** | Tool Governance (Idempotency, Rate Limits, Previews) | Pending | ~20 | — | ~45 min | — | — |
| — | — **WAVE 5: ADVANCED BACKEND** — | — | — | — | — | — | — |
| **AB1** | Cost Control & Token Tracking | Pending | ~15 | — | ~30 min | — | — |
| **AB2** | Output Validation Pipeline | Pending | ~15 | — | ~30 min | — | — |
| **AB3** | Task Scheduling & Prioritization | Pending | ~15 | — | ~30 min | — | — |
| **AB4** | Durable Queue & Private Domain Availability | Pending | ~12 | — | ~30 min | — | — |
| **AB5** | Coding Task Contract & Worker | Pending | ~15 | — | ~30 min | — | — |
| — | — **WAVE 6: WEB CLIENT** — | — | — | — | — | — | — |
| **WC1** | React Project Setup & Chat UI with SSE | Pending | ~15 | — | ~45 min | — | — |
| **WC2** | Run Timeline & Event Details | Pending | ~12 | — | ~30 min | — | — |
| **WC3** | Approval Interface with Dry-Run Previews | Pending | ~12 | — | ~30 min | — | — |
| **WC4** | Task Queue Visualization | Pending | ~10 | — | ~20 min | — | — |
| **WC5** | Memory Audit UI | Pending | ~12 | — | ~30 min | — | — |
| **WC6** | Cost Dashboard & Settings | Pending | ~10 | — | ~25 min | — | — |
| **WC7** | Artifact Viewer & PWA Manifest | Pending | ~10 | — | ~25 min | — | — |

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

### Phase TI5: Web Search Tool (Tavily) (~20 min)

**Goal:** No web search capability exists. This phase implements the Web Search tool using the Tavily API.

**Spec refs:** SPEC.md §12.4

**Depends on:** DW2
**Blocks:** TI6

**Deliverables:**
1. `web_search(query, max_results?)` — search results with title, URL, content snippet (Low risk)
2. Tavily API client

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/web_search.py` | **CREATE** | Web Search tool (Tavily) |
| `tests/unit/test_web_search_tool.py` | **CREATE** | Web search tool tests |

**Tests (~8):**
- Search: returns results with title, URL, snippet
- Max results: respects max_results parameter
- Risk tier: always Low
- Error handling: API failures handled gracefully

**Test gate:**
```bash
pytest tests/unit/test_web_search_tool.py -v
```

---

### Phase TI6: Tool Governance (Idempotency, Rate Limits, Previews) (~45 min)

**Goal:** No tool governance exists. This phase adds idempotency enforcement, rate limiting, and dry-run preview generation across all tools.

**Spec refs:** SPEC.md §19.1, §19.2, §19.3, §25.4

**Depends on:** OC4, TI1-TI5
**Blocks:** None

**Deliverables:**
1. Idempotency key enforcement on all write tools per §19.1
2. Per-tool rate limiting per §19.3
3. Dry-run preview generation for all Medium-risk actions per §19.2
4. Idempotency-Key header support on all write API endpoints per §25.4

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `src/noa/tools/governance.py` | **CREATE** | Idempotency, rate limiting, preview middleware |
| `src/noa/tools/idempotency.py` | **CREATE** | Idempotency key store + dedup logic |
| `src/noa/tools/rate_limiter.py` | **CREATE** | Per-tool rate limiting per §19.3 |
| `src/noa/api/middleware.py` | **EDIT** | Add Idempotency-Key header support |
| `tests/unit/test_tool_governance.py` | **CREATE** | Tool governance tests |

**Tests (~20):**
- Idempotency: duplicate send_email with same key → no re-send per §19.1
- Idempotency: duplicate create_event with same key → returns previous result
- Rate limits: send_email blocked after 10/hour per §19.3
- Rate limits: create_event blocked after 20/hour
- Rate limits: web_search blocked after 30/hour
- Preview generation: all create/send actions generate preview before execution
- Preview format: includes diff-like summary of changes
- API header: Idempotency-Key deduplicates within 24 hours

**Test gate:**
```bash
pytest tests/unit/test_tool_governance.py -v
```

---

## Wave 5: Advanced Backend

Adds cost control, output validation, task scheduling, durable queuing, and the coding task contract. After this wave, the backend is feature-complete.

---

### Phase AB1: Cost Control & Token Tracking (~30 min)

**Goal:** No cost control exists. This phase implements token tracking, cost estimation, and hard budget limits (monthly, daily, per-task).

**Spec refs:** SPEC.md §24

**Depends on:** OC1, OC3
**Blocks:** None

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

### Phase AB2: Output Validation Pipeline (~30 min)

**Goal:** No output validation exists. This phase implements the validation pipeline that checks all worker outputs before Noa acts on them (schema validation, size limits, content filtering, prompt injection detection).

**Spec refs:** SPEC.md §16.1, §16.2, §16.3, §16.4

**Depends on:** OC1, DW1, DW2
**Blocks:** None

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

### Phase AB3: Task Scheduling & Prioritization (~30 min)

**Goal:** No task scheduling exists. This phase implements deterministic task ordering with priority tiers, FIFO within tiers, and dependency resolution.

**Spec refs:** SPEC.md §23.1, §23.3, §23.4

**Depends on:** OC4
**Blocks:** AB4

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

### Phase AB4: Durable Queue & Private Domain Availability (~30 min)

**Goal:** No resilience for private domain unavailability exists. This phase implements the durable queue that holds private tasks when the private domain is down, with retry, timeout, and user notification.

**Spec refs:** SPEC.md §17.1, §17.2, §17.3

**Depends on:** DW1, AB3
**Blocks:** None

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

### Phase AB5: Coding Task Contract & Worker (~30 min)

**Goal:** No coding task execution exists. This phase implements the coding task contract (input/output schema), the shell sandbox within the external container, and structured output from coding tasks.

**Spec refs:** SPEC.md §15, §2.4, §8.2 (Shell Sandbox)

**Depends on:** DW2
**Blocks:** None

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
```

---

## Phase Reports

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

## Changelog

_Entries added after each phase completion._

| Date | Phase | Summary |
|------|-------|---------|
| — | — | Plan created |
