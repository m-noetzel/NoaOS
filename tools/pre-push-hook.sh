#!/usr/bin/env bash
# pre-push-hook.sh — Local pre-push checks for Noa project.
# Runs ruff, mypy, and pytest (if noa-dev container is running).
# Install via: tools/install-hooks.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

# ── Container guard ───────────────────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^noa-dev$'; then
  echo ""
  echo "⚠️  WARNING: noa-dev container not running — ALL pre-push checks SKIPPED"
  echo "   Run 'docker compose up -d' to enable pre-push validation."
  echo ""
  exit 0
fi

ERRORS=0

# ── Ruff lint ────────────────────────────────────────────────────────────────
echo ""
info "Running ruff check src/ tests/ ..."
if docker exec noa-dev python -m ruff check src/ tests/ 2>&1; then
    pass "ruff"
else
    fail "ruff check failed — fix lint errors before pushing"
    ERRORS=$((ERRORS + 1))
fi

# ── Mypy type check ──────────────────────────────────────────────────────────
echo ""
info "Running mypy src/ --ignore-missing-imports ..."
if docker exec noa-dev python -m mypy src/ --ignore-missing-imports 2>&1; then
    pass "mypy"
else
    fail "mypy type check failed — fix type errors before pushing"
    ERRORS=$((ERRORS + 1))
fi

# ── Pytest unit tests ────────────────────────────────────────────────────────
echo ""
info "Running pytest tests/unit/ -x -q --tb=short ..."
if docker exec noa-dev python -m pytest tests/unit/ -x -q --tb=short 2>&1; then
    pass "pytest"
else
    fail "Unit tests failed — fix failing tests before pushing"
    ERRORS=$((ERRORS + 1))
fi

# ── Result ───────────────────────────────────────────────────────────────────
echo ""
if [ "$ERRORS" -eq 0 ]; then
    pass "All pre-push checks passed"
    exit 0
else
    fail "$ERRORS check(s) failed — push aborted"
    exit 1
fi
