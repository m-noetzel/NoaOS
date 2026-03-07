# QA Test-Plan Review: Phase QC7 — Frontend Polish & UX

**Date:** 2026-03-07
**Phase:** QC7
**Reviewer:** qa-review agent
**Review type:** Pre-implementation test-plan

---

## Summary

QC7 addresses 10 medium-severity frontend findings (UI-M1 through UI-M10) covering dead code
removal, pagination, SSE event validation, streaming UX, thread naming, a new Tools page, cost
chart empty states, settings cache invalidation, sidebar badges, and code-splitting. This test plan
defines what the `/write-tests` agent must produce before implementation begins, and identifies
structural gaps that will allow fixes to pass tests while remaining functionally broken.

**Overall assessment:** QC7 is the most complex frontend phase to date. Findings span 5 different
concerns: pure code deletion (UI-M1), data layer (UI-M2, UI-M8), SSE/streaming behavior (UI-M3,
UI-M4), new feature surface (UI-M5, UI-M6, UI-M9), visual/UX states (UI-M7), and a build concern
(UI-M10). Most findings require component rendering tests with `@testing-library/react` — not pure
utility tests.

**Minimum credible test count: 28 tests** — see per-finding breakdown below.

---

## Current Code State (Pre-Implementation)

Before writing tests, the write-tests agent must understand what currently exists:

- `web/src/pages/Index.tsx` — exists as dead placeholder ("Welcome to Your Blank App"), never routed to
- `web/src/pages/Runs.tsx` — fetches all runs with no `limit`/`offset` params; `queryKey: ["runs"]`
- `web/src/pages/Artifacts.tsx` — fetches all artifacts with no pagination; `queryKey: ["artifacts"]`
- `web/src/pages/Cost.tsx` — no loading skeleton, no empty state for empty `summaries` or `records`
- `web/src/api/sse.ts:116` — `eventName as SSEEventType` is an unsafe cast with no runtime validation
- `web/src/pages/Chat.tsx:147-150` — `result_ready` clears `streamingContent` and calls
  `queryClient.invalidateQueries` but does NOT append the assistant message to local state first
- `web/src/pages/Chat.tsx:90` — thread title hardcoded to `"New Thread"` in `createThreadMutation`
- `web/src/App.tsx` — no `/tools` route; no `React.lazy()` wrapping on any page
- `web/src/components/layout/AppSidebar.tsx` — no Tools link; no approval/queue badge counts
- `web/src/pages/Chat.tsx:77-84` — settings loaded into local state once on mount via `useEffect`;
  stale settings persist for up to 30s after changing in the Settings page

---

## Finding-by-Finding Test Coverage Requirements

### UI-M1: Delete `web/src/pages/Index.tsx`

**The fix:** Delete the file entirely. Remove any import in `App.tsx` (there is none — `App.tsx`
already routes `"/"` to `<Chat />`).

**What must be tested:**
1. `web/src/pages/Index.tsx` must NOT exist after the fix (file deleted, not just unused).
2. The `"/"` route in `App.tsx` still renders `<Chat />` (regression guard — not Index).
3. No import of `Index` or `Index.tsx` exists anywhere in `src/`.

**Approach:** Pure file-system assertion tests — these are the only sensible tests here. Use
`fs.existsSync` or import resolution to verify the file is gone.

**Gap to flag:** The write-tests agent should NOT write a test that imports `Index` and checks
it renders a certain way — that would test the dead code, not its removal. The test must verify
the file no longer exists. In vitest this can be done with:

```typescript
import { existsSync } from "fs";
import { resolve } from "path";
it("Index.tsx does not exist", () => {
  expect(existsSync(resolve(__dirname, "../../pages/Index.tsx"))).toBe(false);
});
```

**Required tests: 2** (file deleted, "/" route still renders Chat)

---

### UI-M2: Pagination on Runs, Artifacts, and Cost pages

**The fix:** Add `limit`/`offset` state, pass them as query params to API calls, render
previous/next pagination controls.

