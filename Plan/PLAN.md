# PLAN.md — Noa Implementation Plan

## Overview

This plan implements Noa Phase 1–3 (single-machine deployment + native iOS client) as specified in SPEC.md v5.0. The plan follows the build order defined in SPEC.md §36 and covers Backend Foundation (Build Phase 1), Web Client (Build Phase 2), and Native iOS Client (Build Phase 3). Dual-machine deployment (Build Phase 4) is deferred to future planning.

The plan is organized into **waves** — groups of related phases that deliver a cohesive capability. Each wave has a human gate before execution begins.

---

## Key Documents

- **[FINDINGS.md](FINDINGS.md)** — 49 audit findings (49 resolved, 0 open, 0 partially resolved). Updated inline when findings are resolved.
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
| **iOS5** | Chat UI with SSE Streaming | Planned | — | — | ~60 min | — | ChatView, token streaming, threads, NavigationSplitView |
| — | — **WAVE 15C: iOS FEATURES** — | — | — | — | — | — | — |
| **iOS6** | Push Notifications (APNs Client) | Planned | — | — | ~45 min | — | UNUserNotificationCenter, deep linking, inline actions |
| **iOS7** | Biometric Step-Up Auth & Approval Flow | Planned | — | — | ~45 min | — | Face ID/Touch ID, approval UI, batch approve/deny |
| **iOS8** | Voice Recording & Playback | Planned | — | — | ~45 min | — | AVAudioRecorder, upload to /voice/transcribe, auto-send |
| **iOS9** | Offline Request Queue with Idempotency | Planned | — | — | ~45 min | — | File-based FIFO queue, NWPathMonitor, auto-drain |
| **iOS10** | VPN Auto-Connect & Certificate Pinning | Planned | — | — | ~30 min | — | SPKI pinning, NEVPNManager, Tailscale/WireGuard URL scheme |
| **iOS11** | Integration Tests & Polish | Planned | — | — | ~45 min | — | E2E tests, accessibility, dark mode, error states |
| — | — **WAVE 16: PLAYWRIGHT E2E TESTING** — | — | — | — | — | — | — |
| **PW1** | Playwright Setup & Auth Tests | **Complete** | 6 | main | ~30 min | ~10 min | QA PASS_WITH_NOTES 2026-03-07 |
| **PW2** | Chat E2E with SSE Simulation | **Complete** | 6 | main | ~30 min | ~15 min | QA PASS_WITH_NOTES 2026-03-07 |
| **PW3** | Settings & Navigation Tests | **Complete** | 6 | main | ~20 min | ~5 min | QA PASS_WITH_NOTES 2026-03-07 |

