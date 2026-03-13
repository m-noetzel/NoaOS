#!/usr/bin/env bash
# audit-deps.sh — Run dependency security audits inside the dev container.
# Called on container startup and available for manual runs.
# Non-blocking: logs warnings but does not prevent container from starting.
set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}── Dependency Security Audit ──${NC}"

# Python
echo -e "\n${BOLD}Python (pip-audit):${NC}"
if command -v pip-audit &>/dev/null; then
    pip-audit --desc 2>&1 | tail -5
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        echo -e "${GREEN}✓ No known vulnerabilities${NC}"
    else
        echo -e "${YELLOW}⚠ Vulnerabilities found — run 'pip-audit' for details${NC}"
    fi
else
    echo -e "${YELLOW}⚠ pip-audit not installed${NC}"
fi

# Node (web/)
echo -e "\n${BOLD}Node (npm audit):${NC}"
if [[ -f /workspace/web/package-lock.json ]]; then
    (cd /workspace/web && npm audit --omit=dev 2>&1 | tail -5)
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        echo -e "${GREEN}✓ No known vulnerabilities${NC}"
    else
        echo -e "${YELLOW}⚠ Vulnerabilities found — run 'cd web && npm audit' for details${NC}"
    fi
else
    echo "No package-lock.json found — skipping"
fi

# Process snapshot — baseline for comparison
echo -e "\n${BOLD}Process baseline:${NC}"
ps aux --no-headers 2>/dev/null | awk '{print $11}' | sort -u | head -20

echo -e "\n${BOLD}Open network connections:${NC}"
ss -tunp 2>/dev/null | grep -v "State" | head -10 || echo "ss not available"

echo -e "\n${GREEN}── Audit complete ──${NC}"
