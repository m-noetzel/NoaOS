# QA Test-Plan Review: Phase QC6 — Frontend Critical & High Fixes

**Date:** 2026-03-07
**Phase:** QC6
**Reviewer:** qa-review agent
**Review type:** Pre-implementation test-plan

---

## Summary

The phase plan specifies "~10 tests in `web/src/test/qc6-fixes.test.tsx`". This review evaluates whether 10 tests
are sufficient to verify all 8 findings (UI-C1 through UI-H5) and identifies gaps, edge cases,
and approach concerns before implementation begins.

**Overall verdict on the test plan: INSUFFICIENT — 4 findings are severely under-tested and 3 structural gaps
will allow the fixes to pass tests while still being functionally broken.**

---

## Finding-by-Finding Test Coverage Assessment

### UI-C1: SSE BASE_URL Default (`sse.ts` line 4)

**The fix:** Change `|| "http://localhost:8000"` to `|| ""`.

**What tests are needed:**
1. Verify `SSEClient` constructs fetch URLs as relative paths (e.g. `/api/v1/chat`) when `VITE_API_BASE_URL` is unset.
2. Verify `SSEClient` uses the env var when `VITE_API_BASE_URL` is set.
3. Negative: Verify old absolute URL (`http://localhost:8000/api/v1/chat`) is NOT used as the default.

**What the plan likely delivers:** A single import smoke test or a string constant assertion. The plan says
"~10 tests" for all 8 findings combined — this finding almost certainly gets 1 test.

**Gap:** The real bug is a CORS failure at runtime. A unit test that checks the constant value passes even if
the constant is correct. What is NOT tested:
- Whether `VITE_API_BASE_URL` is picked up correctly in the test environment (jsdom, not a real Vite build).
- Whether the SSEClient actually concatenates `BASE_URL + path` correctly for both cases.

**Risk:** `import.meta.env.VITE_API_BASE_URL` evaluates to `undefined` in vitest unless explicitly set with
`vi.stubGlobal("import.meta", ...)` or `vi.stubEnv(...)`. If the test author forgets this, the test will pass
because `undefined || ""` is `""` regardless — it tests nothing about the env var path.

**Required test:** A unit test that stubs `import.meta.env.VITE_API_BASE_URL = "https://prod.example.com"` and
verifies the fetch URL uses that value. Without this, the env var code path is never exercised.

---

### UI-C2: Chat `currentRunId` Not Set From SSE Meta Event

**The fix:** Add `"meta"` to `SSEEventType`, handle it in `handleSSEEvent` to call `setCurrentRunId`.

**What tests are needed:**
1. When `handleSSEEvent` receives `{ event: "meta", data: { run_id: "run-abc" } }`, `currentRunId` is updated.
2. Verify `ActivityStream` receives the non-null `runId` after the meta event.
3. Negative: When `event` is anything other than `"meta"`, `setCurrentRunId` is NOT called.
4. Regression: `result_ready` still clears `streamingContent` and sets `isStreaming = false`.

**Gap:** This requires testing a React component's internal state after simulating an SSE event. Testing
`handleSSEEvent` in isolation (as a plain function) is not possible because it's defined inside the component
with `useCallback`. Testing requires `@testing-library/react` with `renderHook` or full component rendering.

The plan uses jsdom + vitest but the existing test suite (`wm-tests.test.tsx`) avoids full component rendering
entirely — it only tests utility functions and mock handlers. If QC6 follows the same pattern, `UI-C2` will
only be tested by calling `handleSSEEvent` extracted as a utility, not as part of the rendered component.

**Risk:** The fix could be implemented as `case "meta": setCurrentRunId(event.data.run_id as string); break;`
but if `event.data.run_id` is typed as `unknown` and the cast fails silently in TypeScript's structural
typing, the bug persists. A test needs to assert the string value was actually set.

**Missing edge case:** What if the meta event arrives after `result_ready`? The `currentRunId` is set but
the streaming session is over — `ActivityStream` already closed. No test for this race.

**Missing edge case:** What if `event.data.run_id` is absent or null? No test for graceful degradation.

---

### UI-C3: Logout Does Not Clear React Query Cache

**The fix:** Import `useQueryClient` in `AuthContext.tsx`, call `queryClient.clear()` on logout.