**What must be tested:**
1. Runs page: Initial fetch uses `limit` query param (e.g., `?limit=20&offset=0`).
2. Runs page: Clicking "Next" increments offset and refetches with updated params.
3. Runs page: "Previous" is disabled at offset=0.
4. Runs page: "Previous" is enabled after navigating to next page.
5. Artifacts page: Initial fetch uses `limit`/`offset` params.
6. Artifacts page: Pagination controls work (next/previous).
7. Cost page: Records list uses `limit`/`offset` params.
8. **Negative:** When backend returns fewer items than `limit`, the "Next" button is disabled
   (or hidden) — no infinite empty pages.

**Approach:** Mock `apiRequest` to spy on the URL called. Assert the query string includes
`limit` and `offset`. Simulate clicking "Next" and verify the refetch URL changes.

**Critical gap — queryKey invalidation:** If the fix uses `queryKey: ["runs", { limit, offset }]`
(correct), changing the offset triggers a new fetch. If it uses `queryKey: ["runs"]` (wrong), all
pages share cache. Tests must assert that the `queryKey` changes when pagination state changes,
otherwise the data layer is broken.

**Critical gap — "Next" disabled logic:** With no page-count information from the backend
(backend returns a plain array, not `{ items: [...], total: N }`), the only way to detect the
last page is "returned items < limit". If the fix disables "Next" only when the array is empty,
the user sees one extra empty page. Tests must verify this boundary: if `limit=20` and 20 items
are returned, "Next" is enabled; if 19 items are returned, "Next" is disabled.

**Required tests: 6** (covering Runs, Artifacts, Cost pagination basics + last-page disabling)

---

### UI-M3: Runtime SSE event type validation

**The fix:** In `sse.ts`, validate `eventName` against the `SSEEventType` union before calling
`onEvent`. Log unknown types instead of passing them through via `as SSEEventType` cast.

**What must be tested:**
1. A known event type (e.g., `"token_stream"`) passes through and calls `onEvent`.
2. An unknown event type (e.g., `"malicious_event"`) is NOT passed to `onEvent` — or is logged
   as unknown but does not crash.
3. An event with no `event:` line and no `event_type` field defaults to `"unknown"` and is
   handled gracefully (not crashing).
4. The set of valid event types matches the `SSEEventType` union from `types.ts` — no drift
   between the validation whitelist and the type definition.

**Approach:** Direct unit tests on `SSEClient` by injecting a mock stream reader. The test
controls the raw bytes fed into the stream parser and verifies which events reach `onEvent`.

**Critical gap — the validation approach matters:** There are two valid implementations:

Option A: Filter unknown events entirely (onEvent never called for unknown types).
Option B: Pass them through with `event: "unknown"` as a sentinel value, so the Chat
component can log them.

The test plan must specify which behavior is required. We recommend Option A (filter) because
Option B still passes unvalidated strings to the component switch statement. Tests must specify
the expected behavior for unknown events before implementation begins.

**Required tests: 4**

---

### UI-M4: Streaming content not added to message history on `result_ready`

**The fix:** On `result_ready`, either (a) immediately invalidate the messages query so it
refetches, or (b) optimistically append the assistant message to local state before the
refetch completes.

**Current behavior:** `result_ready` clears `streamingContent` and calls
`queryClient.invalidateQueries` — the text disappears while the query refetches.

**What must be tested:**
1. When `result_ready` fires, the streaming content does NOT disappear before the refetched
   messages arrive (the flash is eliminated).
2. After `result_ready`, the assistant message appears in the message list within one render
   cycle (without waiting for a full refetch round-trip).
3. **Negative:** Duplicate messages must not appear — if the optimistic append AND the refetch
   both add the assistant message, there should still be only one copy.
4. **Regression:** `isStreaming` becomes `false` after `result_ready` (existing behavior).
5. **Regression:** `streamingContent` is cleared after `result_ready` (existing behavior).

