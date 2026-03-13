# TLS Setup — Caddy Reverse Proxy

Noa uses [Caddy](https://caddyserver.com/) as a TLS-terminating reverse proxy in front of the FastAPI backend. Caddy handles:

- Automatic HTTPS via Let's Encrypt (ACME) for public domains
- Automatic HTTPS via its internal CA for local/private domains
- HTTP → HTTPS permanent redirect (308)
- HSTS header injection (`Strict-Transport-Security`)

---

## Quick Start

### 1. Set required environment variable

```bash
export NOA_DOMAIN=noa.example.com          # public domain
# or
export NOA_DOMAIN=noa.tailXXXX.ts.net      # Tailscale MagicDNS hostname
# or
export NOA_DOMAIN=localhost                # local dev (no DNS needed)
```

Optionally set an ACME email (recommended for Let's Encrypt notifications):

```bash
export NOA_ACME_EMAIL=you@example.com
```

### 2. Start the stack

```bash
docker compose up
```

Caddy automatically:
- Obtains a TLS certificate via ACME (for public domains)
- Creates a local CA certificate (for `localhost`)
- Redirects all HTTP traffic to HTTPS
- Proxies HTTPS → `noa-api:8000`

---

## Scenario A: Public Domain (Let's Encrypt)

**Requirements:**
- A domain (e.g. `noa.example.com`) pointing at your server's public IP via DNS A record
- Port 80 and 443 open on the server (for ACME HTTP-01 challenge)

**Setup:**
1. Add DNS A record: `noa.example.com → <server-public-ip>`
2. Set `NOA_DOMAIN=noa.example.com`
3. Set `NOA_ACME_EMAIL=you@example.com`
4. Run `docker compose up`

Caddy will automatically request and renew a certificate from Let's Encrypt.

---

## Scenario B: Tailscale / LAN (Internal CA)

**Requirements:**
- Tailscale installed on server and client devices
- MagicDNS enabled on your Tailnet (Settings → DNS)

**Setup:**
1. Find your Tailscale hostname: `tailscale status --json | jq '.Self.DNSName'`
   Example: `noa.tailXXXX.ts.net`
2. Set `NOA_DOMAIN=noa.tailXXXX.ts.net`
3. Run `docker compose up`

Caddy uses its internal CA for Tailscale/LAN-only hostnames. The iOS app must trust Caddy's internal CA certificate (one-time step on first run — see below).

**Trust the internal CA on iOS:**
```bash
# Export Caddy's root CA certificate
docker exec $(docker compose ps -q caddy) caddy trust
# Or: copy from the caddy-data volume
docker cp $(docker compose ps -q caddy):/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
```
Then AirDrop `caddy-root.crt` to the iPhone and install via Settings → General → VPN & Device Management.

---

## Scenario C: Local Dev (localhost)

**Requirements:** None — works out of the box.

**Setup:**
1. Set `NOA_DOMAIN=localhost` (or leave unset — this is the default)
2. Run `docker compose up`

Caddy uses `tls internal` automatically for `localhost`. Your browser will show a certificate warning; click "Advanced → Proceed" or:

```bash
# Trust Caddy's local CA in your system keychain (macOS)
docker exec $(docker compose ps -q caddy) caddy trust
```

The web app is reachable at `https://localhost`.

**Note on OAuth2 in local dev:** Google OAuth2 requires a registered redirect URI. For local testing use `http://localhost:8000` directly (bypassing Caddy) or register `https://localhost` in Google Cloud Console with a self-signed cert exception.

---

## Port Mapping

| Port | Service | Description |
|------|---------|-------------|
| 80 | caddy | HTTP — always redirects to HTTPS (308) |
| 443 | caddy | HTTPS — TLS-terminated, proxied to `noa-api:8000` |
| 8000 | noa-api | Internal Docker network only — not exposed to host |

In production, `noa-api` port 8000 is **not exposed** to the host. All traffic enters through Caddy.

---

## Volumes

| Volume | Purpose |
|--------|---------|
| `caddy-data` | TLS certificates, ACME state, private keys |
| `caddy-config` | Caddy runtime configuration cache |

**Keep `caddy-data` persistent** — losing it forces certificate re-issuance (rate-limited by Let's Encrypt to 5 per week per domain).

---

## CORS Configuration

When `NOA_DOMAIN` is set to a non-localhost value, the API automatically adds `https://{NOA_DOMAIN}` to its CORS allow-list. The CORS config never allows `*` when credentials are required (M2).

To allow additional origins (e.g. a local dev server alongside a production domain):

```bash
export CORS_ALLOWED_ORIGINS="https://noa.example.com,http://localhost:5173"
```

---

## Troubleshooting

### Certificate not issued (public domain)
- Verify DNS: `dig noa.example.com` must resolve to your server IP
- Verify port 80 is reachable from the internet (ACME HTTP-01 challenge)
- Check Caddy logs: `docker compose logs caddy`

### "Certificate signed by unknown authority" on iOS
- You are using Caddy's internal CA. Follow the iOS trust steps in Scenario B.

### Port 443 already in use
- Check for another service: `sudo lsof -i :443`
- Stop conflicting service or change Caddy's port binding in `docker-compose.yml`

### Let's Encrypt rate limits
- LE limits: 5 duplicate certificates per week per domain
- Use `NOA_ACME_EMAIL` for renewal notifications
- For testing, set `NOA_DOMAIN=localhost` or a staging ACME server
