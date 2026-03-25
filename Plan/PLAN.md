# PLAN.md — Noa Implementation Plan

## Overview

This plan implements Noa Phase 1–3 (single-machine deployment + native iOS client) as specified in SPEC.md v5.0. The plan follows the build order defined in SPEC.md §36 and covers Backend Foundation (Build Phase 1), Web Client (Build Phase 2), and Native iOS Client (Build Phase 3). Dual-machine deployment (Build Phase 4) is deferred to future planning.

The plan is organized into **waves** — groups of related phases that deliver a cohesive capability. Each wave has a human gate before execution begins.

---

## Key Documents

- **[FINDINGS.md](FINDINGS.md)** — 213 audit findings (189 resolved, 24 open). Updated inline when findings are resolved.
- **[PHASE_DETAILS.md](PHASE_DETAILS.md)** — Detailed phase descriptions (search by phase ID).
- **[QA_CHECKLIST.md](QA_CHECKLIST.md)** — QA criteria (M1-M8 must-haves, S1-S5 should-haves).

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
| **QC3** | Error Handling & Observability | **Complete** | 26 | main | ~30 min | ~45 min | H4: repo commit boundary, H5: bare except logging, M8: cost 500 on DB error, M11: AuthUser dataclass, M13: backup check=True + env whitelist |
| **QC4** | Domain Isolation & Worker Wiring | **Complete** | 15 | main | ~45 min | ~30 min | C2: shared OllamaClient in noa.llm.providers, H1: /v1/complete + /rpc endpoints, H9: Google AI tool call id |
| **QC5** | Database & Data Integrity | **Complete** | 20 | main | ~30 min | ~30 min | H2: 7 indexes + migration 006, M3: async purge, M6: approval expiry wired, M9: 24h violation window, M12: Any session type |
| **QC6** | Frontend Critical & High Fixes | **Complete** | 26 | main | ~30 min | ~45 min | QA PASS_WITH_NOTES: UI-C1 SSE BASE_URL, UI-C2 meta event, UI-C3 logout cache, UI-H1 google_ai, UI-H2 model filter, UI-H3 budget validation, UI-H4 ErrorBoundary, UI-H5 delete confirm |
| **QC7** | Frontend Polish & UX | **Complete** | 36 | main | ~45 min | ~30 min | UI-M1–M10: pagination, SSE validation, optimistic append, thread titles, Tools page, Cost states, settings freshness, sidebar badges, code splitting |
| **QC8** | Architecture & Robustness | **Complete** | 33 | main | ~60 min | ~60 min | QA PASS_WITH_NOTES (cycle 2): A1 reset_all, A2 injected clients, A4 NoOpCheckpointer, A5 transactional, H8 per-user rate limit, M1 idempotency wiring, M5 SSE reconnect, M7 step-up auth, M10 token persist (env), M14 timeouts |
| — | — **WAVE 15A: BACKEND EXTENSIONS (iOS)** — | — | — | — | — | — | — |
| **iOS1** | APNs Push Notification Backend | **Complete** | 20 | main | ~45 min | ~20 min | QA PASS_WITH_NOTES 2026-03-08: APNs service, batcher, device tokens, push hooks, migration 008 |
| **iOS2** | Voice Upload Endpoint | **Complete** | 17 | main | ~30 min | ~15 min | QA PASS_WITH_NOTES 2026-03-08: Whisper transcription, audio validation, chat mode, voice router |
| — | — **WAVE 15B: iOS FOUNDATION** — | — | — | — | — | — | — |
| **iOS3** | Xcode Project Scaffold & Networking Layer | **Complete** | 40+41 | main | ~60 min | ~90 min | QA PASS_WITH_NOTES 2026-03-08: SPM package, APIClient actor, SSEClient actor, Swift 6 strict concurrency |
| **iOS4** | Keychain Storage & Auth Flow | **Complete** | 20+16 | main | ~45 min | ~60 min | QA PASS_WITH_NOTES 2026-03-09: KeychainService, AuthService, AuthViewModel, LoginView, AuthGuard, auto-refresh |
| **iOS5** | Chat UI with SSE Streaming | **Complete** | 32+72 | main | ~60 min | ~90 min | QA PASS_WITH_NOTES 2026-03-09: ChatView, ChatViewModel, ThreadListView, MainTabView, NavigationSplitView |
| — | — **WAVE 15C: iOS FEATURES** — | — | — | — | — | — | — |
| **iOS6** | Push Notifications (APNs Client) | **Complete** | 23 | main | ~45 min | ~60 min | QA PASS_WITH_NOTES 2026-03-09: PushNotificationService, DeviceService, DeepLinkRouter, APNs entitlement |
| **iOS7** | Biometric Step-Up Auth & Approval Flow | **Complete** | 14 | main | ~45 min | ~60 min | QA PASS_WITH_NOTES 2026-03-09: BiometricService, ApprovalService, ApprovalListViewModel, ApprovalDetailViewModel, views, Approvals tab |
| **iOS8** | Voice Recording & Playback | **Complete** | 21+15 | main | ~60 min | ~90 min | QA PASS_WITH_NOTES 2026-03-09: AudioRecorderService, AudioPlayerService, VoiceService, dual-provider transcription (OpenAI/whisper.cpp), TranscriptionProviderView |
| **iOS9** | Offline Request Queue with Idempotency | **Complete** | 14 | main | ~45 min | ~30 min | QA pending: OfflineQueueService, NetworkMonitorService, APIClient offline intercept, OfflineIndicator |
| **iOS10** | VPN Auto-Connect & Certificate Pinning | **Complete** | 13 | main | ~30 min | ~45 min | QA PASS_WITH_NOTES 2026-03-09: CertificatePinningDelegate (SPKI), VPNService, VPNStatusBanner; wiring deferred to iOS11 |
| **iOS11** | Integration Tests & Polish | **Complete** | 35+13 | main | ~45 min | ~90 min | QA PASS_WITH_NOTES 2026-03-10: LoginFlowTests (IT1-4), ChatFlowTests (IT5-7), ApprovalFlowTests (IT8-10), OfflineQueueFlowTests (IT11-13), ErrorView, EmptyStateView; Literal["approved","denied"] fix |
| — | — **WAVE 17: MVP STUB ELIMINATION** — | — | — | — | — | — | — |
| **MV1** | Threads & Messages Real DB | **Complete** | 13 | main | ~35 min | ~30 min | All thread/message stubs replaced with real AsyncSession queries |
| **MV2** | Approvals List + Memory Facts | **Complete** | 16 | main | ~40 min | ~25 min | list_pending_approvals + MemoryStore CRUD wired via app_state |
| **MV3** | Usage, Queue & Artifacts | **Complete** | 16 | main | ~40 min | ~20 min | TaskQueue rows, Artifact+Run join, FileResponse download |
| **MV4** | iOS Certificate Pinning Wiring | **Complete** | 7 | main | ~35 min | ~20 min | ServiceFactory.swift composition root, #if DEBUG pinned URLSession |
| **MV5** | Integration Smoke & Verification | **Complete** | 14 | main | ~30 min | ~15 min | AST stub detector + wiring completeness gate; all stubs eliminated |
| — | — **WAVE 16: PLAYWRIGHT E2E TESTING** — | — | — | — | — | — | — |
| **PW1** | Playwright Setup & Auth Tests | **Complete** | 6 | main | ~30 min | ~10 min | QA PASS_WITH_NOTES 2026-03-07 |
| **PW2** | Chat E2E with SSE Simulation | **Complete** | 6 | main | ~30 min | ~15 min | QA PASS_WITH_NOTES 2026-03-07 |
| **PW3** | Settings & Navigation Tests | **Complete** | 6 | main | ~20 min | ~5 min | QA PASS_WITH_NOTES 2026-03-07 |
| — | — **WAVE 18: TOOL MANAGEMENT & CREDENTIALS** — | — | — | — | — | — | — |
| **TM1** | Tool Health-Check Endpoint & Credential Status | **Complete** | 20 | main | ~45 min | ~30 min | QA PASS_WITH_NOTES 2026-03-11: ToolHealthChecker (real httpx probes), CredentialStatusChecker, mask_credential, user-scoped credential store |
| **TM2** | Tools API Enrichment (Functions, Permissions, Metadata) | **Complete** | 20 | main | ~45 min | ~25 min | QA PASS_WITH_NOTES 2026-03-11: risk_tier+domain per function, function-level capabilities, nullable function_name in DB, per-function enable/disable endpoints |
| **TM3** | Tools UI Redesign — Dashboard & Health | **Complete** | 13 | main | ~60 min | ~20 min | Expandable cards, health indicators, CredentialModal, per-function toggles with risk badges, "Test Connection" button |
| **TM4** | Per-Task Tool Permissions & Context Scoping | **Complete** | 13 | main | ~45 min | ~15 min | ToolScopeRegistry (email_draft/research/scheduling), filter_tools_by_allowlist intersection, ApprovalRule.allowed_tools |
| **TM5** | Tool Registry: Add Custom Tools via UI | **Complete** | 18 | main | ~45 min | ~20 min | CustomTool model, HttpToolAdapter, schema validation, POST /tools registration, load_custom_tools from DB, name collision guard |
| **TM6** | MCP Server Connector (Phase 2 Bridge) | **Complete** | 18 | main | ~60 min | ~20 min | Real HTTP+SSE JSON-RPC 2.0 transport, MCP auto-discovery (tools/list), domain isolation in gateway, POST /mcp-servers endpoint |
| — | — **WAVE 19: PRODUCTION READINESS CLEANUP** — | — | — | — | — | — | — |
| **PR1** | Backend Critical Fixes (Data Integrity) | **Complete** | 19 | main | ~60 min | ~45 min | BE-C1: runs join usage_stats (real cost/token/model/duration_ms); BE-C2: user-scoped memory (all endpoints, public persist()); BE-H2: RunService fully async (select/execute pattern) |
| **PR2** | Frontend Critical Fixes (Broken Flows) | **Complete** | 10 | main | ~45 min | ~45 min | QA PASS_WITH_NOTES 2026-03-11: BE-H3/FE-C1 PATCH /settings; FE-H1 thread race (mutateAsync); FE-H2 RunDetail type cast removed |
| **PR3** | iOS Critical Fixes (Broken Flows) | **Complete** | 218 Swift | main | ~60 min | ~120 min | QA PASS_WITH_NOTES 2026-03-11 (cycle 2): iOS-H1 drain wiring, iOS-H2 SSE cancel on thread switch, iOS-H3 handleUnauthorized, iOS-H4 inline model picker; backend ChatRequest model/provider now optional |
| **PR4** | Backend Security & Robustness | **Complete** | 23 Python | main | ~45 min | ~50 min | BE-H1: ProviderRouter reloaded after credential update; BE-M3: path traversal guard in artifact download; BE-M2: MemoryStore public persist() interface verified; BE-M4: structured log context (user_id, run_id, trace_id) in orchestrator |
| **PR5** | Frontend & iOS Polish | **Complete** | 12 web + 233 Swift | main | ~45 min | ~90 min | QA PASS_WITH_NOTES 2026-03-11: FE-M1–M4 + iOS-M1–M5 all resolved; AuthContext cleanup, blob URL requestAnimationFrame, biometric retry guard |
| **PR6** | Integration Tests & Verification | **Complete** | 22 Python + 8 Swift | main | ~75 min | ~90 min | 22 ASGI-based Python integration tests (thread CRUD, settings round-trip, memory isolation, auth flow, artifact auth, approval flow, privacy mode). 8 live Swift tests against Docker backend (LB1–LB8: login, 401 guard, thread create/list, approval list, chat auth, offline queue drain, health, dup registration). FE-L1 finding added. |
| **PR7** | Wave 19 Audit Fix Cleanup | **Complete** | 20 Python | main | ~45 min | ~60 min | H1: privacy_mode Optional+Literal in ChatRequest (iOS 422 fix); H3: JWT error sanitized to "Invalid token"; M3: noa.coding deleted (no tests); M5: X-Content-Type-Options nosniff header; M6: success_envelope accepts list\|dict; L1: threads.py line length; L14 added to ARCH_INVARIANTS; CI-025 added to CLAUDE.md. M1/M2/M4 retained (have active tests). |
| — | — **WAVE 20: DEPLOYMENT & RELIABILITY + GOOGLE OAUTH2** — | — | — | — | — | — | — |
| **DE1** | CI/CD Pipeline | **Complete** | 74 | main | ~60 min | ~90 min | QA PASS_WITH_NOTES (cycle 2): ci.yml (3 jobs + Postgres service), cd.yml (ghcr.io push), web-ci.yml (E2E), ios-ci.yml (swift test), pre-push hook, gate tests |
| **DE2** | TLS & Reverse Proxy | **Complete** | 22 | main | ~60 min | ~20 min | QA PASS_WITH_NOTES: Caddyfile + compose + CORS + docs, 22 tests |
| **DE3** | Worker Container Hardening | **Complete** | 18 | main | ~45 min | ~20 min | QA PASS_WITH_NOTES: cap_drop/security_opt/limits on all services, Dockerfile HEALTHCHECK, _probe_worker tests |
| **DE4** | Backup Verification Automation | **Complete** | 20 | main | ~45 min | ~30 min | QA PASS_WITH_NOTES: verify_backup.sh (gpg→tmpfs→pg_restore→table check), GET /health/backup (ok/stale/failed/never_run), backups:ro mount |
| **GO1** | Google OAuth2 Backend | **Complete** | 28 | main | ~75 min | ~60 min | QA PASS_WITH_NOTES 2026-03-12: 4 OAuth routes (authorize/callback/status/disconnect), CSRF state, encrypted token storage, DB-first loading, env fallback |
| **GO2** | Web UI: Connect Google | **Complete** | 15 | main | ~45 min | ~40 min | Settings Google section (status/connect/disconnect), GoogleCallback page, /auth/google/callback route. 15 frontend tests. |
| **GO3** | iOS: OAuth2 via ASWebAuthenticationSession | **Complete** | 15 | main | ~60 min | ~50 min | GoogleAuthService (actor, WebAuthSessionProviding protocol), SettingsViewModel (@Observable), SettingsView (Google section with connect/disconnect/status), MainTabView updated. 203 Swift tests total (+15). |
| **Wave20-cleanup** | Pre-Wave-21 Findings Cleanup & CI Proposals | **Complete** | — | main | ~90 min | ~120 min | Fixed W20-C1/H1/H2/M1/M2, BE-H4/H5/M1/M5, FE-L1/M5, iOS-L1; applied CI-001–033 proposals; ruff gate expanded to tests/; per-file-ignores added. 109/112 findings resolved. |
| — | — **WAVE 21: PIPELINE EXCELLENCE & QUALITY INFRASTRUCTURE** — | — | — | — | — | — | — |
| **QE1** | CI Backlog Triage & Process Gate Application | **Complete** | 39 | main | ~45 min | ~20 min | All 33 CI proposals triaged (APPLIED/REJECTED/DEFERRED/RESOLVED); zero PROPOSED remaining; 39 verification tests confirm all gates in target files |
| **QE2** | Mypy Zero & Type Safety Enforcement | **Complete** | 25 | main | ~60 min | 60 min | 0 mypy errors (166 files); CI gate enforced (no continue-on-error); 25 tests |
| **QE3** | Open Findings Closure | **Complete** | 5 | main | ~30 min | ~20 min | QA PASS_WITH_NOTES: FINDINGS.md at 0 open; iOS-L2 #warning added; W20-MED-3 continue-on-error removed; W20-MED-4 stubs documented |
| **QE4** | Postgres Integration Tests | **Complete** | 30 | main | ~90 min | 90 min | QA PASS_WITH_NOTES: testcontainers + TEST_DATABASE_URL fallback; 30 integration tests across 6 suites; 2 schema drift migrations (010, 011) caught by tests |
| **QE5** | Requirements Traceability Matrix | **Complete** | 30 | main | ~45 min | ~17 min | QA PASS_WITH_NOTES: traceability.py, TRACEABILITY.md (97/128 covered, 9 Phase-2 deferred orphans), CI step with continue-on-error |
| **QE6** | Test Quality Infrastructure (Coverage, Mutation, Flaky Detection) | **Complete** | 16 | main | ~60 min | ~7 min | QA PASS_WITH_NOTES: pytest-cov (84% baseline, 70% threshold), mutmut config (auth/router/gateway), pytest-repeat nightly CI job |
| — | — **WAVE 22: FINDINGS FIXES & UX** — | — | — | — | — | — | — |
| **FR1** | Domain Isolation & Privacy Enforcement | **Complete** | 30 | main | ~45 min | ~60 min | QA PASS_WITH_NOTES 2026-03-13 (cycle 2): BE-C3 domain column + thread scoping, BE-H8 tool visibility by domain, BE-H11 provider filtering by privacy_mode, migration 014 |
| **FR2** | Memory & Session Fixes | **Complete** | 27 | main | ~60 min | ~60 min | BE-H6 (/data volume mount), BE-H7 (_handle_memory_approval), BE-H9 (external MemoryStore), BE-H10 (memory health), BE-H12 (logout cookie). 27 tests. |
| **FR3** | Backend Data Integrity & Infra | **Complete** | — | main | ~45 min | ~45 min | W21-H1 (usage_stats FK CASCADE), W21-H2 (backup setpgid), W21-M1 (/docs NOA_ENV gate), W21-M2 (traceability --check). Migration 015. |
| **FR4** | Chat & Streaming UX | **Complete** | — | main | ~60 min | ~60 min | UX-H1 (SSE keepalive 15s), UX-H2 (send always enabled), UX-H9 (optimistic message), UX-H10 (activity stream), UX-H5 (tool details), UX-H3 (system-prompt GET/PUT). Web components + runner. |
| **FR5** | Cost, Runs & Dashboard UX | **Complete** | 12 Python + 11 Web | main | ~60 min | ~60 min | QA PASS_WITH_NOTES 2026-03-13: UX-H7/H8/H11/M1/M7/H4/M5/M6 resolved. |
| **FR6** | Tools, Settings & Polish | **Complete** | 19 Python + 18 Web + 8 Swift | main | ~60 min | ~90 min | QA PASS_WITH_NOTES 2026-03-14: UX-H6/M2/M3/M4/M8/M9/M10/L1 + L10 + iOS-H5 resolved. Settings governance/agent-limits, thread rename PATCH, scope endpoints, Notion auto-grant. |
| — | — **WAVE 22 BOUNDARY** — | **Complete** | — | — | — | — | System audit 7.2/10. Retro done. CI analysis done (CI-042 P1). 3 new findings: W22-H1/H2 (dead-end stores), W22-M1 (runs/cost not domain-filtered). HUMAN GATE: approve CI-042 + Wave 23 plan. |
| — | — **AUTH STABILITY (pre-Wave 23)** — | — | — | — | — | — | — |
| **AU1** | Auth Stability — Session Validation & Error Clarity | **Complete** | 13 | main | ~60 min | ~55 min | Fixes AUTH-H1/H2/M1/M2: rate limiting removed, 7-day tokens, `/auth/me` startup check, `skipAuthRetry` on login, localStorage flag removed |
| — | — **WAVE 23: CODE QUALITY — TARGET 9/10** — | — | — | — | — | — | Audit: `docs/CODEBASE_AUDIT_2026-03-16.md`. Before: Arch 7, Wiring 5, Hygiene 6, Security 8, Testing 7, Modern 7, Frontend 7. |
| **CQ1** | Wire Unwired Features | **Complete** | 29 | main | ~60 min | ~30 min | DbCapabilityChecker→gateway (session_factory), load_custom_tools at startup, scope filtering in tool_node, preview already wired. AgentState+ChatRequest+runner tool_scope field. |
| **CQ2** | Delete Dead Governance Stack | **Complete** | — | main | ~30 min | ~15 min | Deleted governance.py, idempotency.py, rate_limiter.py, mcp_adapter.py, ToolRegistry, TOOL_ALLOWLIST, execute_tool, set_registry/get_registry. Updated 8 test files. |
| **CQ3** | Delete Frontend Dead Code | **Complete** | — | main | ~20 min | ~10 min | Deleted 12 unused files: JSONViewer + 11 shadcn/ui components (aspect-ratio, carousel, hover-card, input-otp, menubar, navigation-menu, pagination, resizable, toggle-group, context-menu, command). Build passes. |
| **CQ4** | Enums, Config Centralization, Magic Strings | **Complete** | 19 | main | ~30 min | ~30 min | PrivacyMode + RiskTier StrEnums in types.py. DEFAULT_EXTERNAL_MODEL/DEFAULT_PRIVATE_MODEL in config.py. Replaced magic strings in 10 files. 0 new ruff/mypy errors. |
| **CQ5** | Split Chat.tsx & Settings.tsx | **Complete** | 167 | main | 40 min | — | Chat.tsx 759→7 files (ThreadSidebar, ChatMessages, ApprovalCard, ChatComposer, useChatSSE, useOptimisticMessages). Settings.tsx 640→4 files (GeneralSettings, GoogleSettings, ToolSettings + providerModels.ts). Build passes, 0 new test failures. |
| **CQ6** | Strict Types & DI Cleanup | **Complete** | 23 | main | ~60 min | ~45 min | Typed app_state.py (ProviderRouter/OrchestratorRunner/ToolGateway/MemoryStore/APNsService). Typed agent.py _router. Typed chat.py/health.py/memory.py/cost.py DI helpers. Fixed all 5 pre-existing mypy errors → 0 errors. bool() cast for TypedDict access, removed unused type: ignore. |
| **CQ7** | Integration Tests for Wired Features | **Complete** | 22 | main | ~45 min | ~40 min | 16/22 tests pass (6 dead-code-absence tests pass after CQ2 runs). gateway.py: preview wired into approval path. Real DB tests for capability grant/deny/revoke, custom tool restore, scope filtering. |
| **CQ8** | Consistent Error Handling & SSE Contract | **Complete** | 33 (14 Python + 19 TS) | main | ~30 min | ~45 min | Created sse_types.py with 14 typed SSE event TypedDicts + VALID_SSE_EVENT_TYPES frozenset. Narrowed auth/service.py except Exception→TokenError, openai.py/anthropic.py except Exception→json.JSONDecodeError. Added noqa:BLE001 to 4 retention.py bare excepts. Added asString/asRecord/asStringArray helpers in utils.ts. Replaced all `as string` casts in ActivityStream, ExecutionDetails, EventTimeline, RunGraph, RunSummary, CostBreakdown, RawEventLog, useChatSSE. Frontend build clean, mypy 0 errors, ruff clean. |
| **CQ9** | Security Hardening (final) | **Complete** | — | main | ~20 min | ~5 min | Logging sanitizer (done), structured approval fields (migration 019 + model columns), CORS tests (done), responder defensive check (done). 3/4 already done, added migration. |
| — | — **WAVE 23 FINDINGS** — | — | — | — | — | — | **W23-H1**: External worker has no `/data` volume mount in `docker-compose.yml` or `docker-compose.dev.yml`. `MemoryStore(data_dir=Path("/data/memory/external"))` writes to ephemeral container layer — all external memory facts lost on restart. Fix: add `external-data:/data` volume to external-worker service + volumes section (mirror private worker). |

