# Getting Started with Noa

Your personal AI agent — web UI + native iOS app.

---

## Part 1 — Backend (Mac + Docker)

### Prerequisites

- macOS 13+ with Docker Desktop running
- At least one LLM API key (Anthropic recommended)

### Step 1 — Store your API keys in the Keychain

Noa reads secrets from your macOS Keychain. Nothing is stored in files.

```bash
# Required: at least one LLM provider
./scripts/keychain_store.sh ANTHROPIC_API_KEY "sk-ant-your-key-here"
# or OpenAI:
./scripts/keychain_store.sh OPENAI_API_KEY "sk-your-key-here"

# Required: system secrets (generate once)
./scripts/keychain_store.sh SECRET_KEY "$(openssl rand -hex 32)"
./scripts/keychain_store.sh JWT_SECRET "$(openssl rand -hex 32)"
./scripts/keychain_store.sh POSTGRES_PASSWORD "$(openssl rand -hex 16)"
./scripts/keychain_store.sh BACKUP_PASSPHRASE "$(openssl rand -hex 16)"
```

### Step 2 — Generate the secrets file and start

```bash
# Generate .env.secrets from Keychain (run this every time you add a key)
./tools/keychain_bootstrap.sh

# Start everything
docker compose up -d

# Apply database schema
make migrate
```

### Step 3 — Create your account

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}' | python3 -m json.tool
```

### Step 4 — Open the web UI

Navigate to **http://localhost:5173** and log in.

---

## Part 2 — iOS App on Your iPhone

### What you need

- Xcode 16+ (from the Mac App Store)
- An Apple Developer account (free account works for personal use, 7-day install; paid $99/yr for longer)
- Your iPhone plugged in via USB

### Step 1 — Open the project in Xcode

```
File → Open → navigate to ios/Noa/Package.swift → Open
```

Xcode will resolve the Swift Package dependencies automatically.

### Step 2 — Configure your Team & Bundle ID

1. In the Project Navigator, click the **Noa** package
2. Select the **Noa** target → **Signing & Capabilities**
3. Set **Team** to your Apple Developer account
4. Change **Bundle Identifier** to something unique, e.g. `com.yourname.noa`

### Step 3 — Set your backend URL

For running against your Mac's backend, your iPhone and Mac must be on the same Wi-Fi network.

Find your Mac's local IP:
```bash
ipconfig getifaddr en0
# e.g. 192.168.1.42
```

Edit `ios/Noa/Sources/Noa/Configuration/Environment.swift`, change the development URL:
```swift
case .development:
    return URL(string: "http://192.168.1.42:8000")!
```

You also need to expose the backend on your local network (it currently binds to `127.0.0.1` only). Add this to `docker-compose.yml` under the `noa-api` ports section:
```yaml
ports:
  - "127.0.0.1:8000:8000"   # existing (web)
  - "192.168.1.42:8000:8000" # add: LAN access for iOS
```

Then restart: `docker compose up -d`.

### Step 4 — Trust the app on your iPhone

1. In Xcode: select your iPhone from the device picker at the top
2. Press **⌘R** (Run) — Xcode builds and installs the app
3. On your iPhone: **Settings → General → VPN & Device Management → Developer App → Trust**

The app is now installed and trusted. It will re-install automatically when you build from Xcode.

### Push Notifications (optional)

Push notifications require a paid Apple Developer account and an APNs key:

1. In [developer.apple.com](https://developer.apple.com) → **Certificates, IDs & Profiles** → **Keys** → create a key with **Apple Push Notifications service (APNs)** enabled
2. Download the `.p8` file and store it at `/etc/noa/apns.p8` on your Mac (or adjust the path)
3. Store the credentials:
```bash
./scripts/keychain_store.sh APNS_KEY_ID "your-key-id"
./scripts/keychain_store.sh APNS_TEAM_ID "your-team-id"
./scripts/keychain_store.sh APNS_BUNDLE_ID "com.yourname.noa"
# APNS_KEY_PATH is set in docker-compose.yml, default: /etc/noa/apns.p8
```
4. Re-run `./tools/keychain_bootstrap.sh && docker compose up -d`

---

## Part 3 — Connecting Tools

Tools are enabled automatically when their credentials are present. Add a key → re-bootstrap → restart.

### Web Search (Tavily)

1. Sign up at [tavily.com](https://tavily.com) → Dashboard → copy your API key
2. Store it:
```bash
./scripts/keychain_store.sh TAVILY_API_KEY "tvly-your-key"
./tools/keychain_bootstrap.sh && docker compose up -d
```
3. In the Noa web UI → **Tools** → enable **web_search**

### Google Calendar & Gmail

This requires a Google Cloud project with the Calendar and Gmail APIs enabled.

#### One-time Google Cloud setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a new project (e.g. "Noa")
2. **APIs & Services → Enable APIs** → enable **Google Calendar API** and **Gmail API**
3. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorized redirect URI: `http://localhost:8000/auth/google/callback`
4. Download the JSON — copy the **Client ID** and **Client Secret**

