# QA Review: Phase QC6

**Date:** 2026-03-07
**Verdict:** PASS_WITH_NOTES
**Reviewer:** qa-review agent

## Checklist Score
**Must-haves:** 8/8 | **Should-haves:** 3/5

| ID | Criterion | Result | Notes |
|----|-----------|--------|-------|
| M1 | Spec Traceability | PASS | Tests cite finding IDs (UI-C1 through UI-H5) in every describe block, which qualifies as PLAN Phase ID tracing per checklist. No SPEC.md §section citations — acceptable because frontend findings map to PLAN findings, not spec sections. |
| M2 | Negative Tests | PASS | UI-H3 has three distinct negative path tests (negative number, NaN/empty, daily > monthly). UI-H4 tests throw-on-render. UI-H5 tests cancel path. |
| M3 | Security Boundaries | PASS | No hardcoded secrets. Token storage uses localStorage only for an auth flag — actual tokens are in httpOnly cookies (C6 fix is intact). `tokens.ts` `getAccessToken()` returns null. CORS not in scope for frontend-only changes. |
| M4 | Determinism | PASS | No wall-clock time in tests. No real network calls — all apiRequest mocked via `vi.doMock`. No unseeded randomness. |
| M5 | Implementation Completeness | PASS | All 8 files from the phase file table are present and modified/created. All 8 deliverables implemented: BASE_URL fix, meta handler, queryClient.clear, google_ai type, model filtering, budget validation, ErrorBoundary, AlertDialog. |
| M6 | No Silent Error Swallowing | PASS | `sse.ts:117` `catch {}` is intentional — skips malformed SSE JSON with inline comment, not a spec-critical path. `client.ts:42` `catch {}` is pre-existing code outside QC6 scope. No new bare catches introduced in QC6 files. |
| M7 | Wiring Completeness | PASS | ErrorBoundary imported and wired into `ProtectedRoute` in `App.tsx:37`. All page-level components unchanged structurally. AlertDialog wired directly into Memory component. |
| M8 | Domain Isolation | PASS | Frontend-only phase. No Python package cross-imports possible. No `noa.private_worker` / `noa.external_worker` boundary concerns. |
| S1 | Error Handling & Boundaries | OPEN | ErrorBoundary `handleRetry` resets state but does not remount the failed subtree — retrying a deterministically-broken child will re-throw immediately. See Notes #2. |
| S2 | Code Consistency | PASS | Naming conventions followed. `PROVIDER_MODELS` exported from Settings.tsx — consistent with how test imports it. `handleProviderChange` / `validateBudgets` naming follows existing patterns. |
| S3 | Migration & Rollback | N/A | No DB schema changes in this phase. |
| S4 | Documentation | OPEN | Tests lack SPEC.md section references in docstrings (M1 note). `ErrorBoundary.tsx` has no JSDoc for public `handleRetry`. `PROVIDER_MODELS` export has no comment explaining the structure. |
| S5 | Integration Smoke Test | OPEN | Every test mocks `apiRequest` via `vi.doMock`. No test exercises the real module chain (e.g., real SSEClient parsing real SSE bytes). The UI-C2 "meta event with run_id sets currentRunId" test only asserts `capturedOnEvent` is defined — it never actually verifies that `currentRunId` state in Chat changes. See Notes #3. |

---

## Spec Compliance

QC6 addresses frontend findings UI-C1 through UI-H5. These are not directly tied to a SPEC.md section but to FINDINGS.md entries from the frontend audit. Compliance is assessed against those findings:

