

# Noa — Personal Agent Console (Revised Plan)

## Auth System
- Login page with **identifier + password** fields (not email-specific)
- Access + refresh token flow: tokens stored in `localStorage` with rotation on refresh
- Centralized fetch wrapper with 401 → refresh token → retry logic
- Route guards: unauthenticated users redirected to `/login`
- Logout clears tokens and redirects

## API Client
- **Generate typed client from OpenAPI spec** at `http://localhost:8000/openapi.json`
- Use a code generation tool (e.g., `openapi-typescript` for types, or `openapi-fetch`) to produce typed interfaces and endpoint definitions
- All responses follow envelope `{ data, meta, error }` — typed generically
- React Query hooks wrapping the generated client
- `VITE_API_BASE_URL` env var only (no runtime UI switching)

## Mock Data Layer
- Mock service matching generated types and envelope format
- Simulated SSE streams for chat dev/testing
- Feature flag or env check to swap mock ↔ real API

## Layout
- Collapsible sidebar: Chat, Runs, Approvals, Queue, Memory, Artifacts, Cost, Settings
- Top bar: model selector, privacy toggle, session status
- System-preference dark/light mode with toggle

## Pages

### Chat
- Thread sidebar, message timeline, streaming renderer
- Composer: privacy toggle, model selector, advanced options (temperature, max_tokens)
- SSE via `fetch()` + `ReadableStream` — renders token_stream, tool_called, approval_requested, result_ready, error events
- Reconnect with backoff (1s→2s→5s→10s) via `GET /runs/{run_id}/events`

### Runs
- Table: created_at, summary, status, risk tier, privacy, model, tokens, cost
- Filters: status, risk tier, privacy, provider, date range
- Detail page: event timeline, tool calls, approvals, artifacts, errors

### Approvals
- Pending list with risk tier, preview, run ref, approve/deny buttons
- Batch approve/deny support

### Queue
- Active + queued runs, split private/external
- Cancel and view actions

### Memory Audit
- Pending facts: approve/edit/reject
- Approved facts: searchable with delete

### Artifacts
- List by type (file, diff, export, preview)
- Type-specific viewers

### Cost Dashboard
- Per-run, session, daily, monthly totals
- Budget progress bars, Recharts charts

### Settings
- Default model, privacy mode, budget limits (no API URL field)

## Reusable Components
RunStatusBadge, RiskTierBadge, PrivacyModeBadge, ModelSelector, PrivacyToggle, EventTimeline, ToolCallChip, ApprovalCard, QueueList, FactReviewTable, CostCharts, ArtifactViewer, JSONViewer

## PWA
- Web manifest + service worker for installability