### Wave 24: Intelligence, Observability & Quality
Dependency order: RV1 [done] → W23-FIX → CX1 → DI1 → (MC1 ∥ LF1 ∥ LS1) → (OI1 ∥ VM1 ∥ LF2) → (PC1 ∥ OI5 ∥ OI6) → EV1 → (FB1 ∥ QV1) → EV2
ReAct mode (Thought→Action→Observation loop) active for research + decision_intelligence tasks only; gated by DI1 task_type; implemented inside OI1.

| ID | Phase | Status | Tests | Branch | Est. | Actual | Notes |
|----|-------|--------|-------|--------|------|--------|-------|
| **RV1** | Run Viewer — Event Payload & Cost Fixes | **Complete** | 8 TS | main | ~45 min | ~60 min | Fix 5 silent mismatches between backend event keys and frontend expectations: (1) `message_received.message` → frontend reads `.text`; (2) `error.error` → frontend reads `.message`; (3) `tool_called.tool_call.args` → frontend reads `.args` directly; (4) `tool_result.tool_result` → frontend reads `.result`; (5) `CostBreakdown` shows $0 everywhere — fix to parse `result_ready.llm_usage[]` (real per-call tokens+cost from agent node). Add `tool_start`/`tool_end` to `VALID_EVENT_TYPES` for future duration tracking. |
| **W23-FIX** | W23-H1 Fix — External Worker /data Volume | **Complete** | — | main | ~15 min | ~10 min | QA PASS_WITH_NOTES 2026-03-20: external-data:/data volume added to both compose files |
| **CX1** | Quick Fixes — Checkpointer + Idempotency + Doom Loop | **Complete** | 22 | main | ~45 min | ~45 min | QA PASS_WITH_NOTES 2026-03-20: pg_insert upsert, IdempotencyKey DB table + sweep, DoomLoopError in tool_node |
| **DI1** | Task Classifier | **Complete** | 30 unit | main | ~45 min | ~60 min | Add `task_type` to AgentState + ModelConfig classifier field. New `nodes/classifier.py`: cheap LLM call (GPT-4o-mini/private model) reads last user message and outputs task_type. Graph wired: router → classifier → agent. Classifier uses empty tools list, falls back to "execution" on error. |
| **MC1** | Per-Node Model Configuration | **Complete** | 13 unit | main | ~45 min | — | Expose MR8's `ModelConfig` per-node defaults to user via Settings UI. New `Settings → Intelligence` section: dropdown per node type (Classifier, Planner, Agent, Evaluator) populated from available providers/models in `providerModels.ts`. Backend: `PATCH /settings` extended with `node_models: {classifier, planner, agent, evaluator}` object; stored in `settings` table. `runner.py` reads node_models from settings at run time and passes correct model to each node's LLM call. Defaults: classifier/evaluator → cheapest available model (Haiku or GPT-4o-mini); planner → Sonnet; agent → user's current default. Also exposes model config for AI-backed tools: Transcription provider (OpenAI Whisper / whisper.cpp) and Embeddings model (nomic-embed-text / OpenAI) once VM1 exists. iOS: SettingsViewModel updated with Intelligence section. Parallel with LF1 + LS1. |
| **LF1** | Langfuse Self-Hosted + Backend Instrumentation | **Complete** | 19 unit | main | ~60 min | ~30 min | langfuse + langfuse-db in docker-compose.yml. langfuse>=2.0.0 in pyproject.toml. TraceContext in noa.observability.langfuse_client — one trace per run, generation spans from llm_usage, tool spans from tool_results, graceful no-op when unavailable. Runner instrumented. 19 tests. |
| **LS1** | LLM Token Streaming | **Complete** | 15 unit | main | ~90 min | — | Fixes TECH-H1. Add stream=True to Anthropic, OpenAI, Google AI, and Ollama clients. Runner yields `token` SSE events per partial chunk. Frontend renders tokens incrementally (already handles SSE). Ollama already has a streaming API; Anthropic/OpenAI use server-sent events natively. Parallel with LF1. |
| **LF2** | Traces Page — Langfuse Iframe Embed | **Complete** | 0 | main | ~45 min | ~15 min | New `/traces` route in web app. Full-height iframe embedding self-hosted Langfuse UI (langfuse:3000). AppSidebar nav entry. RunDetail "View Trace" button navigates to `/traces?traceId=<run_id>`. Depends on LF1 only. Parallel with OI1 + VM1. |
| **OI1** | Planning Node + ReAct Execution | **Complete** | 25 unit | main | ~60 min | — | Add `plan`, `archetype`, `thoughts: list[ThoughtStep]`, `use_react: bool` to AgentState. Create `nodes/planner.py` (LLM call without tools): reads task_type (from DI1), selects archetype (comparative_selection / prioritization / diagnosis / research / execution), sets `use_react=True` for research + decision_intelligence tasks. Each archetype defines: solve pattern, stop criteria, eval rubric extension. Planner output injected as system context for agent. ReAct mode: agent node uses Thought→Action→Observation prompt template; Thought parsed from each response before tool_calls extracted; stored as `ThoughtStep(step, text, action)` in AgentState; forwarded to Langfuse (LF1) as span annotations. simple_utility + execution tasks skip ReAct entirely (no token overhead). EV1 receives `thoughts` for reasoning-chain evaluation via a sixth rubric dimension `reasoning_coherence` (research/decision tasks only). Parallel with VM1 + LF2. |
| **VM1** | Private Vector Memory (pgvector + Ollama embeddings) | **Complete** | 20 unit | main | ~60 min | ~60 min | Replace placeholder embeddings in MemoryStore with real `nomic-embed-text` via Ollama. Add pgvector extension + `embedding` column to memory_facts. Wire `rag_ingest`, `rag_query`, `summarize`, `search` RPC handlers in private worker. Cosine similarity recall replaces stub. Memory trust tiers: ephemeral (AgentState only, not persisted) / candidate (status=pending) / trusted (status=approved) — vector search runs against trusted only by default. Parallel with OI1 + LF2. |
| **PC1** | Privacy Classifier — Configurable + Semantic | **Complete** | 31 unit | main | ~60 min | — | Two improvements: (1) expose `private_keywords` as a user-configurable list in Settings UI + PATCH /settings. (2) Add semantic scoring via `nomic-embed-text` from VM1 Ollama — cosine similarity against a "private intent" embedding catches "draft my resignation letter" that keywords miss. Keyword OR semantic threshold triggers private mode. Depends on VM1. Parallel with OI5 + OI6. |
| **OI5** | Audit Trail UI | **Complete** | 12 unit | main | ~45 min | — | Per-run audit trail view (linked from activity stream via trace_id), chain integrity indicator on health dashboard, filterable audit log page (date/action/tool/domain), JSON export. Backend endpoints exist (`/audit/entries`, `/audit/verify`), needs frontend wiring only. No new backend dependencies — runs after OI1 group completes. Parallel with PC1 + OI6. |
| **OI6** | Proactive Memory Extraction (zero-cost) | **Complete** | — | — | ~30 min | — | Wire `auto_extract` as an available tool in agent turns. System prompt instructs LLM to call it alongside normal responses when user shares personal facts/preferences/scheduling. No extra LLM call — piggybacks on existing agent turn. Facts land as `status: "pending"` (candidate memory tier), user approves in Memory UI. `auto_extraction_enabled` flag already exists in MemoryTool. Pre-compaction flush: when context compaction triggers (CC1), before summarising, the runner first calls `auto_extract` to preserve any user facts in the current context — facts saved to memory survive the context reset. Depends on OI1. Parallel with PC1 + OI5. |
| **EV1** | Evaluation Node | **Complete** | 42 unit | main | ~60 min | ~60 min | LangGraph node after responder. Cheap model scores response on 5 base dimensions + archetype extensions. Verdict: pass/reroute/flag. Reroute injects feedback (max 2 cycles). response_evaluations table + migration 024. Langfuse score() calls for all dimensions. simple_utility skips evaluation. 2026-03-20 |
| **FB1** | User Feedback Loop — Response Ratings | **Complete** | 12 unit | main | ~60 min | ~45 min | Thumbs up/down on each assistant message in ChatMessages.tsx. POST /api/v1/ratings endpoint writes to `response_ratings` table and writes back to `response_evaluations.user_rating` (user_rating becomes ground truth for rubric calibration). Quality score widget on Cost dashboard (% positive over 7d/30d). Parallel with QV1. 2026-03-20 |
| **QV1** | LLM Quality Evaluation Framework | **Complete** | 65 unit | main | ~45 min | ~30 min | 13 quality fixtures across 6 categories (simple_utility, execution, research, decision_intelligence, privacy routing, tool selection). Tests assert rubric thresholds via mocked evaluator_node (goal_alignment >= 3.5, grounding >= 4.0 for research, completeness >= 3.0 all). Classifier accuracy and planner archetype coverage. @pytest.mark.quality CI gate. 2026-03-20 |
| **EV2** | Self-Improvement Analytics | **Complete** | 15 unit | main | ~45 min | ~90 min | Completes the quality flywheel. `GET /analytics/eval-trends` + `GET /analytics/worst-dimensions`. Aggregation by dimension / model / task_type / archetype. Divergence detector (user_rating vs eval >1.5 threshold). Quality Trends dashboard widget in Cost.tsx: horizontal bar chart, worst-dimension progress bars, divergence alert banner. UUID hex-vs-hyphen fix for cross-engine SQLite compatibility. 2026-03-20 |