| Finding | Requirement | Implemented | Evidence |
|---------|-------------|-------------|---------|
| UI-C1 | `sse.ts` BASE_URL defaults to `""` | YES | `sse.ts:4`: `const BASE_URL = import.meta.env.VITE_API_BASE_URL \|\| "";` |
| UI-C2 | `handleSSEEvent` handles `"meta"` event, calls `setCurrentRunId` | YES | `Chat.tsx:139-143`: `case "meta": if (event.data.run_id) { setCurrentRunId(...) }` |
| UI-C2 | `result_ready` invalidates messages query | YES | `Chat.tsx:150`: `queryClient.invalidateQueries({ queryKey: ["messages", activeThread] })` |
| UI-C3 | `queryClient.clear()` called on logout | YES | `AuthContext.tsx:71`: `queryClient.clear()` before `setIsAuthenticated(false)` |
| UI-H1 | `"google_ai"` added to `Provider` type | YES | `types.ts:49`: `"google_ai"` in union |
| UI-H1 | Provider dropdown uses `"google_ai"` value | YES | `Settings.tsx:168`: `<SelectItem value="google_ai">` |
| UI-H2 | Model dropdown filtered by provider | YES | `Settings.tsx:133`: `const availableModels = PROVIDER_MODELS[provider] \|\| []` |
| UI-H2 | Provider change resets model if current invalid | YES | `Settings.tsx:72-80`: `handleProviderChange` resets to `models[0].value` |
| UI-H3 | `min="0"` on budget inputs | YES | `Settings.tsx:211,215`: `min="0" step="0.01"` on both inputs |
| UI-H3 | Budget validation: daily <= monthly, no negatives, no NaN | YES | `Settings.tsx:84-102`: `validateBudgets()` function |
| UI-H4 | ErrorBoundary component at ProtectedRoute level | YES | `App.tsx:37`: `<ErrorBoundary>{children}</ErrorBoundary>` inside `ProtectedRoute` |
| UI-H4 | Fallback shows "Something went wrong" with retry button | YES | `ErrorBoundary.tsx:33-46` |
| UI-H5 | AlertDialog confirmation before delete | YES | `Memory.tsx:64-76, 232-245` |

All deliverables from the phase plan are implemented.

---

## Test Coverage

| Test Suite | Finding | Tests | Negative Path? | Quality |
|------------|---------|-------|----------------|---------|
| UI-C1 SSE BASE_URL | UI-C1 | 2 | Yes (wrong URL check) | Good — captures actual fetch URL |
| UI-C2 meta event | UI-C2 | 4 | Partial | WEAK: 2 of 4 tests only assert `capturedOnEvent.toBeDefined()`, not that `currentRunId` changes |
| UI-C3 logout cache | UI-C3 | 3 | Yes (regression guards) | Good — verifies cache emptied, tokens cleared, auth state |
| UI-H1 provider type | UI-H1 | 2 | No | Acceptable — type-level; save payload verified |
| UI-H2 model filtering | UI-H2 | 5 | Yes (cross-provider models absent) | Caution: Radix Select doesn't render options without interaction in jsdom — filtering assertions check innerHTML, not actual options |
| UI-H3 budget validation | UI-H3 | 4 | Yes (negative, NaN, daily>monthly) | Good — covers all three error cases + happy path |
| UI-H4 error boundary | UI-H4 | 3 | Yes (throw-on-render) | Good — covers error, retry button, happy path |
| UI-H5 delete confirm | UI-H5 | 3 | Yes (cancel path) | Good |

Total: 26 tests across 8 finding groups.