**What tests are needed:**
1. After `logout()` is called, `queryClient.getQueryCache().getAll()` returns an empty array.
2. Regression: `clearTokens()` is still called (auth flag is removed from localStorage).
3. Regression: `setIsAuthenticated(false)` is still called.
4. Negative: Another user's data cannot be read after logout (cross-user data isolation).

**Gap:** `useQueryClient` is a React hook. Testing `logout()` in isolation requires either:
(a) A full component render with `QueryClientProvider` wrapper, or
(b) Extracting `queryClient.clear()` to a testable unit.

The existing tests in `wm-tests.test.tsx` do NOT wrap anything in `QueryClientProvider` — they test
pure functions only. If QC6 tests follow the same pattern, testing `AuthContext.logout` is impossible
without rendering the component tree.

**Risk:** The developer might add a `queryClient.clear()` call but instantiate a different `QueryClient`
instance than the one passed to `QueryClientProvider`. The existing `App.tsx` creates a module-level
`queryClient = new QueryClient(...)`. `AuthContext` must use the SAME instance via `useQueryClient()`.
A test that just checks "logout function calls queryClient.clear()" with a fresh mock client does not
catch this wiring error.

**Required approach:** The test MUST render `<QueryClientProvider client={queryClient}><AuthProvider><TestComponent /></AuthProvider></QueryClientProvider>` and verify the actual cache is cleared. Any mock-based approach is insufficient.

---

### UI-H1: Provider Dropdown Contains Invalid "google"

**The fix:** Add `"google_ai"` to `Provider` type in `types.ts`, change dropdown value from `"google"` to `"google_ai"`.

**What tests are needed:**
1. TypeScript compile check: `"google"` is not assignable to `Provider`.
2. TypeScript compile check: `"google_ai"` is assignable to `Provider`.
3. That the settings save mutation sends `"google_ai"` (not `"google"`) when Google AI is selected.
4. Regression: Backend expects `"google_ai"` — mock handler should accept it.

**Gap:** TypeScript type checks are compile-time only. A vitest unit test cannot verify that the `Provider`
type was updated — it verifies runtime behavior. However, the real risk here is that `types.ts` is updated
but `Settings.tsx` still sends `"google"` to the backend, or vice versa.

**The useful test:** A test that simulates selecting `"google_ai"` in the provider dropdown (using
`@testing-library/react`) and then clicking Save, verifying the request body contains
`default_provider: "google_ai"`. This requires component rendering.

**Risk:** If only a type-check test is added (e.g., asserting that `"google_ai" satisfies Provider`),
the actual dropdown value remains untested at runtime.

---

### UI-H2: Model Dropdown Is Hardcoded

**The fix:** Add a `PROVIDER_MODELS` map, filter model dropdown by selected provider.

**What tests are needed:**
1. When provider is `"anthropic"`, only Claude models appear in the model list.
2. When provider is `"openai"`, only GPT models appear.
3. When provider is `"google_ai"`, only Gemini models appear.
4. When provider is `"ollama"`, only Llama/local models appear.
5. When provider changes, the selected model resets to a valid value for the new provider.
6. Negative: After switching from `"openai"` to `"anthropic"`, `"gpt-4o"` is NOT in the dropdown.

**Gap:** This is the most complex UI fix. Filtering behavior requires either:
(a) Testing the `PROVIDER_MODELS` map data structure directly (is this a unit test or a data validation test?), or
(b) Rendering the Settings component and interacting with the Select elements.

Option (a) is trivial and catches nothing about the render logic.
Option (b) requires `@testing-library/react` with full Select interaction, which is complex with Radix UI.

**Risk:** Radix UI `Select` components do not render their options to the DOM in jsdom without user
interaction simulation. Testing that "only Claude models appear" requires a `userEvent.click()` on the
trigger, then checking the rendered options. This is non-trivial. If the test author skips rendering and
just tests the `PROVIDER_MODELS` data object, the filtering logic in the component is never exercised.

**Missing edge case:** What model is pre-selected when the user switches providers? If the current model
is invalid for the new provider, the Select should either reset to the first valid model or show a
validation error. No test for this.

**Missing edge case:** What if `PROVIDER_MODELS["anthropic"]` returns an empty array? The model dropdown
would render empty. No boundary test.

