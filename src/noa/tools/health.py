"""Tool health-check and credential-status services — Phase TM1.

Provides:
- ToolHealthChecker: per-tool health probes (external API reachability)
- CredentialStatusChecker: reports configured vs. missing credentials
- mask_credential: returns masked display of a secret value
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known tools and their required secrets
# ---------------------------------------------------------------------------

_TOOL_REQUIRED_SECRETS: dict[str, list[str]] = {
    "web_search": ["TAVILY_API_KEY"],
    "google_calendar": [
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
    ],
    "gmail": [
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
    ],
    "notion": ["NOTION_INTEGRATION_TOKEN"],
    "memory": ["MEMORY_STORE_DSN"],
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
        import os

        return bool(os.environ.get(secret_name))

    async def get_status(self, tool_name: str) -> str:
        """Return 'configured' if all required secrets are present, else 'missing'."""
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


class ToolHealthChecker:
    """Per-tool health probes verifying external API reachability."""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    # --- Probe methods (one per tool) ---

    async def _probe_tavily(self) -> None:
        """Probe Tavily web search API."""
        key = os.environ.get("TAVILY_API_KEY")
        if not key:
            raise ConnectionError("TAVILY_API_KEY not configured")
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": "test", "max_results": 1},
            )
            r.raise_for_status()

    async def _probe_google_calendar(self) -> None:
        """Probe Google Calendar API."""
        token = os.environ.get("GOOGLE_REFRESH_TOKEN")
        if not token:
            raise ConnectionError("Google credentials not configured")
        # Lightweight: list 0 events from primary calendar
        access = os.environ.get("GOOGLE_ACCESS_TOKEN", "")
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(
                "https://www.googleapis.com/calendar/v3"
                "/calendars/primary/events",
                params={"maxResults": "1"},
                headers={"Authorization": f"Bearer {access}"},
            )
            r.raise_for_status()

    async def _probe_gmail(self) -> None:
        """Probe Gmail API."""
        token = os.environ.get("GOOGLE_REFRESH_TOKEN")
        if not token:
            raise ConnectionError("Google credentials not configured")
        access = os.environ.get("GOOGLE_ACCESS_TOKEN", "")
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(
                "https://gmail.googleapis.com/gmail/v1"
                "/users/me/messages",
                params={"maxResults": "1"},
                headers={"Authorization": f"Bearer {access}"},
            )
            r.raise_for_status()

    async def _probe_notion(self) -> None:
        """Probe Notion API."""
        token = os.environ.get("NOTION_INTEGRATION_TOKEN")
        if not token:
            raise ConnectionError(
                "NOTION_INTEGRATION_TOKEN not configured",
            )
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(
                "https://api.notion.com/v1/search",
                json={"query": "", "page_size": 1},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Notion-Version": "2022-06-28",
                },
            )
            r.raise_for_status()

    async def _probe_memory(self) -> None:
        """Probe memory store (always available locally)."""
        # Memory store is file-based, always reachable

    # --- Tool-to-probe mapping ---

    _PROBE_MAP: dict[str, str] = {
        "web_search": "_probe_tavily",
        "google_calendar": "_probe_google_calendar",
        "gmail": "_probe_gmail",
        "notion": "_probe_notion",
        "memory": "_probe_memory",
    }

    async def check(self, tool_name: str) -> dict[str, Any]:
        """Run the health probe for the named tool.

        Returns {"status": "ok"|"error", "error": str|None}.
        """
        probe_method_name = self._PROBE_MAP.get(tool_name)
        if probe_method_name is None:
            return {"status": "error", "error": f"Unknown tool: {tool_name}"}

        probe = getattr(self, probe_method_name)
        try:
            await asyncio.wait_for(probe(), timeout=self.timeout)
        except TimeoutError:
            msg = f"Health probe timeout after {self.timeout}s"
            return {"status": "error", "error": msg}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Health probe failed for %s: %s", tool_name, exc)
            return {"status": "error", "error": str(exc)}

        return {"status": "ok", "error": None}