### Wave 24B: Architecture & Security
| ID | Phase | Status | Tests | Branch | Est. | Actual | Notes |
|----|-------|--------|-------|--------|------|--------|-------|
| **CC1** | Context Window Compaction | **Complete** | 28 | main | ~60 min | ~45 min | token_budget.py (model context windows, 80% threshold), compactor.py (cheap LLM summary, keep_recent=6), runner wired, CompactionEvent SSE type, checkpoint save after compaction |
| **OI7** | Cross-Domain Step-Up Approval | **Complete** | 15 | main | ~60 min | ~30 min | Gateway returns approval_required instead of PermissionError for cross-domain, privacy_mode wired through tool_node, runner emits cross_domain+reason in approval event |
| **OI8** | Smart Domain Redirect (cross-domain UX) | **Complete** | 6 | main | ~45 min | ~20 min | 403 DOMAIN_MISMATCH replaced with auto-redirect, new thread created in correct domain, meta event includes redirected/original_thread_id, frontend toast + thread switch |
| **LS2** | Orchestrator Timeout Watchdog | **Complete** | 7 | main | ~30 min | ~15 min | time.monotonic() check after each node, error SSE with TIMEOUT code, run marked failed, stream callback cleared |
| **RLS1** | Postgres Row-Level Security | **Complete** | 16 | main | ~90 min | ~30 min | Migration 025: RLS on 6 tables (conversations, approvals, memory_facts, audit_log, custom_tools, runs), transaction-local set_config, SQLite-safe skip, rls.py helpers |
| **W24B-FIX** | Audit Finding Fixes | **Complete** | — | main | — | ~5 min | W24-AUDIT-H1: Langfuse env vars in dev-full compose. H2+H3 already resolved. Mypy chat.py comparison-overlap fix. |

