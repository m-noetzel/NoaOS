#!/usr/bin/env bash
# keychain_bootstrap.sh — DEPRECATED.
#
# Previously wrote secrets to .env.secrets on disk.
# Use `./noa` instead — it injects secrets directly from Keychain into
# docker compose without writing anything to disk.
#
# Example:
#   ./noa up -d          # start all services
#   ./noa logs -f        # stream logs
#   ./noa down           # stop

echo "⚠️  keychain_bootstrap.sh is deprecated." >&2
echo "   Use ./noa instead — secrets stay in RAM, nothing written to disk." >&2
echo "" >&2
echo "   ./noa up -d        # start" >&2
echo "   ./noa logs -f      # logs" >&2
echo "   ./noa down         # stop" >&2
exit 1