**Gap:** No test verifies that switching providers in the UI actually updates the displayed model dropdown options (the Radix Select component doesn't render options without user interaction in jsdom). The filtering tests check `container.innerHTML` which only includes the currently visible trigger, not the option list.

---

## Anti-Pattern Scan Results

### Bare catch blocks in QC6-modified files:

```
src/api/sse.ts:117:  } catch {
  // skip malformed events — intentional, JSON parse failure on malformed SSE data
```

```
src/api/client.ts:42:  } catch {
  clearTokens();
  return false;
  // Pre-existing, not introduced by QC6
```

```
src/test/qc6-fixes.test.tsx:48,76,459,824,854,884:  } catch {
  // expected — test scaffolding catches mock failures; acceptable in tests
```

No new bare catches introduced by QC6. The `sse.ts:117` catch is intentional with comment.

### Domain isolation:
```
# No private_worker imports in external_worker (frontend phase, N/A for Python)
# No cross-domain import violations in frontend code
```

### Router/service wiring:
```
# ErrorBoundary: wired at App.tsx:37 inside ProtectedRoute
# All imports verified in App.tsx:22 — ErrorBoundary imported
# No new FastAPI routers (frontend-only phase)
```

---

## Smoke Test Results

Tests run: 26/26 (per developer report — Bash execution not available in this review session)

Key behavioral verification via code inspection:

**UI-C1 verified:** `sse.ts:4` is `const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";` — matches `client.ts:5`. Finding fixed.

**UI-C2 verified:** `Chat.tsx:138-155` switch statement includes `case "meta"` at line 139. `setCurrentRunId` called at line 141. `queryClient.invalidateQueries` at line 150 in `result_ready` case.

**UI-C3 verified:** `AuthContext.tsx:71` calls `queryClient.clear()` before `setIsAuthenticated(false)`. The `useQueryClient()` hook is imported at line 2 and called at line 18.

**UI-H1 verified:** `types.ts:49` — `Provider` union includes `"google_ai"`. `Settings.tsx:168` — SelectItem value is `"google_ai"` not `"google"`.

**UI-H2 verified:** `PROVIDER_MODELS` map at `Settings.tsx:13-29` covers all 4 providers. `handleProviderChange` at line 72 resets model on provider switch. `availableModels` at line 133 filters by current provider.

**UI-H3 verified:** `Settings.tsx:211,215` — both inputs have `min="0" step="0.01"`. `validateBudgets()` at line 84 catches NaN, negative, and daily > monthly.

**UI-H4 verified:** `ErrorBoundary.tsx` exists with class component, `getDerivedStateFromError`, and retry button. `App.tsx:37` wraps children with `<ErrorBoundary>`.

**UI-H5 verified:** `Memory.tsx` imports AlertDialog components at lines 11-20. `deleteTargetId` state drives dialog open/close. `handleDeleteClick` sets target; `handleDeleteConfirm` triggers mutation only on confirm.

---

## Security

**No new security issues introduced.**

- Token storage: `tokens.ts` stores only an authentication flag (`noa_authenticated`) in localStorage. Actual tokens remain in httpOnly cookies (C6 fix from QC2 intact). `getAccessToken()` returns `null`.
- No hardcoded secrets or API keys in any modified file.
- Budget validation prevents NaN values from reaching the backend.
- AlertDialog for Memory delete adds a confirmation gate for destructive actions.
- CORS: Not modified in this phase.

**Pre-existing concern (not new to QC6):** `client.ts:42` catch block silently clears tokens on any error, including transient network failures, which could log users out unexpectedly. This is pre-existing and outside QC6 scope.

---

## Code Quality

**Positive patterns:**
- `PROVIDER_MODELS` constant is exported from `Settings.tsx` — allows test assertions against it directly.
- `handleProviderChange` correctly preserves model selection if the model is valid for the new provider.
- `validateBudgets` is separated from the submit handler — clean separation.
- `ErrorBoundary` uses correct React class component lifecycle (`getDerivedStateFromError` is static, `componentDidCatch` logs error info).

**Issues:**

1. `App.tsx:33` references `React.ReactNode` without importing `React`. With `react-jsx` JSX transform and `strict: false`, this compiles — types are erased at runtime. But this is a latent issue if `strict` is ever enabled.

2. `ErrorBoundary.tsx:27-29` — `handleRetry` resets `hasError: false` but does NOT remount the failed child. If the child's render continues to throw (e.g., a query that keeps returning an error), the retry immediately re-throws and the boundary catches it again. The user sees a flash of children followed by the error UI. This is misleading — the button label "Try Again" implies a retryable operation, but it only unmounts the error state, not the underlying failure.

3. `sse.ts:137-147` — `tryReconnect` guard `if (this.closed || !this.runId) return` means reconnection is silently skipped if no `run_id` was captured. The SSE client captures `run_id` from `parsed.run_id` (the outer JSON payload, line 103), but the Chat component's `handleSSEEvent` reads it from `event.data.run_id`. These read from different levels of the parsed JSON. If the backend sends `{ "event_type": "meta", "payload": { "run_id": "..." } }`, then `parsed.run_id` is undefined (run_id is inside payload) but `event.data.run_id` is defined. This means Chat component shows the correct run ID but the SSE client cannot reconnect after a disconnect. This is a pre-existing M5 (SSE Reconnection) issue, but the interaction between QC6's meta handler and the SSEClient's reconnect guard needs attention.

4. `Settings.tsx` — The `initialized` guard (lines 135-143) shows "Loading settings..." until settings fetch completes. This means on slow connections, the Save button is absent. If the settings query fails (network error), `initialized` never becomes `true` and the user sees a perpetual loading state with no error message. There is no error state handled for the settings query in the Settings component.

---

## Blocking Issues

None. All M1-M8 criteria pass.

---

## Notes (PASS_WITH_NOTES)

1. **Test weakness — UI-C2 tests at lines 119 and 175:** Both tests assert only `expect(capturedOnEvent).toBeDefined()` after rendering the Chat component. This verifies the SSEClient callback is registered but does NOT verify that receiving a `"meta"` event actually sets `currentRunId` state. To properly test UI-C2, the test needs to call `capturedOnEvent({ event: "meta", data: { run_id: "run-123" } })` and then assert on the rendered output (e.g., check `ActivityStream` props or `data-testid` showing the run ID). The test as written would pass even if the `"meta"` case in `handleSSEEvent` was deleted.

2. **ErrorBoundary retry semantics are misleading:** `handleRetry` at `ErrorBoundary.tsx:27` resets error state, which causes React to re-render the child. If the child renders synchronously without any async recovery (e.g., the React Query error hasn't been cleared), it will immediately throw again. Consider either: (a) accepting this as-is and changing the button label to "Dismiss", or (b) calling `window.location.reload()` for a true retry, or (c) accepting a `fallback` render prop instead of a hardcoded recovery button. This is a functional limitation that may confuse end users.

3. **Radix Select options invisible in jsdom:** The UI-H2 model filtering tests check `container.innerHTML` for absent model names. Since Radix Select only renders the trigger button by default (not the full option list) until user interaction, these tests are actually checking that the model label text doesn't appear in the trigger. This is a weak signal — the trigger shows only the selected model value, not all options. The tests pass currently because the trigger shows "Claude Sonnet 4" (not "GPT-4.1") when provider is "anthropic". However, if Radix changes its rendering behavior, these tests could produce false positives. A stronger approach would be to open the select, then assert which options appear.

4. **Settings query failure is unhandled:** `Settings.tsx` has no `isError` or `error` handling for the initial settings fetch. If the API is down, the user sees "Loading settings..." forever. Add an error state that shows a retry button.

5. **`SSEClient.tryReconnect` will not trigger after QC6:** The SSE client captures `run_id` at `sse.ts:103` from `parsed.run_id`. But if the backend sends run_id inside a meta payload (i.e., `{ event_type: "meta", payload: { run_id: "..." } }`), then `parsed.run_id` is undefined (the run_id is under `payload`), while `event.data.run_id` correctly extracts it. This means the Chat component can display the run ID, but `this.runId` in the SSEClient is never set, so reconnection after disconnect silently no-ops. This needs coordination with how the backend formats the first SSE event.

---

## Decision Review

No `Plan/DECISION_LOG.md` exists (deleted per git status). No architectural decisions to review for QC6 — all changes are straightforward fixes with no competing design options.

The choice to use a class component for ErrorBoundary (rather than a functional component with a library like `react-error-boundary`) is correct — React class components are still required for error boundary lifecycle methods as of React 19. No concern here.

The choice to export `PROVIDER_MODELS` from `Settings.tsx` rather than a shared constants file is acceptable for now, but if other pages need to display model names, this will need to be moved to a shared location.
