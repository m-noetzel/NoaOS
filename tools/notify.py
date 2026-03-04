#!/usr/bin/env python3
"""Send push notifications via ntfy.sh.

Usage:
    python tools/notify.py "Title" "Message body"
    python tools/notify.py "Message body"              # title defaults to "NoaOS Agent"

Configure the topic via NTFY_TOPIC env var (default: noaos-by2lnbzr).
"""

import os
import sys
import urllib.request

TOPIC = os.environ.get("NTFY_TOPIC", "noaos-by2lnbzr")
URL = f"https://ntfy.sh/{TOPIC}"


def send(title: str, message: str) -> None:
    req = urllib.request.Request(URL, data=message.encode())
    req.add_header("Title", title)
    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()


if __name__ == "__main__":
    if len(sys.argv) == 3:
        send(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        send("NoaOS Agent", sys.argv[1])
    else:
        print(f"Usage: {sys.argv[0]} [title] message", file=sys.stderr)
        sys.exit(1)
