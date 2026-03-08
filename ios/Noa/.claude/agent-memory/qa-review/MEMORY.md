# QA Review Agent Memory (iOS)

## Project Structure
- iOS code lives at `/Users/martin2020/Projekte/NoaOS/ios/Noa/` (SPM package, not xcodeproj)
- Plan docs are at `/Users/martin2020/Projekte/NoaOS/Plan/` (root, not inside ios/Noa/)
- Swift 6 strict concurrency enforced via swift-tools-version: 6.0
- Test target named `NaoTests` (note: Nao, not Noa -- naming inconsistency)

## Backend Contract Tests Pattern
- Backend contract tests in `tests/unit/test_ios{N}_*.py` pin the JSON shapes iOS must decode
- These import real backend modules (schemas, middleware) -- not mocks
- Always verify Swift CodingKeys match backend field names exactly

## Recurring Patterns to Watch
- `@unchecked Sendable` escape hatches -- check if T constraints could be tightened instead
- `nonisolated(unsafe)` on test helpers (MockURLProtocol.handler) -- acceptable for serial tests
- `try?` in streaming parsers -- document as intentional resilience, verify error callback exists
- SSEClient reconnection logic is complex (while-true loop) but has no behavioral test coverage as of iOS3
- `timeoutIntervalForRequest = 0` may not mean "no timeout" on all platforms

## Key Backend Schemas (iOS model must match)
- Envelope: `{ok, data, error, trace_id}` -- flat trace_id, NOT nested meta object
- Run: `{id, thread_id, user_id, status, risk_tier, privacy_mode, summary, created_at, updated_at}`
- Approval: `{id, run_id, user_id, risk_tier, preview_text, decision, domain, requested_at, decided_at, decided_by_user_id}`
- SSE event types: 12 total including "meta"

## Review Process Notes
- `swift test` runs at `/Users/martin2020/Projekte/NoaOS/ios/Noa/`
- Backend contract tests run in Docker: `docker exec noa-dev pytest tests/unit/test_ios3_networking_contract.py`
- For iOS phases, M7 (wiring) is assessed differently -- library package has no app entry point until iOS4/iOS5
- M8 (domain isolation) is N/A for pure iOS packages
