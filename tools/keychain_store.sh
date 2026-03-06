#!/usr/bin/env bash
# keychain_store.sh — Store/retrieve Noa secrets in macOS Keychain.
#
# Usage:
#   ./keychain_store.sh set <key-name> <value>
#   ./keychain_store.sh get <key-name>
#   ./keychain_store.sh delete <key-name>
#
# All secrets are stored under the service name "noa" in the login keychain.
# SPEC.md §11.1, §11.2

set -euo pipefail

SERVICE="noa"

usage() {
    echo "Usage: $0 {set|get|delete} <key-name> [value]"
    echo ""
    echo "Commands:"
    echo "  set <key> <value>   Store a secret in the keychain"
    echo "  get <key>           Retrieve a secret from the keychain"
    echo "  delete <key>        Remove a secret from the keychain"
    exit 1
}

if [[ $# -lt 2 ]]; then
    usage
fi

COMMAND="$1"
KEY_NAME="$2"

case "$COMMAND" in
    set)
        if [[ $# -lt 3 ]]; then
            echo "Error: 'set' requires a value argument" >&2
            usage
        fi
        VALUE="$3"
        # Delete existing entry if present (security add fails on duplicates)
        security delete-generic-password -s "$SERVICE" -a "$KEY_NAME" 2>/dev/null || true
        security add-generic-password -s "$SERVICE" -a "$KEY_NAME" -w "$VALUE"
        echo "Stored '$KEY_NAME' in keychain under service '$SERVICE'"
        ;;
    get)
        security find-generic-password -s "$SERVICE" -a "$KEY_NAME" -w 2>/dev/null
        ;;
    delete)
        security delete-generic-password -s "$SERVICE" -a "$KEY_NAME" 2>/dev/null
        echo "Deleted '$KEY_NAME' from keychain"
        ;;
    *)
        echo "Error: Unknown command '$COMMAND'" >&2
        usage
        ;;
esac
