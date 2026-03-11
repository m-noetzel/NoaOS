# Architecture Invariants

System-level rules that must hold across all phases. QA reviews check against these. Violations are BLOCKING.

---

## L1: Layering Rules

```
Clients (web/, cli/)
    ↓ HTTP only
API Layer (src/noa/api/)
    ↓ function calls
Services (src/noa/auth/, src/noa/orchestrator/, src/noa/tools/)
    ↓ function calls
Data Layer (src/noa/db/)
    ↓ SQLAlchemy
Postgres
```

**Rules:**
1. **API layer** imports from services and data layer. Never imports from workers directly.
2. **Services** import from data layer. Never import from API layer.
3. **Data layer** (models, engine) imports nothing from API or services.
4. **Workers** (private, external) communicate with the control plane via RPC only — never import from `src/noa/api/` or `src/noa/db/` directly.
5. **No circular imports.** If A imports B, B must not import A (directly or transitively).

---

## L2: Dependency Direction

```
src/noa/api/     → src/noa/auth/, src/noa/orchestrator/, src/noa/db/
src/noa/auth/    → src/noa/db/
src/noa/orchestrator/ → src/noa/db/, src/noa/tools/, src/noa/workers/
src/noa/tools/   → external APIs only (never src/noa/db/ directly — goes through orchestrator)
src/noa/workers/ → RPC contract only
src/noa/db/      → (leaf node — imports nothing from src/noa/)
```

---

## L3: Domain Isolation

From SPEC.md §6.2, §8.1, §8.3:

1. **Private domain code** must never make external network calls (no `requests`, `httpx`, `urllib` to internet).
2. **External domain code** must never access private data storage directly.
3. **All cross-domain communication** goes through the RPC contract (SPEC.md §9).
4. **No shared Docker volumes** between private and external containers.
5. **No shared Docker networks** between private and external containers.

---

## L4: Naming Conventions

### Python
- **Packages/modules**: `snake_case` (e.g., `src/noa/auth/jwt.py`)
- **Classes**: `PascalCase` (e.g., `RunEvent`, `AuthService`)
- **Functions/methods**: `snake_case` (e.g., `create_access_token`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_COUNT`)
- **Private**: prefix with `_` (e.g., `_compute_hash`)

### API
- **Endpoints**: `/api/v1/{resource}` — plural nouns, kebab-case for multi-word
- **Response envelope**: all responses wrapped in standard envelope (SPEC.md §25.3)
- **Error codes**: machine-readable string codes, not just HTTP status

### Database
- **Tables**: `snake_case`, plural (e.g., `run_events`, `audit_logs`)
- **Columns**: `snake_case` (e.g., `created_at`, `user_id`)
- **Foreign keys**: `{referenced_table_singular}_id` (e.g., `user_id`, `run_id`)

### Git
- **Branches**: `agent/<agent_id>-<task_slug>`
- **Commits**: `<scope>: <summary>` (e.g., `auth: add JWT refresh endpoint`)

---

## L5: Error Schema

All errors follow a consistent structure:

```python
{
    "ok": False,
    "error": {
        "code": "AUTH_TOKEN_EXPIRED",    # machine-readable, UPPER_SNAKE_CASE
        "message": "Access token has expired",  # human-readable
        "details": {}                     # optional context
    },
    "meta": {
        "trace_id": "uuid",
        "timestamp": "ISO8601"
    }
}
```

**Rules:**
1. Never return bare strings as errors.
2. Never expose stack traces in production responses.
3. Error codes are stable — once published, don't rename them.
4. Log full error context server-side; return safe summary client-side.

---

## L6: Logging Schema

Structured JSON logging everywhere:

```python
{
    "timestamp": "ISO8601",
    "level": "INFO|WARNING|ERROR",
    "logger": "noa.auth.service",
    "message": "descriptive message",
    "trace_id": "uuid",
    "user_id": "uuid or null",
    "extra": {}
}
```

**Rules:**
1. Never log secrets, passwords, tokens, or raw private-domain content.
2. Every log entry includes `trace_id` for request correlation.
3. Use `structlog` or equivalent structured logger — no bare `print()` statements.

---

## L7: Configuration

From SPEC.md §4.1:

1. All config via environment variables with sensible defaults.
2. Secrets never in config files — always env vars or secret manager.
3. Config is validated at startup — fail fast on invalid config.
4. No runtime config mutation — config is immutable after startup.

---

## L8: Testing

1. **Unit tests** use in-memory database (SQLite with async adapter or test Postgres).
2. **No network calls** in unit tests — mock all external boundaries.
3. **No filesystem side effects** in unit tests — use `tmp_path` fixture.
4. **Tests are independent** — no shared mutable state between tests.
5. **Deterministic** — no time-dependent, network-dependent, or random-dependent tests without explicit seeding/mocking.

---

## L9: Exception Handling

1. **No bare `except:` blocks.** Always catch specific exception types.
2. **No `except Exception: pass`.** If you catch a broad exception, you must log it (with `trace_id`) or re-raise.
3. **No success responses on error.** An `except` block must never return HTTP 200 or an empty success envelope.
4. **Enforced by ruff:** Rules `E722` (bare except) and `BLE001` (blind exception) are configured as errors in `pyproject.toml`.

---

## L10: Wiring Completeness

1. **Every FastAPI router** must be registered via `app.include_router()` in `app.py`.
2. **Every service class** must be instantiated during app startup or available via dependency injection.
3. **Every worker handler** must be connected to a route in the worker's FastAPI app.
4. **No orphaned code.** If code exists in `src/` but is not reachable from any running application entry point, it is dead code and must be either wired or removed.

---

## L11: Security Defaults

1. **No fallback defaults on secrets.** `secret_key or ""` is forbidden. If a secret is missing, the app must refuse to start.
2. **Default-deny on permissions.** Tool capabilities, API access, and feature flags default to deny. Explicit grant required.
3. **No plaintext token storage.** Tokens in `localStorage` are forbidden. Use httpOnly, Secure, SameSite=Strict cookies.

---

## L12: Write-Path User Scoping

Every write path that stores user-associated data **must** set `user_id` at write time.

**Rules:**
1. Any data model with a `user_id` column must have that column populated on insert — never left null when a user context is available.
2. Read paths that filter by `user_id` are invalid if the corresponding write path does not set it (silent data loss — facts/records become invisible to their owner).
3. When adding a new store method or insert path, verify: "Does the write include `user_id` if the read filters by it?"
4. Applies to all storage: ORM models, in-memory dicts, file-based stores, and caches.

**Checked by:** QA review (cross-check write path vs. read path for any user-scoped resource).

---

## Enforcement

These invariants are checked:
- **Manually** by QA review agent (Checks 4, 6, 7 reference this file)
- **Automatically** via ruff rules (`E722`, `BLE001`, `S101`) at lint time
- **Automatically** via import boundary checks in QA anti-pattern scan
- **At merge time** via `ruff check` + `mypy` static gates