**Approach:** Render `Chat` with a mocked `SSEClient`. Simulate a sequence of events:
`meta` → `token_stream` (multiple) → `result_ready`. Assert that after `result_ready`, the
accumulated streaming content appears in the message list and is not blank.

**Critical gap — "optimistic vs. invalidate" is an implementation choice that tests must
specify upfront:** If the fix uses optimistic append (option b), the message must have the
correct structure (`role: "assistant"`, `content: streamingContent`). If it only relies on
`invalidateQueries`, the test must wait for the mocked refetch to resolve and verify the
message appears. The test should assert the outcome (no flash) not the mechanism.

**Required tests: 3** (no-flash, no-duplicate, streaming regression)

---

### UI-M5: Auto-generate thread title from first message

**The fix:** When creating a new thread, use the first message content (truncated to ~50 chars)
as the thread title instead of the hardcoded `"New Thread"`.

**Current behavior:** `createThreadMutation` sends `{ title: "New Thread" }` for every new
thread (Chat.tsx:90).

**What must be tested:**
1. When a user sends the first message in a new thread, the thread creation request body
   contains a `title` derived from the message content (not `"New Thread"`).
2. The title is truncated to ≤50 characters (or the configured limit).
3. The title has trailing `"..."` appended when truncated.
4. **Negative:** An empty message does not create a thread (existing guard: `!input.trim()`).
5. **Negative:** A message of exactly 50 chars produces a title without `"..."`.
6. A message with only whitespace produces the default title (graceful degradation) rather
   than a whitespace-only title.

**Approach:** Mock `apiRequest` to spy on the POST body sent to `/api/v1/threads`. Assert the
`title` field. No component rendering is strictly required — the mutation function can be
tested by simulating `handleSend` via the component.

**Critical gap — implementation timing:** The thread may be created BEFORE the first message
is sent (user clicks "+" to create a new thread). In that case, the fix must update the title
AFTER the first message. If the implementation only changes what title is used during thread
creation (the "+" click), but the first message is sent without a thread title update, the
finding is not fixed. Tests must cover the flow where a new thread is created inline when the
user sends the first message to an empty state.

**Required tests: 4** (title truncation, no "New Thread", empty message guard, exact-50 edge)

---

### UI-M6: Tools page

**The fix:** Create `web/src/pages/Tools.tsx` that fetches `/api/v1/tools`, shows name,
description, risk tier, and enabled status. Add `/tools` route in `App.tsx`. Add sidebar link.

**Important:** The backend's `GET /api/v1/tools` endpoint **does not exist** in the current
codebase. The tools router (`src/noa/api/v1/tools.py`) only has `POST /{name}/enable` and
`DELETE /{name}`. The frontend test plan must account for this — either the backend adds a
`GET /api/v1/tools` list endpoint as part of QC7, or the frontend must use `TOOL_CAPABILITIES`
keys in a different way.

If the phase plan intends to add a backend `GET /api/v1/tools` endpoint, this is an
undocumented deliverable that needs a test. If the frontend is expected to call a non-existent
endpoint, the tests must mock it and document the assumption.

**What must be tested for the frontend Tools page:**
1. Tools page renders with data from `/api/v1/tools` when data is available.
2. Each tool row shows: name, description/capability string, risk tier (if present), enabled status.
3. **Empty state:** "No tools configured" when the API returns an empty array.
4. **Loading state:** Skeleton or spinner shown while fetching.
5. **Error state:** Error message shown when the API call fails.
6. The `/tools` route exists in `App.tsx` — navigating to `/tools` renders the Tools page.
7. The sidebar has a "Tools" link that navigates to `/tools`.
8. **Negative:** The sidebar link is NOT shown when not authenticated (regression guard).

**Approach:** Mock `apiRequest` to return a tool list. Render `<Tools />` wrapped in
`QueryClientProvider` + `MemoryRouter`. Assert tool names and capabilities appear.

**Critical gap — backend GET endpoint:** The test must document clearly whether:
(a) It calls `GET /api/v1/tools` (needs backend change), or
(b) It calls `GET /api/v1/tools` and the backend is expected to add this endpoint as part of QC7.

