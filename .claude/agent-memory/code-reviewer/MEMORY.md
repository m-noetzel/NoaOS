# Code Reviewer Memory

## Project Patterns (confirmed)

### Auth
- Auth uses httpOnly cookies for actual tokens; `localStorage.noa_authenticated` is the JS-readable flag (`src/auth/tokens.ts`).
- `AuthGuard` reads `hasTokens()` which checks `localStorage`. E2E tests must call `loginViaUI()` to set this flag — `page.evaluate(() => localStorage.setItem(...))` is an alternative shortcut.
- `AuthContext.logout()` fires a best-effort POST to `/api/v1/auth/logout` then calls `clearTokens()` synchronously. No redirect is performed by the context — Navigation after logout is the page's responsibility (Login.tsx does it via navigate after `useAuth`).

### SSE Client
- `SSEClient` (`src/api/sse.ts`) uses raw `fetch()` with manual SSE parsing. Playwright `page.route()` intercepts this correctly since it intercepts at the network level.
- `SSEClient` only reconnects if `this.runId` is set (populated from the `meta` event). Tests that omit the meta event will not trigger reconnect.
- An empty-line separator in SSE body dispatches the event; the formatter in `e2e/helpers/sse-mock.ts` uses `\n\n` between events which is correct.

### Testing Conventions
- Vitest unit tests live in `web/src/test/`; Playwright E2E tests live in `web/e2e/`.
- `test:e2e` = `playwright test`; `test:e2e:ui` opens the interactive UI; `test:e2e:report` shows last HTML report.
- The Wave 16 E2E fixture pattern: `setupApiMocks(page)` first, then specific overrides, then `loginViaUI(page)`.

### Known Dead Code in Wave 16
- `AUTH_STATE_PATH` in `web/e2e/fixtures.ts` is exported but never imported by any test. It was presumably scaffolded for `storageState`-based auth (Playwright's persistent auth) but that pattern was abandoned in favour of `loginViaUI()`.

### Settings page selectors
- Settings page budget inputs lack `htmlFor` associations; tests reach them via `page.locator('input[type="number"]').first()` (daily) and `.nth(1)` (monthly). This is fragile — if field order changes the tests silently break.