### Wave 25: Polish & Extended Capabilities

| ID | Phase | Status | Tests | Branch | Est. | Actual | Notes |
|----|-------|--------|-------|--------|------|--------|-------|
| **SEC1** | JWT Token Revocation | **Complete** | 16 | main | ~45 min | ~20 min | TokenBlacklist table, middleware check, logout revocation, hourly sweeper. Resolves TECH-M1. |
| **KM1** | Kimi 2.5 LLM Provider (Moonshot AI) | **Complete** | 19 | main | ~60 min | ~15 min | KimiClient (OpenAI-compatible), router registration, config + DB + frontend. Models: kimi-k2, moonshot-v1-128k. |
| **BU1** | Frontend Bundle Optimization | **Complete** | — | main | ~45 min | ~10 min | 13 lazy routes, manualChunks (react/router/charts/radix/query), check-bundle-size.sh (500KB gate). |
| **VX1** | Voice UX Refinement | **Complete** | 7 TS | main | ~60 min | ~15 min | useVoiceRecorder hook, mic button in ChatComposer, recording bar, transcription via /voice/transcribe. |
| **IS1** | iOS Widget & Shortcuts Integration | **Complete** | 19 Swift | main | ~90 min | ~30 min | WidgetKit widget (small/medium, last thread), SharedDataManager (App Groups), SendMessage+ListThreads AppIntents, Siri phrases. |

