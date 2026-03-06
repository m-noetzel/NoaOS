#!/usr/bin/env bash
# smoke_test.sh — Docker-based end-to-end smoke test (MR7)
#
# Usage:
#   ./tools/smoke_test.sh
#
# This script runs the MR7 integration smoke tests inside the dev container.
# If Docker is not available, it falls back to running pytest directly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Noa MR7 Smoke Test ==="

if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    echo "Running smoke tests via Docker..."
    docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" run --rm \
        -e NOA_ENV=testing \
        -e SECRET_KEY=test-secret-key-for-smoke \
        -e DATABASE_URL=sqlite+aiosqlite:///:memory: \
        noa-dev python -m pytest tests/integration/test_mr7_smoke.py -v
else
    echo "Docker not available — running tests locally..."
    cd "$PROJECT_ROOT"
    NOA_ENV=testing \
    SECRET_KEY=test-secret-key-for-smoke \
    DATABASE_URL=sqlite+aiosqlite:///:memory: \
    python -m pytest tests/integration/test_mr7_smoke.py -v
fi

echo "=== Smoke test complete ==="
