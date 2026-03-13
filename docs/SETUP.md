# Noa — Full System Setup Guide

How to set up Noa from scratch on a macOS machine with Docker.

---

## Prerequisites

| Requirement | Version | Install |
|------------|---------|---------|
| macOS | 13+ (Ventura) | — |
| Docker Desktop | 4.x | `brew install --cask docker` |
| Node.js | 20+ | `brew install node` |
| Python | 3.11+ | `brew install python@3.11` |
| Ollama (optional) | latest | `brew install ollama` |

---

## 1. Clone and Initial Setup

```bash
git clone <repo-url> ~/Projects/NoaOS
cd ~/Projects/NoaOS
```

---

## 2. Obtain API Credentials

You need at least **one LLM provider key**. Everything else is optional.

| Credential | Required? | Where to Get | Notes |
|-----------|-----------|-------------|-------|
| **Anthropic API Key** | Recommended | [console.anthropic.com](https://console.anthropic.com) → API Keys | Best tool-calling, default provider |
| **OpenAI API Key** | Optional | [platform.openai.com](https://platform.openai.com) → API Keys | Alternative: GPT-4.1 / GPT-4.1 mini |
| **Google AI API Key** | Optional | [aistudio.google.com](https://aistudio.google.com) → Get API Key | For Gemini models |
| **Tavily API Key** | Optional | [tavily.com](https://tavily.com) → Dashboard → API Key | Web search tool |
| **Notion Integration Token** | Optional | [notion.so/my-integrations](https://www.notion.so/my-integrations) → New Integration | Notion tool |
| **Google OAuth Client** | Optional | Google Cloud Console → APIs & Services → Credentials | Calendar + Gmail (see Section 6) |

---

## 3. Store Secrets in macOS Keychain

Noa reads credentials from your macOS Keychain at startup. **No secrets in files.**

### Store each key:

```bash
# LLM Providers (at least one required)
./tools/keychain_store.sh set ANTHROPIC_API_KEY "sk-ant-your-key-here"
./tools/keychain_store.sh set OPENAI_API_KEY "sk-your-key-here"
./tools/keychain_store.sh set GOOGLE_AI_API_KEY "AIza-your-key-here"

# Tool Credentials (optional)
./tools/keychain_store.sh set TAVILY_API_KEY "tvly-your-key-here"
./tools/keychain_store.sh set NOTION_TOKEN "ntn_your-token-here"

# System Secrets (generated automatically if not set)
./tools/keychain_store.sh set SECRET_KEY "$(openssl rand -hex 32)"
./tools/keychain_store.sh set POSTGRES_PASSWORD "$(openssl rand -hex 16)"
```

### Verify stored keys:

```bash
# List all Noa keys in Keychain
security find-generic-password -a noa -s "noa/ANTHROPIC_API_KEY" 2>/dev/null && echo "OK" || echo "NOT SET"
```

### Remove a key:

```bash
security delete-generic-password -a noa -s "noa/ANTHROPIC_API_KEY"
```

---

## 4. Start the System

```bash
# Bootstrap: reads Keychain, starts Docker containers with injected secrets
./tools/keychain_bootstrap.sh

# Run database migrations
make migrate

# Start the web UI (separate terminal)
cd web && npm install && npm run dev
```

The system is now running:
- **Web UI**: http://localhost:5173
- **API**: http://localhost:8000
- **Health**: http://localhost:8000/health

---

## 5. First-Run Registration

On first launch (empty database):

1. Open http://localhost:5173
2. You'll see the login page
3. Click "Register" (only available when no users exist)
4. Enter your email and password
5. You're logged in — start chatting

> **Note:** Registration is automatically disabled after the first user is created. Noa is a single-user system.

---

## 6. Google Calendar + Gmail Setup (Optional)

This requires a Google Cloud project with OAuth2 credentials.

### Step 1: Create Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable these APIs:
   - Google Calendar API
   - Gmail API

### Step 2: Configure OAuth Consent Screen

1. Go to APIs & Services → OAuth consent screen
2. Select "External" user type
3. Add your email as a test user
4. Add scopes: `calendar.readonly`, `calendar.events`, `gmail.readonly`, `gmail.send`

### Step 3: Create OAuth Client

1. Go to APIs & Services → Credentials
2. Create Credentials → OAuth 2.0 Client ID
3. Application type: **Web application**
4. Add redirect URI: `http://localhost:8000/api/v1/oauth/google/callback`
5. Copy Client ID and Client Secret

### Step 4: Store in Keychain

```bash
./tools/keychain_store.sh set GOOGLE_CLIENT_ID "your-client-id.apps.googleusercontent.com"
./tools/keychain_store.sh set GOOGLE_CLIENT_SECRET "GOCSPX-your-secret"
```

### Step 5: Authorize in Noa

1. Go to Settings in the Noa UI
2. Click "Connect Google Account"
3. Complete the OAuth flow in your browser
4. Calendar and Gmail tools are now active

---

## 7. Notion Setup (Optional)

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click "New Integration"
3. Name it "Noa", select your workspace
4. Copy the Internal Integration Token
5. Store it:
   ```bash
   ./tools/keychain_store.sh set NOTION_TOKEN "ntn_your-token"
   ```
6. In Notion: share the pages/databases you want Noa to access with the integration
7. Restart Noa: `./tools/keychain_bootstrap.sh`

---

## 8. Local LLM with Ollama (Optional, Free)

For fully offline operation — no data leaves your machine.

```bash
# Install and start Ollama
brew install ollama
ollama serve  # runs on localhost:11434

# Pull a model
ollama pull llama3.1       # 8B, good general purpose
ollama pull qwen2.5:7b     # alternative

# Store config
./tools/keychain_store.sh set DEFAULT_LLM_PROVIDER "ollama"
./tools/keychain_store.sh set DEFAULT_LLM_MODEL "llama3.1"
```

> **Note:** Ollama models run in the **private domain** only. They are used for memory/RAG tasks and private conversations. External tool calls still use cloud LLMs if configured.

---

## 9. LLM Provider Configuration

Set your default provider and model:

```bash
# Option A: Anthropic (recommended)
./tools/keychain_store.sh set DEFAULT_LLM_PROVIDER "anthropic"
./tools/keychain_store.sh set DEFAULT_LLM_MODEL "claude-sonnet-4-20250514"

# Option B: OpenAI
./tools/keychain_store.sh set DEFAULT_LLM_PROVIDER "openai"
./tools/keychain_store.sh set DEFAULT_LLM_MODEL "gpt-4.1-mini"

# Option C: Google
./tools/keychain_store.sh set DEFAULT_LLM_PROVIDER "google"
./tools/keychain_store.sh set DEFAULT_LLM_MODEL "gemini-2.5-flash"

# Option D: Ollama (fully local)
./tools/keychain_store.sh set DEFAULT_LLM_PROVIDER "ollama"
./tools/keychain_store.sh set DEFAULT_LLM_MODEL "llama3.1"
```

You can change the provider at any time. Restart after changing:

```bash
./tools/keychain_bootstrap.sh
```

---

## 10. Verify Everything Works

```bash
# Check all containers are running
docker compose ps

# Check API health
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/metrics

# Check private worker
curl http://localhost:8001/health

# Run test suite
make check   # ruff + mypy + pytest
```

---

## 11. Daily Operation

### Start Noa
```bash
cd ~/Projects/NoaOS
./tools/keychain_bootstrap.sh     # starts backend
cd web && npm run dev               # starts frontend (dev mode)
```

### Stop Noa
```bash
docker compose down
```

### View Logs
```bash
docker compose logs -f noa-api          # API logs
docker compose logs -f private-worker   # Private worker logs
docker compose logs -f external-worker  # External worker logs
```

### Update
```bash
git pull
make migrate                            # apply any new DB migrations
./tools/keychain_bootstrap.sh         # restart with latest
cd web && npm install && npm run dev    # rebuild frontend
```

---

## 12. Backup & Restore

### Manual Backup
```bash
# Database
docker compose exec postgres pg_dump -U noa noa > backup_$(date +%Y%m%d).sql

# Private data
docker compose cp private-worker:/data ./backup_private_$(date +%Y%m%d)/
```

### Restore
```bash
# Database
cat backup_20260306.sql | docker compose exec -T postgres psql -U noa noa
```

---

## Architecture Overview

```
┌─── Your Mac ─────────────────────────────────────────────┐
│                                                           │
│  macOS Keychain ──secrets──▶ Docker Containers            │
│                                                           │
│  ┌── noa-internal (no internet) ───────────────────┐      │
│  │  postgres:5432    private-worker:8001            │      │
│  │  (your data)      (Ollama, Memory, RAG)          │      │
│  └──────────────────────────────────────────────────┘      │
│           ▲                                                │
│     noa-api:8000 (bridge between networks)                │
│           ▼                                                │
│  ┌── noa-external (internet allowed) ──────────────┐      │
│  │  external-worker:8002                            │      │
│  │  (Anthropic, OpenAI, Google, Tavily, Notion)     │      │
│  └──────────────────────────────────────────────────┘      │
│                                                           │
│  Web UI: localhost:5173 ──proxy──▶ noa-api:8000           │
└───────────────────────────────────────────────────────────┘
```

**Security boundaries:**
- Private data never leaves `noa-internal` (no internet access)
- External APIs only accessible from `noa-external`
- API keys injected from Keychain, never stored in files
- All containers: read-only filesystem, non-root user, dropped capabilities

---

## Troubleshooting

### "Cannot connect to database"
```bash
docker compose logs postgres          # check Postgres is running
docker compose exec postgres pg_isready -U noa   # check connectivity
make migrate                          # ensure schema is up to date
```

### "LLM provider error"
```bash
# Verify key is in Keychain
security find-generic-password -a noa -s "noa/ANTHROPIC_API_KEY" -w

# Check container has the key
docker compose exec noa-api printenv ANTHROPIC_API_KEY | head -c 10
```

### "Tool not available"
Check that the tool's credential is stored:
```bash
security find-generic-password -a noa -s "noa/TAVILY_API_KEY" -w 2>/dev/null && echo "OK" || echo "NOT SET"
```
Tools without credentials are automatically disabled at startup.

### Reset everything
```bash
docker compose down -v   # WARNING: deletes all data
make migrate             # recreate schema
```
