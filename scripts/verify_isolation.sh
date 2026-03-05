#!/bin/bash
# verify_isolation.sh -- Continuous network isolation verification (SPEC.md Section 20.4)
#
# Runs inside the Docker host to verify that the private container cannot
# reach the internet via IPv4, IPv6, or DNS. Any successful egress is a
# security violation and triggers an alert.
#
# Usage: ./scripts/verify_isolation.sh
#
# Exit codes:
#   0 — All isolation checks passed (egress correctly blocked)
#   1 — Isolation breach detected (egress succeeded when it should not)

set -euo pipefail

PRIVATE_CONTAINER="private-worker"
CANARY_URL="https://canary.example.com"
PASS=0
FAIL=0

log_pass() { echo "[PASS] $1"; PASS=$((PASS + 1)); }
log_fail() { echo "[FAIL] $1"; FAIL=$((FAIL + 1)); }

# ---------------------------------------------------------------------------
# Test 1: Private container IPv4 egress must be blocked
# ---------------------------------------------------------------------------
echo "=== Test 1: Private container egress (curl IPv4) ==="
if docker compose exec -T "$PRIVATE_CONTAINER" \
    curl -s --max-time 5 "$CANARY_URL" >/dev/null 2>&1; then
    log_fail "Private container reached $CANARY_URL — egress NOT blocked!"
else
    log_pass "Private container cannot reach $CANARY_URL — egress blocked."
fi

# ---------------------------------------------------------------------------
# Test 2: Private container DNS resolution must be blocked
# ---------------------------------------------------------------------------
echo "=== Test 2: Private container DNS resolution (nslookup) ==="
if docker compose exec -T "$PRIVATE_CONTAINER" \
    nslookup google.com >/dev/null 2>&1; then
    log_fail "Private container resolved google.com — DNS NOT blocked!"
else
    log_pass "Private container cannot resolve google.com — DNS blocked."
fi

# ---------------------------------------------------------------------------
# Test 3: Private container IPv6 egress must be blocked
# ---------------------------------------------------------------------------
echo "=== Test 3: Private container IPv6 egress (curl -6) ==="
if docker compose exec -T "$PRIVATE_CONTAINER" \
    curl -6 -s --max-time 5 "$CANARY_URL" >/dev/null 2>&1; then
    log_fail "Private container reached $CANARY_URL via IPv6 — egress NOT blocked!"
else
    log_pass "Private container cannot reach $CANARY_URL via IPv6 — egress blocked."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Isolation Verification Summary ==="
echo "Passed: $PASS  Failed: $FAIL"

if [ "$FAIL" -gt 0 ]; then
    echo "ALERT: Network isolation breach detected! Review container network config."
    exit 1
fi

echo "All isolation checks passed."
exit 0