---

### UI-H3: Budget Inputs Accept Negative Numbers

**The fix:** Add `min="0"` and `step="0.01"` to inputs. Validate `daily <= monthly` before save.

**What tests are needed:**
1. Save is blocked when `dailyBudget < 0`.
2. Save is blocked when `monthlyBudget < 0`.
3. Save is blocked when `dailyBudget > monthlyBudget`.
4. Save succeeds with valid values (e.g., daily=10, monthly=200).
5. Error message is shown (not silently swallowed) when validation fails.
6. Edge case: `dailyBudget === monthlyBudget` should be allowed.
7. Edge case: Empty string input — `parseFloat("") === NaN` — what happens?
8. Edge case: `"abc"` as input — `parseFloat("abc") === NaN` — should be rejected.

**Gap:** The plan mentions `min="0"` and `step="0.01"` as HTML attributes. These are browser-enforced,
not JavaScript-enforced. In jsdom, HTML input validation (`min`/`max`) is NOT enforced — `element.value = "-5"` works fine regardless of `min="0"`. Tests in jsdom will NOT catch missing HTML validation.

**The real protection is the JavaScript validation** (`daily <= monthly` check before save). This IS
testable in vitest.

**Risk:** If the test only checks that the `min` attribute is present on the DOM element (e.g.,
`expect(input).toHaveAttribute("min", "0")`), it does NOT verify that the save is actually blocked.
The attribute check is worthless if the `saveMutation` is called before validation.

**Required test:** Simulate clicking Save with `dailyBudget = -5` and verify `saveMutation.mutationFn`
is NOT called (or verify the error toast appears).

---

### UI-H4: No Error Boundaries

**The fix:** Create `web/src/components/ErrorBoundary.tsx` (class component), wrap `ProtectedRoute` in `App.tsx`.

**What tests are needed:**
1. When a child component throws during render, `ErrorBoundary` renders the fallback UI (not a blank page).
2. The fallback shows a "Something went wrong" message.
3. A retry/reload button is present and functional.
4. Regression: Normal (non-throwing) children render correctly through the boundary.
5. `ErrorBoundary` catches errors in lifecycle methods (not just render).

**Gap:** Error boundaries are React class components that implement `componentDidCatch`. Testing them
in vitest with `@testing-library/react` requires:
```tsx
function ThrowingComponent() { throw new Error("test error"); }
render(<ErrorBoundary><ThrowingComponent /></ErrorBoundary>);
expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
```

This IS testable and straightforward. However, `@testing-library/react` requires suppressing the
console.error output that React emits for uncaught errors in tests, or the test output will be noisy.

**Missing from plan:** The `ErrorBoundary` must be wired at the `ProtectedRoute` level in `App.tsx`.
A test for the `ErrorBoundary` component itself does NOT verify the wiring. A separate wiring test
or smoke test is needed for `App.tsx`.

**Wiring risk:** The plan says "wrap ProtectedRoute children" but there are two interpretations:
(a) Wrap the `{children}` inside `ProtectedRoute`, or
(b) Wrap `<ProtectedRoute>` itself in `App.tsx`.

If implemented as (b), the error boundary does NOT catch errors inside `<AuthGuard>` or `<AppLayout>`.
No test distinguishes between these two wiring positions.

---

### UI-H5: Memory Delete Has No Confirmation Dialog

**The fix:** Add `AlertDialog` confirmation before `deleteMutation.mutate(fact.id)`.

**What tests are needed:**
1. Clicking the delete button does NOT immediately call `deleteMutation.mutate()` — the dialog appears first.
2. Clicking "Cancel" in the dialog does NOT call `deleteMutation.mutate()`.
3. Clicking "Confirm"/"Delete" in the dialog DOES call `deleteMutation.mutate()` with the correct `fact.id`.
4. The dialog is dismissible (Escape key / overlay click cancels).
5. Regression: Delete in the "approved" tab (line 192) also has confirmation (there are TWO delete buttons).

**Gap:** Both the Pending tab (line 140: `<X>` button) and the Approved tab (line 192: `<Trash2>` button)
call `deleteMutation.mutate()` directly. The plan says to add `AlertDialog` — but does it cover BOTH
delete buttons, or only one?