The write-code agent cannot implement a frontend page that calls an endpoint that doesn't exist
without also implementing the backend endpoint. This is a scope creep risk that tests should
make explicit.

**Required tests: 5** (renders with data, empty state, loading state, route registered, sidebar link)

---

### UI-M7: Loading skeletons and empty states for Cost charts

**The fix:** Add `isLoading` skeleton placeholders in Cost page; add "No cost data yet" text
when `summaries.length === 0` or `records.length === 0`.

**Current behavior:** Loading shows blank space; empty data shows charts with empty axes.

**What must be tested:**
1. When `isLoading` is true for either query, a skeleton or spinner is visible.
2. When `summaries` is empty (`[]`), "No cost data yet" (or similar) text is visible.
3. When `records` is empty (`[]`), the chart area shows an empty state, not an empty axis.
4. **Regression:** When data is present, charts render (not blocked by empty-state logic).
5. **Negative:** The empty state message does not appear when data is loading (conflated states).

**Approach:** Render `<Cost />` with React Query mocks:
- Mock `isLoading: true` to test skeleton state.
- Mock `data: { data: [] }` to test empty state.
- Mock `data: { data: [{...}] }` to test normal render.

**Critical gap — recharts in jsdom:** Recharts renders SVG elements in jsdom without errors, but
`ResponsiveContainer` may not render correctly because jsdom has no layout engine. Tests that
check "chart renders" may need to use a `ResizeObserver` mock. The existing `setup.ts` already
mocks `matchMedia` but not `ResizeObserver`. If `ResponsiveContainer` requires real dimensions,
the test will fail with an unhelpful error.

Recommendation: Mock `recharts` in these tests to avoid jsdom layout issues, and test the
conditional rendering logic (empty state vs chart container) rather than the chart itself.

**Required tests: 3** (skeleton shown loading, empty state shown, regression with data)

---

### UI-M8: Settings changes affect Chat without stale state

**The fix:** Either (a) use settings query data directly in Chat (no local state copy), or
(b) invalidate the settings cache on navigation to Chat.

**Current behavior:** `Chat.tsx:77-84` — `useEffect` copies settings into local state once on
mount. If settings change in the Settings page and the user navigates back to Chat, the old
values persist until the next `staleTime` expiry (30s).

**What must be tested:**
1. If settings are updated and the user navigates back to Chat, the updated `provider`/`model`
   are reflected in the next chat request (not the stale pre-update values).
2. **Regression:** The Chat page still reads the correct initial defaults from settings on first
   load (does not reset to hardcoded values).
3. If `settingsRes.data` changes (query refetch), Chat uses the new values immediately.

**Approach:** The test depends on which implementation is chosen:

Option A (use query data directly): Assert that Chat's effective `provider`/`model` values
always equal `settingsRes.data.default_provider`/`.default_model`, even after settings change.

Option B (cache invalidation on navigation): Assert that navigating to `/` triggers an
`invalidateQueries({ queryKey: ["settings"] })` call.

The test plan must specify the expected implementation so the write-code agent doesn't choose
the harder-to-test option.

**Recommendation:** Option A is safer and more testable. The test should: render Chat with
initial settings, update the mocked query data (simulating a settings change), and verify Chat
uses the updated values for the next send.

**Required tests: 3** (fresh values after settings change, initial load still works, next
message uses updated provider)

---

### UI-M9: Approval and queue count badges on sidebar

**The fix:** Fetch `/api/v1/approvals/pending` and `/api/v1/queue` counts and display badges
on the Approvals and Queue sidebar items.

**Current behavior:** `AppSidebar.tsx` has no API calls — it's a pure navigation component.

**What must be tested:**
1. When `GET /api/v1/approvals/pending` returns 3 approvals, the "Approvals" sidebar item
   shows a badge with "3".
2. When `GET /api/v1/queue` returns 2 queued items, the "Queue" sidebar item shows a badge
   with "2".