**Deferred (Phase 2):** TECH-M3 Egress control — external egress proxy (squid/mitmproxy) sidecar enforcing `noa.egress.allowlist` labels.
**Deferred (long-term):** TECH-L1 Privacy classifier full ML — conversation-context-aware routing (PC1 covers the practical improvement).

---

## Deployment Roadmap

### Stage 1 — Local Development (current)
- Backend: Docker on Mac (`localhost:8000`)
- iOS app: installed via Xcode, Developer Mode required
- Networking: **Tailscale** — Mac + iPhone in private VPN mesh, stable `100.x.x.x` IP, no third-party relay
- Environment: `NoaEnvironment.development` → Mac's Tailscale IP

### Stage 2 — Personal TestFlight
- **Apple Developer Program** (€99/year) required
- App distributed via TestFlight — no Developer Mode, no 7-day expiry, up to 90 days per build
- Backend still on Mac or moved to a small VPS (Hetzner CX22 ~€4/mo, fly.io free tier)
- APNs: configure real key in Apple Developer Portal → update `APNS_KEY_PATH` / `APNS_KEY_ID` / `APNS_TEAM_ID`
- HTTPS: Let's Encrypt or Cloudflare proxy

### Stage 3 — Production / App Store
- Backend on dedicated server with domain + TLS
- Certificate pinning active (Release build, `CertificatePinningDelegate`)
- `NOA_BASE_URL` set in Info.plist (production environment)
- App Store submission or Ad Hoc distribution
- Monitoring: structured logs, health checks (already implemented in OP1–OP5)

