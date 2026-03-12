#!/usr/bin/env bash
# install-hooks.sh — Install Git hooks for the Noa project.
# Run from the project root: bash tools/install-hooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
    echo "ERROR: .git/hooks directory not found. Are you in the repo root?"
    exit 1
fi

# Install pre-push hook
SRC="$SCRIPT_DIR/pre-push-hook.sh"
DEST="$HOOKS_DIR/pre-push"

cp "$SRC" "$DEST"
chmod +x "$DEST"

echo "Installed pre-push hook: $DEST"
echo ""
echo "The hook will run on every 'git push':"
echo "  - ruff check src/"
echo "  - mypy src/ --ignore-missing-imports"
echo "  - pytest tests/unit/ -x -q --tb=short (if noa-dev container is running)"
echo ""
echo "To skip the hook for an emergency push: git push --no-verify"