3. **Empty/zero state:** When approval count is 0, no badge is rendered (or badge is hidden).
4. **Negative:** Badge shows a maximum cap (e.g., "99+") for very large counts — or at minimum
   the badge does not overflow its container.
5. **Error resilience:** If the approvals or queue fetch fails, the sidebar still renders
   normally (no crash, badge just absent).

**Approach:** Render `<AppSidebar />` wrapped in required providers
(`MemoryRouter` + `QueryClientProvider` + `SidebarProvider`). Mock `apiRequest`. Assert badge
text is visible.

**Critical gap — Sidebar component context requirement:** `AppSidebar` uses `useSidebar()` which
requires a `SidebarProvider` context. Tests that render `AppSidebar` without `SidebarProvider`
will crash with a context missing error. The test infrastructure must wrap with `SidebarProvider`.

**Required tests: 4** (approval badge, queue badge, zero badge hidden, fetch error graceful)

---

### UI-M10: React.lazy() + Suspense for route-level code splitting

**The fix:** Wrap heavy pages (Cost, RunDetail, possibly others) with `React.lazy()` in App.tsx.
Add `<Suspense fallback={<LoadingSpinner />}>` wrappers.

**What must be tested:**
1. `App.tsx` uses `React.lazy()` for at least Cost (recharts dependency) — verifiable by
   checking that `import Cost from "@/pages/Cost"` is NOT a static top-level import.
2. Each lazy-loaded route has a `<Suspense>` wrapper with a non-null fallback.
3. **Regression:** The lazy-loaded pages still render their content when the dynamic import
   resolves.
4. **Negative:** Without Suspense, a lazy component throws a Promise during render. The
   `<Suspense>` must be present or the ErrorBoundary catches it (which would be wrong).

**Approach:** This is the hardest finding to test in vitest because:
- `React.lazy()` returns a component that suspends during the dynamic import.
- In vitest/jsdom, `import()` resolves synchronously (no network delay).
- The practical test is a code inspection test: assert `lazy(` appears in `App.tsx` and
  `React.lazy` is not statically assigned to the same variable names as before.

**Recommended test approach:** Source-level assertion test that reads `App.tsx` and verifies
it contains `lazy(` and `<Suspense`. This is a structural test, not a behavioral test. Behavioral
tests (does the page actually render) should reuse the existing smoke tests in other test files.

**Alternative:** Use vitest's module mock to make a dynamic import never resolve, assert the
Suspense fallback appears, then resolve it and assert the page appears.

**Required tests: 2** (lazy loading in App.tsx verified, Suspense fallback shown during load)

---

## Structural Requirements for the Write-Tests Agent

### Requirement 1: Test file location and naming

All QC7 tests must go in `web/src/test/qc7-fixes.test.tsx`. The QC6 pattern
(`qc6-fixes.test.tsx`) establishes the naming convention. The file extension MUST be `.tsx`
(not `.ts`) because JSX is used in component rendering tests.

### Requirement 2: Required test infrastructure

Every component test must use:
```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
```

Tests that render `AppSidebar` additionally require `SidebarProvider`.

The standard wrapper pattern from QC6 must be followed:
```typescript
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

render(
  <QueryClientProvider client={queryClient}>
    <MemoryRouter>
      <ComponentUnderTest />
    </MemoryRouter>
  </QueryClientProvider>
);
```

### Requirement 3: API mocking via vi.doMock + vi.resetModules

The QC6 pattern of `vi.doMock("@/api/client", ...)` + `vi.resetModules()` before dynamic
import is the established pattern for component tests that need to control API responses. All
component tests must follow this pattern to prevent mock bleed-through between test suites.

### Requirement 4: Spec traceability

Every `describe` block must include a comment citing the finding ID and the PHASE_DETAILS.md
entry, matching the M1 (Spec Traceability) checklist criterion. Example:
```typescript
/**
 * UI-M2: No Pagination on Runs, Artifacts, Cost Records
 * Spec ref: PHASE_DETAILS.md Phase QC7 / UI-M2
 * Finding: Runs/Artifacts/Cost pages fetch all data without limit/offset
 */
```

