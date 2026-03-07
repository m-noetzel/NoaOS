# MASTER_PLAN.md — Noa Implementation Plan

## Overview

This plan implements Noa Phase 1–3 (single-machine deployment + native iOS client) as specified in SPEC.md v5.0. The plan follows the build order defined in SPEC.md §36 and covers Backend Foundation (Build Phase 1), Web Client (Build Phase 2), and Native iOS Client (Build Phase 3). Dual-machine deployment (Build Phase 4) is deferred to future planning.

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
| **DW1** | Private Worker with Ollama & RPC Contract | **Complete** | 38 | agent/dw1-private-worker | ~45 min | ~20 min | QA PASS_WITH_NOTES 2026-03-05 |
| **DW2** | External Worker Skeleton | **Complete** | 16 | agent/dw2-external-worker | ~30 min | ~15 min | QA PASS 2026-03-05 |
| **DW3** | Docker Network Isolation & Verification | **Complete** | 16 | agent/dw3-network-isolation | ~30 min | ~10 min | QA PASS 2026-03-05 |
| **DW4** | Privacy Router & Classification | **Complete** | 21 | agent/dw4-privacy-router | ~45 min | ~15 min | QA PASS_WITH_NOTES 2026-03-05 |
| — | — **WAVE 4: TOOL INTEGRATIONS** — | — | — | — | — | — | — |
| **TI1** | Memory Tool (Remember/Recall) | **Complete** | 29 | agent/ti1-memory-tool | ~30 min | ~15 min | Merged fd4c71b 2026-03-05 |
| **TI2** | Google Calendar Tool | **Complete** | 17 | agent/ti2-calendar-tool | ~30 min | ~10 min | Merged 5cf5ae2 2026-03-05 |
| **TI3** | Gmail Tool | **Complete** | 14 | agent/ti3-gmail-tool | ~30 min | ~10 min | Merged 6d1cdcf 2026-03-05 |
| **TI4** | Notion Tool | **Complete** | 13 | agent/ti4-notion-tool | ~30 min | ~10 min | Merged 2b487de 2026-03-05 |
| **TI5** | Web Search Tool (Provider-Agnostic, Tavily first) | **Complete** | 13 | agent/ti5-web-search-tool | ~20 min | ~10 min | Merged 505e494 2026-03-05 |
| **TI6** | Tool Interface, Registry & Governance (MCP-ready) | **Complete** | 36 | agent/ti6-tool-governance | ~60 min | ~20 min | Merged d735763 2026-03-05 |
| — | — **WAVE 5: ADVANCED BACKEND** — | — | — | — | — | — | — |
| **AB1** | Cost Control & Token Tracking | **Complete** | 16 | agent/ab1-cost-control | ~20 min | ~5 min | Merged 2026-03-05 |
| **AB2** | Output Validation Pipeline | **Complete** | 24 | agent/ab2-output-validation | ~20 min | ~4 min | Merged 2026-03-05 |
| **AB3** | Task Scheduling & Prioritization | **Complete** | 18 | agent/ab3-task-scheduler | ~20 min | ~5 min | Merged 2026-03-05 |
| **AB4** | Durable Queue & Private Domain Availability | **Complete** | 15 | agent/ab4-durable-queue | ~20 min | ~3 min | Merged 2026-03-05 |
| **AB5** | Coding Task Contract & Worker | **Complete** | 17 | agent/ab5-coding-task | ~20 min | ~7 min | Merged 2026-03-05 |
| — | — **WAVE 6: WEB CLIENT** — | — | — | — | — | — | — |
| **WC1** | React Project Setup & Chat UI with SSE | **Complete** | 25 | main | ~10 min | ~8 min | QA PASS 2026-03-05 |
| **WC2** | Run Timeline & Event Details | **Complete** | 9 | main | ~7 min | ~3 min | QA PASS 2026-03-05 |
| **WC3** | Approval Interface with Dry-Run Previews | **Complete** | 8 | main | ~7 min | ~3 min | QA PASS 2026-03-05 |
| **WC4** | Task Queue Visualization | **Complete** | 7 | main | ~5 min | ~2 min | QA PASS 2026-03-05 |
| **WC5** | Memory Audit UI | **Complete** | 8 | main | ~7 min | ~4 min | QA PASS 2026-03-05 |
| **WC6** | Cost Dashboard & Settings | **Complete** | 8 | main | ~5 min | ~3 min | QA PASS 2026-03-05 |
| **WC7** | Artifact Viewer & PWA Manifest | **Complete** | 10 | main | ~7 min | ~3 min | QA PASS 2026-03-05 |
| — | — **WAVE 7: UI MIGRATION & BACKEND WIRING** — | — | — | — | — | — | — |
| **WM1** | UI Swap & Build Config | **Complete** | — | main | ~15 min | ~5 min | Polished UI replaces old web/, lovable refs removed |
| **WM2** | Frontend Contract Alignment | **Complete** | — | main | ~10 min | ~5 min | ApiResponse → backend envelope, auth email+device_id |
| **WM3** | Backend API Completion | **Complete** | 56 | main | ~30 min | ~10 min | 6 new routers, tasks mounted, approvals fixed, CORS tightened |
| **WM4** | Frontend Wiring (No-Ops → Real) | **Complete** | — | main | ~20 min | ~10 min | Memory, Settings, Queue, Chat, Threads all wired |
| **WM5** | Security Hardening | **Complete** | — | main | ~10 min | ~3 min | DOMPurify XSS fix, CORS restricted, 429 handling |
| **WM6** | Tests & Verification | **Complete** | 73 | main | ~20 min | ~5 min | 56 backend + 17 frontend tests, build clean |
| — | — **WAVE 8: CREDENTIAL MANAGEMENT** — | — | — | — | — | — | — |
| **CM1** | Extend Settings with Tool Credentials | **Complete** | 18 | main | ~30 min | ~10 min | QA PASS 2026-03-06 |
| **CM2** | macOS Keychain Bootstrap | **Complete** | 16 | main | ~45 min | ~8 min | QA PASS 2026-03-06 |
| — | — **WAVE 9: LLM PROVIDER WIRING** — | — | — | — | — | — | — |
| **LP1** | Anthropic Client HTTP | **Complete** | 10 | main | ~30 min | ~8 min | Real httpx calls to /v1/messages, tool_use blocks, retry on 429/529 |
| **LP2** | OpenAI Client HTTP | **Complete** | 10 | main | ~30 min | ~5 min | Real httpx calls to /v1/chat/completions, tool_calls parsing |
| **LP3** | Google AI Client (New) | **Complete** | 9 | main | ~30 min | ~5 min | GoogleAIClient for Gemini via generateContent API |
| **LP4** | Ollama Client HTTP | **Complete** | 8 | main | ~20 min | ~5 min | Real httpx calls to /api/chat, model manifest check |
| **LP5** | ProviderRouter as Dispatch Hub | **Complete** | 9 | main | ~30 min | ~8 min | Router creates clients, dispatches complete(), privacy enforcement |
| — | — **WAVE 10: END-TO-END CHAT PIPELINE** — | — | — | — | — | — | — |
| **CP1** | Wire invoke_llm to ProviderRouter | **Complete** | 13 | main | ~30 min | ~5 min | LLMResponse wrapper, async agent_node, set_router/get_router |
| **CP2** | OrchestratorRunner + Event Types | **Complete** | 10 | main | ~45 min | ~5 min | Graph execution, SSE event yielding, RunService persistence |
| **CP3** | Chat Endpoint → Real Pipeline | **Complete** | 8 | main | ~45 min | ~8 min | SSE StreamingResponse, meta event, thread creation, error handling |
| **CP4** | App Startup Wiring | **Complete** | 9 | main | ~30 min | ~5 min | wire_llm_pipeline(), ProviderRouter + Runner in lifespan |
| — | — **WAVE 11: TOOL GATEWAY + TAVILY** — | — | — | — | — | — | — |
| **TG1** | ToolRequest/ToolResponse + ToolGateway | **Complete** | 16 | main | ~30 min | ~5 min | Gateway with idempotency, rate limits, dry-run, telemetry |
| **TG2** | DirectApiAdapter | **Complete** | 8 | main | ~20 min | ~3 min | Wraps ToolInterface for gateway dispatch |
| **TG3** | Tavily HTTP Client + Registration | **Complete** | 10 | main | ~30 min | ~5 min | Real httpx Tavily calls, registered at startup |
| — | — **WAVE 12: GOOGLE + NOTION TOOLS** — | — | — | — | — | — | — |
| **GT1** | Google OAuth Token Exchange + Storage | **Complete** | 19 | main | ~30 min | ~5 min | OAuth exchange, refresh, DB column, no-log compliance |
| **GT2** | Google Calendar + Gmail HTTP Clients | **Complete** | 14 | main | ~30 min | ~5 min | Calendar API v3 + Gmail API v1 httpx, auto-refresh on 401 |
| **GT3** | Notion HTTP Client + Registration | **Complete** | 11 | main | ~30 min | ~3 min | Notion API v1 httpx, tool registration |
| **GT4** | McpRemoteAdapter (Phase 2 Stub) | **Complete** | 4 | main | ~10 min | ~2 min | Stub with NotImplementedError |
| — | — **WAVE 13: MVP COMPLETION** — | — | — | — | — | — | — |
| **MR1** | Real Auth + First-Run Registration | **Complete** | 14 | main | ~30 min | ~8 min | Real DB queries, register endpoint, sid claim fix |
| **MR2** | Memory Persistence | **Complete** | 13 | main | ~25 min | ~4 min | JSON-file-per-fact persistence for MemoryStore |
| **MR3** | Tool Call Audit Trail | **Complete** | 16 | main | ~25 min | ~4 min | Async audit callback in ToolGateway |
| **MR4** | Tool Call Telemetry to DB | **Complete** | 13 | main | ~30 min | ~6 min | ToolCallLog model, DB persistence, /health/tools |
| **MR5** | Capability-Based Tool Permissions | **Complete** | 14 | main | ~30 min | ~5 min | Per-tool capabilities, DB grants, enable/disable endpoints |
| **MR6** | Docker Compose Hardening | **Complete** | 15 | main | ~20 min | ~2 min | Healthchecks, resource limits, security flags |
| **MR8** | Per-Node Model Routing | **Complete** | 13 | main | ~25 min | ~3 min | ModelConfig per-node model defaults |
| **MR9** | Conditional Graph Edges | **Complete** | 19 | main | ~25 min | ~7 min | Conditional edges, tool-loop cap |
| **MR7** | Integration Smoke Test | **Complete** | 10 | main | ~25 min | ~7 min | End-to-end auth flow against ASGI app |
| — | — **WAVE 14: OPERATIONS & GO-LIVE** — | — | — | — | — | — | — |
| **OP1** | Backup Infrastructure | **Complete** | 29 | main | ~30 min | ~5 min | pg_dump + GPG encryption, restore verification, Docker sidecar |
| **OP2** | Log Persistence + Rotation | **Complete** | 25 | main | ~25 min | ~5 min | JSON logging, Docker log drivers, retention scheduler (90d) |
| **OP3** | Health Checks + Compose Fixes | **Complete** | 15 | main | ~20 min | ~3 min | External-worker healthcheck, private-worker 4CPU/32G limits |
| **OP4** | Postgres Maintenance | **Complete** | 13 | main | ~20 min | ~3 min | Pool tuning (10+20), VACUUM scheduler, pool stats endpoint |
| **OP5** | Operational Runbook | **Complete** | 11 | main | ~20 min | ~4 min | Pre-flight checks, runbook with 8 sections, troubleshooting |
| — | — **WAVE 14B: QUALITY & CLEANUP** — | — | — | — | — | — | — |
| **QC1** | Critical Runtime Fixes | **Complete** | 13 | main | ~30 min | ~15 min | C1: async tool dispatch, C4: migration 005, C5: JWT no empty fallback, A3: full state init, H3: proper AuditService ctor |
| **QC2** | Security Hardening | **Complete** | 31 | main | ~45 min | ~40 min | C3: audit FOR UPDATE, C6: httpOnly cookies, H6: email validation, H7: default deny, H10: nh3 sanitization, M2: CORS tightening, M4: CSP headers |
| **QC3** | Error Handling & Observability | Planned | — | — | ~30 min | — | H4, H5, M8, M11, M13 |
| **QC4** | Domain Isolation & Worker Wiring | Planned | — | — | ~45 min | — | C2, H1, H9 |
| **QC5** | Database & Data Integrity | Planned | — | — | ~30 min | — | H2, M3, M6, M9, M12 |
| **QC6** | Frontend Critical & High Fixes | Planned | — | — | ~30 min | — | UI-C1–C3, UI-H1–H5 |
| **QC7** | Frontend Polish & UX | Planned | — | — | ~45 min | — | UI-M1–M10 |
| **QC8** | Architecture & Robustness | Planned | — | — | ~60 min | — | A1, A2, A4, A5, H8, M1, M5, M7, M10, M14 |
| — | — **WAVE 15A: BACKEND EXTENSIONS (iOS)** — | — | — | — | — | — | — |
| **iOS1** | APNs Push Notification Backend | Planned | — | — | ~45 min | — | Device token registration, HTTP/2 APNs service, approval batching |
| **iOS2** | Voice Upload Endpoint | Planned | — | — | ~30 min | — | Multipart audio upload, Whisper transcription, chat pipe |
| — | — **WAVE 15B: iOS FOUNDATION** — | — | — | — | — | — | — |
| **iOS3** | Xcode Project Scaffold & Networking Layer | Planned | — | — | ~60 min | — | SwiftUI app, APIClient, SSEClient, shared models |
| **iOS4** | Keychain Storage & Auth Flow | Planned | — | — | ~45 min | — | KeychainService, AuthService, LoginView, auto-refresh |
| **iOS5** | Chat UI with SSE Streaming | Planned | — | — | ~60 min | — | ChatView, token streaming, threads, NavigationSplitView |
| — | — **WAVE 15C: iOS FEATURES** — | — | — | — | — | — | — |
| **iOS6** | Push Notifications (APNs Client) | Planned | — | — | ~45 min | — | UNUserNotificationCenter, deep linking, inline actions |
| **iOS7** | Biometric Step-Up Auth & Approval Flow | Planned | — | — | ~45 min | — | Face ID/Touch ID, approval UI, batch approve/deny |
| **iOS8** | Voice Recording & Playback | Planned | — | — | ~45 min | — | AVAudioRecorder, upload to /voice/transcribe, auto-send |
| **iOS9** | Offline Request Queue with Idempotency | Planned | — | — | ~45 min | — | File-based FIFO queue, NWPathMonitor, auto-drain |
| **iOS10** | VPN Auto-Connect & Certificate Pinning | Planned | — | — | ~30 min | — | SPKI pinning, NEVPNManager, Tailscale/WireGuard URL scheme |
| **iOS11** | Integration Tests & Polish | Planned | — | — | ~45 min | — | E2E tests, accessibility, dark mode, error states |
| — | — **WAVE 16: PLAYWRIGHT E2E TESTING** — | — | — | — | — | — | — |
| **PW1** | Playwright Setup & Auth Tests | Planned | — | — | ~30 min | — | Install, config, auth fixture, 6 auth/route-guard tests |
| **PW2** | Chat E2E with SSE Simulation | Planned | — | — | ~30 min | — | SSE mock helper, 6 chat streaming tests |
| **PW3** | Settings & Navigation Tests | Planned | — | — | ~20 min | — | 3 settings tests, 3 navigation tests, data-testid attrs |

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