**Critical regression risk:** The FINDINGS description (UI-H5) references lines 140 and 192. Both must
be fixed. If only one is fixed, the finding is half-resolved. Tests must cover BOTH.

**Risk with Radix AlertDialog in jsdom:** The `AlertDialog` component from Radix renders a portal.
`@testing-library/react` handles portals, but the developer must use `screen.getByRole("alertdialog")`
correctly. If the test queries by wrong roles, it will miss the dialog.

---

## Structural Gaps in the Test Plan

### Gap 1: No Component Rendering Tests

The existing test suite (`wm-tests.test.tsx`) tests only pure utility functions and mock handlers —
no component is rendered. The QC6 fixes are ALL in React components (Chat, Settings, Memory, App, AuthContext).
Without `@testing-library/react` component tests, none of the fixes to reactive behavior can be verified.

The plan says "~10 tests" but does not specify whether they use component rendering or pure logic tests.
If the `/write-tests` agent follows the existing test pattern (pure functions only), 7 of the 8 findings
will have unverifiable tests.

**Requirement before implementation:** The test plan MUST specify that `@testing-library/react` is used
for all component-level tests. The `render()`, `screen`, and `userEvent` APIs must be imported.

### Gap 2: `import.meta.env` Not Mockable by Default in Vitest

The UI-C1 fix uses `import.meta.env.VITE_API_BASE_URL`. In vitest, `import.meta.env` can be stubbed
using `vi.stubEnv("VITE_API_BASE_URL", "https://...")` — but this requires vitest 0.34+ and proper
vitest configuration. The current `vitest.config.ts` does not set `define` or `env` for test mode.
Tests that verify the env var path must explicitly stub the env.

### Gap 3: `useQueryClient` Hook Requires Provider Context

Tests for `AuthContext.logout` that call `queryClient.clear()` CANNOT be unit-tested without wrapping in
`<QueryClientProvider>`. The existing test infrastructure does not provide this wrapper. If the test
creates a fresh `QueryClient` for the test and passes it to `AuthProvider` (not using `useQueryClient`
at all in the test), the wiring is untested.

---

## Missing Negative Tests

The following negative/error-path tests are absent from the plan entirely:

| Finding | Missing Negative Test |
|---------|----------------------|
| UI-C2 | Meta event with missing `run_id` field — should not crash |
| UI-H1 | Provider value `"google"` (old/invalid) sent to backend — should be rejected |
| UI-H2 | Provider with empty model list — dropdown renders gracefully |
| UI-H3 | `parseFloat("")` → NaN budget — save blocked, error shown |
| UI-H3 | `parseFloat("abc")` → NaN budget — save blocked |
| UI-H3 | daily > monthly — save blocked with specific message |
| UI-H4 | Error boundary catches errors in child lifecycle methods |
| UI-H5 | Dialog cancel does NOT trigger delete (regression guard) |

---

## Test Approach Assessment

### What should be done

| Finding | Recommended Test Approach |
|---------|--------------------------|
| UI-C1 | Pure unit test with `vi.stubEnv("VITE_API_BASE_URL", ...)`, verify URL construction |
| UI-C2 | Component test with `@testing-library/react`, simulate SSE event, assert `currentRunId` |
| UI-C3 | Component test with `QueryClientProvider`, assert `queryClient.getQueryCache().getAll()` is empty after logout |
| UI-H1 | Pure unit test on `PROVIDER_MODELS` type + component test verifying save payload |
| UI-H2 | Component test: change provider Select, verify only valid models in model Select |
| UI-H3 | Pure unit test on validation logic + component test: Save with invalid values shows error |
| UI-H4 | Component test: `render(<ErrorBoundary><ThrowingChild /></ErrorBoundary>)`, assert fallback rendered |
| UI-H5 | Component test: click delete, assert dialog appears; confirm → assert mutation called; cancel → assert not called |

### What the plan currently implies (and its weaknesses)

- ~10 tests for 8 findings = ~1.25 tests per finding. This is too sparse for findings with multiple
  edge cases (UI-H2, UI-H3, UI-H5).
- No mention of `@testing-library/react` or `userEvent` — suggests pure logic tests, which are
  insufficient for component-level fixes.