### Requirement 5: Each describe block needs at least one negative test

Per M2 (Negative Tests), every critical behavior needs at least one negative test. See the
per-finding breakdown above for specific negative tests required.

---

## Test Count Summary

| Finding | Min Tests | Notes |
|---------|-----------|-------|
| UI-M1 | 2 | file-deletion assertion + "/" route regression |
| UI-M2 | 6 | Runs pagination, Artifacts pagination, Cost pagination, last-page disable |
| UI-M3 | 4 | known event passes, unknown filtered/logged, no-event defaults, type consistency |
| UI-M4 | 3 | no flash, no duplicate, streaming regression |
| UI-M5 | 4 | title from message, truncation, no "New Thread", empty edge case |
| UI-M6 | 5 | Tools page renders, empty state, loading state, route, sidebar link |
| UI-M7 | 3 | skeleton on loading, empty state, regression with data |
| UI-M8 | 3 | fresh settings used, initial load works, next message uses updated values |
| UI-M9 | 4 | approval badge, queue badge, zero hidden, error graceful |
| UI-M10 | 2 | lazy import in App.tsx, Suspense fallback |
| **Total** | **36** | |

Minimum acceptable count is **28** (the lower bound for ~1 positive + 1 negative per finding
with some consolidation). Going below 20 means critical behaviors are untested.

---

## Pre-Implementation Blockers

The following must be resolved before the write-tests agent begins:

### Blocker 1: Backend GET /api/v1/tools endpoint does not exist

UI-M6 requires a frontend Tools page that fetches tool data from `/api/v1/tools`. The current
backend tools router (`src/noa/api/v1/tools.py`) has only `POST /{name}/enable` and
`DELETE /{name}`. There is no `GET /api/v1/tools` list endpoint.

**Decision needed before tests are written:**
- (a) Does QC7 add a backend `GET /api/v1/tools` list endpoint? If yes, what is the response schema?
- (b) Does the frontend derive tool data from another source (e.g., static config)?

If (a): the backend endpoint must be defined first, and a mock matching its response schema must
be used in tests.

If (b): the source must be specified (which component/file, what data structure).

Without resolution, the write-tests agent will invent a schema that the write-code agent may not
match.

**Recommended resolution:** Add `GET /api/v1/tools` returning:
```json
[{ "name": "web_search", "capability": "search.read", "risk_tier": "low", "description": "..." }]
```
derived from `TOOL_CAPABILITIES`. This requires one minor backend change that should be
documented in the phase plan as an implicit deliverable.

### Blocker 2: UI-M4 implementation strategy must be specified before tests

There are two valid fixes for the streaming content disappearing flash:

- Option A: On `result_ready`, append the streamed content as an optimistic message to local
  state before calling `invalidateQueries`.
- Option B: Do not clear `streamingContent` until the `queryClient.invalidateQueries` resolves
  and the new data is in cache.

The tests for these two options are different. Option A tests for an optimistic message with
`role: "assistant"` appearing. Option B tests that `streamingContent` remains visible during
the refetch. The write-tests agent must choose one to test.

**Recommendation:** Option A (optimistic append) is more robust and tests more behavior.
Specify this explicitly so both write-tests and write-code agents align.

### Blocker 3: UI-M10 is not independently testable at unit level

Code splitting is a build-time concern. Vitest/jsdom cannot measure bundle sizes or verify that
dynamic imports produce separate chunks in the Vite build. The only testable aspects are:
(a) the presence of `lazy(` in `App.tsx`, and (b) the presence of `<Suspense>` wrappers.

The only definitive test for code splitting is `vite build` followed by checking output chunk
sizes. The write-tests agent should write a source-inspection test as a best-effort check, and
document that a true verification requires the build pipeline.

---

## Approach Risks by Finding

