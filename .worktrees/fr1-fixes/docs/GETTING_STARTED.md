# Getting Started with Noa

Your personal AI agent — web UI + native iOS app.

**Security model:** All secrets stay in your macOS Keychain and are injected
directly into memory at runtime. Nothing is ever written to disk.

---

## Part 1 — Backend (Mac + Docker)

### Prerequisites

- macOS 13+ with Docker Desktop running
- At least one LLM API key (Anthropic recommended)
- FileVault enabled (System Settings → Privacy & Security → FileVault)

### Step 1 — First-time setup

Run `./noa setup`. This stores required system secrets in your Keychain
(auto-generated), builds Docker images, and verifies everything is ready.

```bash
./noa setup
```

### Step 2 — Store your API keys

```bash
# At least one LLM provider is required
./noa set ANTHROPIC_API_KEY "sk-ant-your-key-here"
# or OpenAI:
./noa set OPENAI_API_KEY "sk-your-key-here"
```

Verify what's stored at any time:

```bash
./noa keys
# ✓ ANTHROPIC_API_KEY = sk-ant-…
# ✗ OPENAI_API_KEY (not set)
# ✓ SECRET_KEY = 3f9a12…
# ...
```

### Step 3 — Start

```bash
./noa up
```

This reads all secrets from Keychain into RAM, starts all services, runs
database migrations, and waits for a healthy API — all in one command.

### Step 4 — Create your account

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}' | python3 -m json.tool
```

### Step 5 — Open the web UI

Navigate to **http://localhost:5173** and log in.

---

## Part 2 — iOS App on Your iPhone

### What you need

- Xcode 16+ (from the Mac App Store)
- An Apple Developer account (free works for personal use — 7-day install window; paid $99/yr removes that limit)
- Your iPhone plugged in via USB

### Step 1 — Open the project in Xcode

```
File → Open → navigate to ios/Noa/Package.swift → Open
```

Xcode resolves Swift Package dependencies automatically.

### Step 2 — Set your Team & Bundle ID

1. Click the **Noa** package in the Project Navigator
2. Select the **Noa** target → **Signing & Capabilities**
3. Set **Team** to your Apple Developer account
4. Change **Bundle Identifier** to something unique, e.g. `com.yourname.noa`

### Step 3 — Point the app at your Mac's backend

Your iPhone and Mac must be on the same Wi-Fi network.

Find your Mac's local IP:
```bash
ipconfig getifaddr en0
# e.g. 192.168.1.42
```

Edit `ios/Noa/Sources/Noa/Configuration/Environment.swift`:
```swift
case .development:
    return URL(string: "http://192.168.1.42:8000")!
```

Expose the backend on your LAN — in `docker-compose.yml` under `noa-api → ports`, add:
```yaml
ports:
  - "127.0.0.1:8000:8000"    # existing (web browser)
  - "192.168.1.42:8000:8000"  # add this line (iPhone on LAN)
```

Restart: `./noa restart noa-api`

### Step 4 — Build and install

1. Select your iPhone from the device picker at the top of Xcode
2. Press **⌘R** — Xcode builds and installs
3. On iPhone: **Settings → General → VPN & Device Management → Developer App → Trust**

Done. The app reinstalls automatically each time you build from Xcode.

### Push Notifications (optional, requires paid developer account)

1. In [developer.apple.com](https://developer.apple.com) → **Certificates, IDs & Profiles → Keys** → new key with **Apple Push Notifications service (APNs)** enabled
2. Download the `.p8` file, save it to `/etc/noa/apns.p8`
3. Store the credentials:
```bash
./noa set APNS_KEY_ID   "your-key-id"
./noa set APNS_TEAM_ID  "your-team-id"
./noa set APNS_BUNDLE_ID "com.yourname.noa"
```
4. Restart: `./noa restart noa-api`

---

## Part 3 — Connecting Tools

Add a key with `./noa set`, then restart — the tool activates automatically.

### Web Search (Tavily)

1. Sign up at [tavily.com](https://tavily.com) → Dashboard → copy your API key
2. Store and restart:
```bash
./noa set TAVILY_API_KEY "tvly-your-key"
./noa restart noa-api
```
3. In the Noa web UI → **Tools** → enable **web_search**

### Google Calendar & Gmail

Requires a Google Cloud project with the Calendar and Gmail APIs enabled.

#### One-time Google Cloud setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create project "Noa"
2. **APIs & Services → Enable APIs** → enable **Google Calendar API** and **Gmail API**
3. **Credentials → Create → OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorized redirect URI: `http://localhost:8000/auth/google/callback`
4. Copy the **Client ID** and **Client Secret**

#### Store and authorize

```bash
./noa set GOOGLE_CLIENT_ID     "your-id.apps.googleusercontent.com"
./noa set GOOGLE_CLIENT_SECRET "your-secret"
./noa restart noa-api

# Open in browser — sign in with your Google account
open "http://localhost:8000/auth/google/authorize"
```

The refresh token is stored encrypted in the database automatically. Calendar and Gmail are now active.

### Notion

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) → **New Integration**
2. Name it "Noa", select your workspace, copy the **Internal Integration Token**
3. Share pages with the integration: open any page → **Share → Invite → Noa**
4. Store and restart:
```bash
./noa set NOTION_TOKEN "ntn_your-token"
./noa restart noa-api
```
5. In the Noa web UI → **Tools** → enable **notion**

---

## Part 4 — Switching the AI Provider

By default, Noa uses Claude Sonnet (Anthropic) if that key is present, otherwise falls back to OpenAI, then Google AI.

### Switch to GPT-4.1 mini permanently

Add `DEFAULT_PROVIDER` and `DEFAULT_MODEL` to Keychain, then add them to the `KEYCHAIN_MAP` in the `noa` script so they get exported on startup.

**Quickest approach** — edit `docker-compose.yml` to hard-code the default:

```yaml
# under noa-api → environment:
- DEFAULT_PROVIDER=openai
- DEFAULT_MODEL=gpt-4.1-mini
```

Then restart: `./noa restart noa-api`

### Switch per conversation (from the UI)

Web UI → chat composer → model picker (bottom-right) → select **OpenAI → gpt-4.1-mini**.

### Available models

| Provider | Key name | Models |
|----------|----------|--------|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514`, `claude-opus-4-5` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4.1`, `gpt-4.1-mini`, `gpt-4o` |
| Google AI | `GOOGLE_AI_API_KEY` | `gemini-2.0-flash`, `gemini-pro` |
| Ollama (local, free) | — | `llama3.1`, `mistral` — runs on your Mac, no key needed |

---

## Quick Reference

```bash
./noa setup          # first-time setup (generates system secrets, builds images)
./noa up             # start everything (reads Keychain → RAM, no disk writes)
./noa down           # stop all services
./noa restart        # restart all services
./noa logs           # stream all logs
./noa logs noa-api   # stream API logs only
./noa status         # show container health
./noa keys           # show which Keychain secrets are present
./noa set KEY value  # store a secret in Keychain
./noa db migrate     # run database migrations manually
./noa db console     # open a psql shell
./noa reset-password you@example.com   # reset account password
```

**Web UI:** http://localhost:5173
**API:** http://localhost:8000
**API docs (Swagger):** http://localhost:8000/docs
