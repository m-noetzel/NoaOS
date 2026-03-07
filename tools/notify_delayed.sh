#!/bin/bash
# Delayed notification — sends only if Claude is still waiting after DELAY seconds.
# Used by the Stop hook. Cancelled by the PreToolUse hook clearing the token file.

DELAY=60
TOKEN_FILE="/tmp/.claude_stop_token"
NOTIFY_SCRIPT="/Users/martin2020/Projekte/NoaOS/tools/notify.py"

# Generate unique token for this stop event
token="$$-$(date +%s)"
echo "$token" > "$TOKEN_FILE"

# Background: wait, then check if still waiting
(
  sleep "$DELAY"
  if [ -f "$TOKEN_FILE" ] && [ "$(cat "$TOKEN_FILE" 2>/dev/null)" = "$token" ]; then
    python3 "$NOTIFY_SCRIPT" "Claude wartet" "Input benötigt (>${DELAY}s idle)"
    rm -f "$TOKEN_FILE"
  fi
) &

exit 0