| Finding | Primary Risk | Mitigation |
|---------|-------------|------------|
| UI-M1 | Testing file existence via `fs` in vitest — path resolution depends on `__dirname` in ESM context | Use `import.meta.url` + `fileURLToPath` for path resolution in ESM tests |
| UI-M2 | `queryKey` with pagination params may not match how RQ deduplicates — test must call the refetch and check the URL, not just the queryKey | Spy on `apiRequest` mock and check the `path` argument includes `?limit=...` |
| UI-M3 | The validation set must match `SSEEventType` exactly — if a new event type is added to the type but not to the validator, events are silently dropped | Assert the validator set and `SSEEventType` union have the same members |
| UI-M5 | Thread creation may happen before or after first message — if the fix only sets title during creation (not after first send), the test must verify the correct timing | Mock `createThreadMutation` and check the `title` field in the POST body sent during `handleSend` |
| UI-M6 | Backend endpoint missing — all Tests will mock it, giving false confidence | Document the mock assumption; add a TODO for integration test once backend endpoint exists |
| UI-M7 | `recharts` + `ResponsiveContainer` may error in jsdom without `ResizeObserver` mock | Add `vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} })` to setup.ts or test body |
| UI-M9 | `AppSidebar` uses `useSidebar()` which requires `SidebarProvider` context | Wrap render in `SidebarProvider` |
| UI-M10 | `React.lazy()` in jsdom resolves the dynamic import synchronously — the Suspense fallback may never be visible | Use `vi.mock` to return a never-resolving promise for the lazy import to force Suspense to show |

---

## Missing Negative Tests Summary

The following negative tests are explicitly required (not optional):

| Finding | Required Negative Test |
|---------|----------------------|
| UI-M2 | When API returns fewer items than `limit`, "Next" button is disabled |
| UI-M3 | Unknown event type `"hacked_event"` is NOT passed to `onEvent` callback |
| UI-M5 | Message with only whitespace does not produce a whitespace-only thread title |
| UI-M6 | Tools page shows error state when API returns 500 |
| UI-M7 | Empty state message is NOT shown when data is loading (not a false empty state) |
| UI-M8 | After settings change, old stale provider/model is NOT used in the next chat request |
| UI-M9 | When approval/queue fetch fails with network error, sidebar does not crash |
| UI-M10 | Without Suspense wrapper, the lazy component would throw a Promise (verified by asserting Suspense IS present) |

---

## Regression Guards Required

The following behaviors must NOT regress after QC7 changes:

| Component | Regression | Test Method |
|-----------|----------|------------|
| `Chat.tsx` | Settings are still loaded on initial mount | Mock API returning settings; render Chat; assert `provider` state has the mocked value |
| `Chat.tsx` | SSE `token_stream` still appends to `streamingContent` | After UI-M4 fix, `result_ready` should not break token streaming |
| `Chat.tsx` | `result_ready` still sets `isStreaming = false` | After UI-M4 fix, streaming state is cleared |
| `sse.ts` | Valid known event types still call `onEvent` | After UI-M3 validation added, known events are not accidentally filtered |
| `App.tsx` | All existing routes still render | After adding `/tools` and `React.lazy()`, existing routes must not break |
| `AppSidebar.tsx` | Existing nav links still work | After adding Tools link and badges, existing links are not broken |
| `Runs.tsx` | "No runs found" empty state still works | After pagination added, zero-item empty state still renders correctly |

---

## Verdict on Test Plan Readiness

**Status: REQUIRES BLOCKER RESOLUTION before write-tests begins.**

The three blockers above (missing backend endpoint for UI-M6, UI-M4 implementation strategy
choice, UI-M10 unit-testability limitation) must be explicitly decided. The write-tests agent
should document which implementation strategy it assumes for UI-M4 and UI-M6 schema, and note
the UI-M10 limitation in the test file header comment.

With these decisions made, a 28–36 test suite covering all 10 findings is achievable using the
QC6-established infrastructure (`vi.doMock`, `@testing-library/react`, `MemoryRouter`,
`QueryClientProvider`).