### Phase iOS8: Voice Recording & Playback (~45 min)

**Goal:** Add voice recording via AVFoundation, upload to backend voice endpoint, display transcription.

**Spec refs:** SPEC.md §29.3 item 3, §36.3 item 3

**Depends on:** iOS2 (backend), iOS5 (chat)
**Blocks:** None

**Deliverables:**
1. `AudioRecorderService` using AVAudioRecorder for m4a recording
2. `AudioPlayerService` using AVAudioPlayer for playback
3. Microphone permission handling (NSMicrophoneUsageDescription)
4. Voice button in ComposerBar: tap-and-hold or toggle recording
5. Recording waveform/timer visualization
6. Upload to `POST /api/v1/voice/transcribe`, auto-send to chat option
7. Max 10 min recording duration

**Files:**

| File | Action | Description |
|------|--------|-------------|
| `ios/Noa/Noa/Services/AudioRecorderService.swift` | **CREATE** | AVAudioRecorder wrapper |
| `ios/Noa/Noa/Services/AudioPlayerService.swift` | **CREATE** | AVAudioPlayer wrapper |
| `ios/Noa/Noa/Services/VoiceService.swift` | **CREATE** | Upload to /voice/transcribe |
| `ios/Noa/Noa/ViewModels/VoiceViewModel.swift` | **CREATE** | Recording state, upload, transcription |
| `ios/Noa/Noa/Views/Chat/VoiceRecordButton.swift` | **CREATE** | Record button with waveform |
| `ios/Noa/Noa/Views/Chat/ComposerBar.swift` | **MODIFY** | Add voice button |
| `ios/Noa/Noa/Info.plist` | **MODIFY** | NSMicrophoneUsageDescription |

**Tests (~12):**
- Recording start/stop, permission handling, upload multipart, transcription receipt, auto-send mode, cancel discard, max duration

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

_Entries added after each phase completion._

| Date | Phase | Summary |
|------|-------|---------|
| — | — | Plan created |
