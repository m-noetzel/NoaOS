# Claude Code Dev Container — Security Policy

Aligned with SPEC.md §2.4, §8, §11, §16.2, §20.
Last updated: 2026-03-07.

---

## GRANT

- **Workspace read/write:** project repo mount only (`/workspace`)
- **Git local:** status, diff, branch, commit, local merge-to-main after tests pass
- **Dev tooling:** linters, type checks, tests, coverage, migrations
- **Browser testing:** Playwright/headless browser, screenshots, traces, videos
- **Test services:** test-only Postgres, Redis, mock services (never production)
- **Code editing:** application code (`src/`), test code (`tests/`), docs, pre-commit config
- **Package registries:** access to allowlisted domains for dependency install (see egress list)
- **Test-only API keys:** injected as env vars or tmpfs files, revocable, least-privilege
- **Artifact writing:** logs, coverage reports, test artifacts inside workspace only

---

## DENY

- **No host Docker socket** (`/var/run/docker.sock`)
- **No privileged mode** (`--privileged`)
- **No host network mode** (`--network=host`)
- **No host PID namespace** (`--pid=host`)
- **No broad host mounts** (`~`, `.ssh`, `Documents`, `Downloads`, `Desktop`, or unrelated folders)
- **No direct macOS Keychain access** (secrets come via env vars from the host launcher script)
- **No production credentials or production databases**
- **No remote git push** (human-only; CLAUDE.md git workflow)
- **No remote force-push** (any branch, any remote)
- **No org-admin GitHub rights**
- **No direct deploy to any environment**
- **No unrestricted internet** (egress allowlist enforced)
- **No personal SaaS accounts**

---

## CONTAINER HARDENING

| Setting | Value | Spec Ref |
|---------|-------|----------|
| User | Non-root (dedicated dev user) | §8.1, §8.2 |
| Root filesystem | Read-only (`--read-only`) | §8.1 |
| Capabilities | `--cap-drop=ALL`, add back only what's needed | §8.1 |
| Seccomp | Default Docker seccomp profile (minimum) | §8.1 |
| Writable mounts | Workspace + narrow cache/temp mount only | §8.2 |
| CPU time per command | 5 minutes max | §2.4 |
| Memory per command | 4 GB max | §2.4 |
| Concurrent shells | 2 max | §2.4 |

---

## SECRET HANDLING

Priority order (most secure first):

1. **tmpfs-mounted secret files** (preferred)
2. **Environment variables** (when file-based injection is impractical)

Rules:

- Secrets are **never** written to disk inside the container (§11.2)
- Secrets are **never** logged, even at debug level (§11.2)
- Secrets are **never** passed as command-line arguments (visible in `ps aux`)
- Secrets are **never** persisted in workspace files (code, config, test fixtures)
- Secrets are **never** echoed in shell history or debug output
- Automatic log redaction for known secret patterns (API keys, tokens, passwords)
- Test-only keys only — never production credentials
- Revocable and least-privilege scoped

---

## NETWORK EGRESS ALLOWLIST

Only these domains are reachable from the container. All other egress is blocked.

| Domain | Purpose |
|--------|---------|
| `api.anthropic.com` | Anthropic LLM API |
| `api.openai.com` | OpenAI LLM API |
| `generativelanguage.googleapis.com` | Google Gemini LLM API |
| `gmail.googleapis.com` | Gmail tool |
| `www.googleapis.com` | Google Calendar API |
| `oauth2.googleapis.com` | Google OAuth token exchange |
| `accounts.google.com` | Google OAuth authorization |
| `api.notion.com` | Notion tool |
| `api.tavily.com` | Tavily web search |
| `registry.npmjs.org` | npm packages |
| `pypi.org` | Python packages |
| `files.pythonhosted.org` | Python package downloads |

**Note:** SPEC.md §20.3 uses `*.googleapis.com` — this policy narrows it to the 4 specific
subdomains the codebase actually uses. If a new Google API is added, its subdomain must be
explicitly added here.

`github.com` is **not** in the allowlist. The repo is bind-mounted (not cloned at runtime) and
all dependencies come from PyPI/npm. If a future dependency requires GitHub access, add the
specific domain with justification.

---

## AUDIT

- **Every shell command + exit code** logged (§2.4)
- **DNS queries** logged (§20.3)
- **Git operations** logged
- **Test results and coverage reports** retained as workspace artifacts
- Logs kept inside workspace for human review

---

## GOVERNANCE (human approval required)

The following changes are **never** applied autonomously. Claude may propose patches, but a
human must review and approve before they take effect.

**Infrastructure and config:**
- `Dockerfile`, `docker-compose.yml`, `.devcontainer/` config
- CI/CD workflows (`.github/workflows/`, etc.)
- Shell bootstrap scripts (`tools/*.sh`)
- Package/task scripts that affect execution, secrets, or network (`Makefile`, `package.json` scripts)
- Linter/type-checker config changes that weaken enforcement (e.g., removing ruff rules)

**Git and deployment:**
- Remote push to any branch
- Merge to main on remote
- Deploy to any environment

**Secrets and access:**
- New secret provisioning or rotation
- Changes to egress allowlist
- Changes to container capabilities or mounts
