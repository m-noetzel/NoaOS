#!/usr/bin/env bash
# BU1: Bundle size gate
# Fails if any single JS/CSS chunk exceeds 500 KB gzipped.
# Usage: bash scripts/check-bundle-size.sh [--no-build]
#
# Pass --no-build to skip the build step (useful when dist/ already exists).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$WEB_DIR/dist/assets"
MAX_GZIP_KB=500
FAIL=0

cd "$WEB_DIR"

if [[ "${1:-}" != "--no-build" ]]; then
  echo "==> Building..."
  npm run build
fi

if [[ ! -d "$DIST_DIR" ]]; then
  echo "ERROR: dist/assets not found. Run the build first."
  exit 1
fi

echo ""
echo "==> Checking chunk sizes (limit: ${MAX_GZIP_KB} KB gzipped)"
echo ""

# Print header
printf "%-60s %10s %10s %6s\n" "File" "Raw (KB)" "Gzip (KB)" "Status"
printf "%-60s %10s %10s %6s\n" "----" "--------" "---------" "------"

while IFS= read -r file; do
  filename="$(basename "$file")"
  raw_bytes=$(wc -c < "$file")
  raw_kb=$(( raw_bytes / 1024 ))

  # gzip to temp file, measure
  tmp=$(mktemp)
  gzip -c "$file" > "$tmp"
  gz_bytes=$(wc -c < "$tmp")
  rm -f "$tmp"
  gz_kb=$(( gz_bytes / 1024 ))

  if (( gz_kb > MAX_GZIP_KB )); then
    status="FAIL"
    FAIL=1
  else
    status="ok"
  fi

  printf "%-60s %10d %10d %6s\n" "$filename" "$raw_kb" "$gz_kb" "$status"
done < <(find "$DIST_DIR" -maxdepth 1 \( -name "*.js" -o -name "*.css" \) | sort)

echo ""

if (( FAIL == 1 )); then
  echo "FAIL: One or more chunks exceed ${MAX_GZIP_KB} KB gzipped."
  echo "      Consider splitting large chunks further or removing unused dependencies."
  exit 1
else
  echo "PASS: All chunks are within the ${MAX_GZIP_KB} KB gzipped limit."
fi