#### Store credentials

```bash
./scripts/keychain_store.sh GOOGLE_CLIENT_ID "your-client-id.apps.googleusercontent.com"
./scripts/keychain_store.sh GOOGLE_CLIENT_SECRET "your-client-secret"
```

#### Authorize (get a refresh token)

```bash
./tools/keychain_bootstrap.sh && docker compose up -d

# Open this URL in your browser — log in with your Google account
open "http://localhost:8000/auth/google/authorize"
```

After authorizing, the refresh token is stored automatically in the database. Calendar and Gmail tools are now active.

### Notion

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) → **New Integration**
2. Name it "Noa", select your workspace, copy the **Internal Integration Token**
3. Share each Notion page/database you want Noa to access: open the page → **Share → Invite → Noa**
4. Store the token:
```bash
./scripts/keychain_store.sh NOTION_TOKEN "ntn_your-token"
./tools/keychain_bootstrap.sh && docker compose up -d
```
5. In the Noa web UI → **Tools** → enable **notion**

---

## Part 4 — Switching the AI Provider

By default, Noa uses **Claude Sonnet** (Anthropic) if that key is present, otherwise falls back to OpenAI, then Google AI.

### Switch to GPT-4.1 mini (OpenAI)

**Option A — Make OpenAI the default provider** (affects all conversations):

Add `DEFAULT_PROVIDER=openai` to your `.env.secrets` file, or store it in Keychain and add it to `keychain_bootstrap.sh`.

Quickest way:
```bash
# Append to .env.secrets (re-run keychain_bootstrap.sh will overwrite this, so add permanently):
echo "DEFAULT_PROVIDER=openai" >> .env.secrets
echo "DEFAULT_MODEL=gpt-4.1-mini" >> .env.secrets
docker compose up -d
```

To make it permanent, edit `tools/keychain_bootstrap.sh` and add:
```bash
echo "DEFAULT_PROVIDER=openai" >> "$OUTPUT"
echo "DEFAULT_MODEL=gpt-4.1-mini" >> "$OUTPUT"
```

Then update `docker-compose.yml` to pass those vars through:
```yaml
environment:
  - DEFAULT_PROVIDER=${DEFAULT_PROVIDER:-anthropic}
  - DEFAULT_MODEL=${DEFAULT_MODEL:-}
```

**Option B — Switch per conversation** (from the UI):

In the web UI → chat composer → model picker (bottom-right) → select **OpenAI → gpt-4.1-mini**.

**Available models:**

| Provider | Key in Keychain | Models |
|----------|----------------|--------|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514`, `claude-opus-4-5` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4.1`, `gpt-4.1-mini`, `gpt-4o` |
| Google AI | `GOOGLE_AI_API_KEY` | `gemini-2.0-flash`, `gemini-pro` |
| Ollama (local) | — | `llama3.1`, `mistral` (runs on your Mac, no key needed) |

---

## Quick Reference

```bash
# Start everything
./tools/keychain_bootstrap.sh && docker compose up -d && make migrate

# View logs
docker compose logs -f noa-api

# Stop
docker compose down

# Full reset (DELETES ALL DATA)
docker compose down -v && make migrate

# Re-run all tests
docker exec noa-dev bash -c "cd /workspace && python -m pytest tests/unit/ -q"
```

**Web UI:** http://localhost:5173
**API:** http://localhost:8000
**API docs (Swagger):** http://localhost:8000/docs
