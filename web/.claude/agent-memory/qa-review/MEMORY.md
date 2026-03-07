# QA Review Agent Memory

## Project: NoaOS / Noa Web

### Plan directory location
`/Users/martin2020/Projekte/NoaOS/Plan/` (NOT web/Plan/)

### Recurring Anti-Patterns Found

#### Frontend (QC6, 2026-03-07)
- **Radix Select invisible in jsdom**: Radix UI Select does not render option list without user interaction in jsdom. Tests checking for absent model names via `container.innerHTML` only check the trigger — this is a weak signal. Prefer opening the select and asserting visible options.
- **Bare catch swallowing test scaffolding**: `vi.doMock` + `try { ... } catch {}` patterns in test helpers are acceptable — don't flag as M6 violations in test code.
- **`capturedOnEvent.toBeDefined()` pattern is weak**: Multiple UI-C2 tests assert only that a callback was registered, not that the state change actually occurred. Flag this as an S5/M2 gap.
- **ErrorBoundary retry semantics**: Class-based `handleRetry` that resets error state will re-throw immediately if child failure is deterministic. Document this as a note, not a blocking issue.
- **SSEClient `this.runId` capture vs event.data.run_id mismatch**: SSEClient captures `parsed.run_id` (outer JSON) for reconnection, but Chat component reads `event.data.run_id` (inside payload). If backend puts run_id inside payload, reconnection silently fails.

#### Backend (earlier phases)
- Bare `except Exception: pass` was pervasive (fixed in QC3)
- `commit()` in repository layer (fixed in QC3)
- Settings query: error state often unhandled — user sees infinite loading

### Test Quality Patterns
- Tests in this project use `vi.doMock` + `vi.resetModules()` for dynamic mocking — required for module-level constants like BASE_URL
- All frontend tests mock `apiRequest` — no true integration tests exist
- S5 (integration smoke test) is consistently OPEN for frontend phases

### Wiring Checklist for Frontend Phases
- Check ErrorBoundary is in `ProtectedRoute`, not just individual pages
- Check `useQueryClient` is imported AND hook is called, not just the clear invoked
- Check provider dropdown values match `Provider` type union exactly

### Security Patterns
- `tokens.ts`: Auth flag in localStorage, actual tokens in httpOnly cookies — correct per C6 fix
- `getAccessToken()` returning null means SSE Authorization header is omitted — relies on cookies

### File Locations
- Frontend tests: `web/src/test/`
- Frontend source: `web/src/`
- vitest config: `web/vitest.config.ts`
- QA reviews: `Plan/REVIEWS/review_{phase-id}.md`