- No mention of `vi.stubEnv` for UI-C1 — the env var path will not be tested.
- No mention of `QueryClientProvider` wrapper for UI-C3 — the wiring will not be tested.

---

## Recommended Test Count

The minimum credible test suite for QC6 is **~20 tests**, not ~10:

| Finding | Min Tests |
|---------|-----------|
| UI-C1 | 2 (default empty string, env var override) |
| UI-C2 | 3 (meta event sets runId, missing run_id graceful, result_ready regression) |
| UI-C3 | 3 (cache cleared, clearTokens still called, cross-user isolation) |
| UI-H1 | 2 (type validation, save payload contains "google_ai") |
| UI-H2 | 4 (anthropic models, openai models, google_ai models, provider change resets model) |
| UI-H3 | 4 (negative rejected, daily>monthly blocked, NaN blocked, valid passes) |
| UI-H4 | 2 (throws → fallback shown, non-throwing children work) |
| UI-H5 | 3 (dialog shown on click, cancel → no delete, confirm → delete both buttons) |
| **Total** | **23** |

---

## Blocking Issues for the Write-Tests Agent

Before writing tests, the following must be resolved:

1. **Commit to `@testing-library/react` for component tests.** The existing test pattern (pure functions)
   cannot verify findings UI-C2, UI-C3, UI-H2, UI-H4, UI-H5. If the write-tests agent avoids component
   rendering, the test-plan review will FAIL.

2. **UI-H5: Both delete buttons** (Pending tab line 140 AND Approved tab line 192) must be covered.
   Write a test for each. A fix that only adds confirmation to one tab is a partial fix.

3. **UI-H3: Test the JavaScript validation path**, not just the HTML attribute. Use
   `fireEvent.change` to set negative values and assert the save is blocked.

4. **UI-C3: Use real `QueryClient` wired through `QueryClientProvider`**, not a mock. The test must
   verify the actual cache is empty after logout, not that "clear() was called on some mock."

5. **UI-C1: Use `vi.stubEnv`** to test both the default path and the env var path. A test that only
   imports `SSEClient` and checks that `BASE_URL === ""` is a trivial constant test — not a real
   behavior test.

---

## Risks Not Covered by Any Planned Test

- **Reconnection path still uses absolute URL:** `sse.ts:146` shows `tryReconnect()` hardcodes the path
  `/api/v1/runs/${this.runId}/events`. This is a relative path, which is correct — but if `BASE_URL` was
  previously `"http://localhost:8000"`, old reconnection logic that prepended `BASE_URL` would now break.
  Verify the reconnection URL is still constructed correctly after the UI-C1 fix.

- **`"meta"` event not in `SSEEventType` before fix — TypeScript error risk:** `types.ts` currently lists
  all valid `SSEEventType` values. Adding `"meta"` to this union without understanding whether the backend
  actually sends it as a named SSE event (`event: meta\ndata: ...`) vs. as a JSON field (`event_type: "meta"`)
  matters. The SSE client has two code paths for event name extraction (line 109-111 of `sse.ts`). A test
  should verify the meta event is recognized regardless of which format the backend uses.

- **`queryClient` in `AuthContext` must be the SAME instance as in `App.tsx`:** `App.tsx` creates
  `queryClient` as a module-level singleton. `AuthContext` uses `useQueryClient()` which reads from
  the nearest `QueryClientProvider`. If `AuthProvider` is ever placed outside `QueryClientProvider`
  (a future refactor risk), `useQueryClient()` throws. No test guards this invariant.

---

## Verdict on Test Plan

**Status: INSUFFICIENT — requires revision before implementation begins.**

The plan's ~10 test estimate reflects a pure-function test approach that is structurally unable to verify
component-level fixes. Without `@testing-library/react` component tests, 6 of the 8 findings will have
tests that pass regardless of whether the fix is correct.

The minimum revision required:
1. Increase test count to ~20-23.
2. Explicitly specify use of `@testing-library/react` with `render`, `screen`, `fireEvent`/`userEvent`.
3. Add a test wrapper utility that provides `QueryClientProvider` for React Query-dependent tests.
4. Cover BOTH delete buttons for UI-H5.
5. Test JavaScript-side validation (not just HTML attributes) for UI-H3.
6. Add at least one negative test per finding.
