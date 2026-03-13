"""Tool health-check and credential-status services — Phase TM1.

Provides:
- ToolHealthChecker: per-tool health probes via gateway adapters
- CredentialStatusChecker: reports configured vs. missing credentials
- mask_credential: returns masked display of a secret value
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known tools and their required secrets
# ---------------------------------------------------------------------------

_TOOL_REQUIRED_SECRETS: dict[str, list[str]] = {
    "web_search": ["TAVILY_API_KEY"],
    "calendar": [
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    ],
    "gmail": [
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
    ],
    "notion": ["NOTION_TOKEN"],
    "memory": [],
    "external_memory": [],  # BE-H9: external domain memory — no credentials needed
}

# All known tool names (for validation)
KNOWN_TOOLS: set[str] = set(_TOOL_REQUIRED_SECRETS)


# ---------------------------------------------------------------------------
# mask_credential
# ---------------------------------------------------------------------------


def mask_credential(value: str | None) -> str:
    """Return a masked version of a credential for safe display.

    - Empty/None returns empty string
    - Short values (<=8 chars) are fully masked
    - Longer values show last 4 chars with prefix masked
    """
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return "****" + value[-4:]


# ---------------------------------------------------------------------------
# CredentialStatusChecker
# ---------------------------------------------------------------------------


class CredentialStatusChecker:
    """Check whether required secrets for each tool are configured."""

    def required_secrets(self, tool_name: str) -> list[str]:
        """Return the list of secret names required for a tool."""
        return _TOOL_REQUIRED_SECRETS.get(tool_name, [])

    async def _check_secret(self, secret_name: str) -> bool:
        """Check whether a single secret is configured.

        Default implementation checks environment variables.
        Can be patched in tests.
        """
        return bool(os.environ.get(secret_name))

    async def get_status(self, tool_name: str) -> str:
        """Return 'configured' or 'missing'."""
        secrets = self.required_secrets(tool_name)
        if not secrets:
            return "configured"
        for secret_name in secrets:
            if not await self._check_secret(secret_name):
                return "missing"
        return "configured"


# ---------------------------------------------------------------------------
# ToolHealthChecker
# ---------------------------------------------------------------------------

# Lightweight probe requests per tool. These go through the
# actual registered adapters in the gateway, which already have
# valid credentials and auth clients wired at startup.
_PROBE_REQUESTS: dict[str, dict[str, Any]] = {
    "web_search": {
        "function": "web_search",
        "args": {"query": "test", "max_results": 1},
    },
    "calendar": {
        "function": "list_events",
        "args": {
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2026-01-01T01:00:00Z",
        },
    },
    "gmail": {
        "function": "search_emails",
        "args": {"query": "test", "max_results": 1},
    },
    "notion": {
        "function": "search_pages",
        "args": {"query": "test"},
    },
}


def _check_memory_health(*, tool_name: str = "memory") -> dict[str, Any]:
    """Check memory tool health by verifying MemoryStore is available.

    The memory tool does not use external credentials — it only needs
    the /data volume to be mounted and the MemoryStore singleton to be
    accessible via app_state.  This probe never makes network calls.

    Args:
        tool_name: "memory" (private) or "external_memory" (BE-H9).
    """
    try:
        if tool_name == "external_memory":
            from noa.api.app_state import get_external_memory_store
            store = get_external_memory_store()
        else:
            from noa.api.app_state import get_memory_store
            store = get_memory_store()

        if store is None:
            return {
                "status": "error",
                "error": "MemoryStore not wired — /data volume may be missing",
            }
        # Confirm the store has a data_dir configured (volume mount check)
        data_dir = getattr(store, "_data_dir", None)
        if data_dir is None:
            return {
                "status": "error",
                "error": (
                    "MemoryStore has no data_dir"
                    " — memory will not persist across restarts"
                ),
            }
        return {"status": "ok", "error": None}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Memory health check error: %s", exc)
        return {"status": "error", "error": str(exc)}


class ToolHealthChecker:
    """Per-tool health probes via the ToolGateway.

    Uses the actual registered adapters (with real credentials)
    rather than reimplementing API calls.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    async def check(
        self, tool_name: str,
    ) -> dict[str, Any]:
        """Run a health probe for the named tool.

        Returns {"status": "ok"|"error", "error": str|None}.
        """
        from noa.orchestrator.nodes.tools import get_gateway

        gw = get_gateway()

        # If gateway not wired, check if secrets exist at least
        if gw is None:
            return {
                "status": "error",
                "error": "Tool gateway not initialized",
            }

        # Check if tool is registered in gateway
        if tool_name not in gw.list_tools():
            # Not registered = credentials missing at startup
            secrets = _TOOL_REQUIRED_SECRETS.get(
                tool_name, [],
            )
            missing = [
                s for s in secrets
                if not os.environ.get(s)
            ]
            if missing:
                return {
                    "status": "error",
                    "error": (
                        f"Not registered — missing: "
                        f"{', '.join(missing)}"
                    ),
                }
            # No required secrets — tool may not need credentials.
            # For memory tools specifically, check MemoryStore availability
            # via app_state rather than via gateway registration.
            if tool_name in ("memory", "external_memory"):
                return _check_memory_health(tool_name=tool_name)
            return {
                "status": "error",
                "error": "Tool not registered in gateway",
            }

        # Tool is registered — do a real probe via adapter
        probe = _PROBE_REQUESTS.get(tool_name)
        if probe is None:
            # No probe defined — registered = healthy
            return {"status": "ok", "error": None}

        from noa.tools.gateway import ToolRequest

        req = ToolRequest(
            tool=tool_name,
            function=probe["function"],
            args=probe["args"],
        )

        try:
            resp = await asyncio.wait_for(
                gw.dispatch(req),
                timeout=self.timeout,
            )
        except TimeoutError:
            msg = f"Probe timeout after {self.timeout}s"
            return {"status": "error", "error": msg}
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Health probe failed for %s: %s",
                tool_name, exc,
            )
            return {"status": "error", "error": str(exc)}

        if resp.error:
            return {
                "status": "error",
                "error": resp.error,
            }
        return {"status": "ok", "error": None}
