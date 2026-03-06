"""Tool registration — creates tool instances and registers in gateway.

Called at app startup from wire_llm_pipeline().
"""

from __future__ import annotations

import logging
import os

from noa.tools.adapters.direct import DirectApiAdapter
from noa.tools.gateway import ToolGateway

logger = logging.getLogger(__name__)


def register_tools(gateway: ToolGateway) -> None:
    """Register available tools in the gateway.

    Checks environment for API keys and only registers tools
    whose credentials are configured.
    """
    _register_web_search(gateway)
    _register_google_tools(gateway)
    _register_notion(gateway)


def _register_web_search(gateway: ToolGateway) -> None:
    """Register web_search if TAVILY_API_KEY is set."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        logger.info("TAVILY_API_KEY not set — skipping web_search")
        return

    from noa.tools.search_providers.tavily import (
        TavilySearchProvider,
    )
    from noa.tools.web_search import WebSearchTool

    provider = TavilySearchProvider(api_key=api_key)
    tool = WebSearchTool(provider=provider)
    adapter = DirectApiAdapter(tool=tool)
    gateway.register("web_search", adapter)

    # §19.3: web_search rate limit = 30/hour
    gateway.set_rate_limit(
        "web_search", max_calls=30, window_seconds=3600
    )
    logger.info("Registered web_search tool (Tavily)")


def _register_google_tools(gateway: ToolGateway) -> None:
    """Register calendar + gmail if Google OAuth credentials are set."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "")

    if not (client_id and client_secret and refresh_token):
        logger.info(
            "Google credentials not set — skipping calendar + gmail"
        )
        return

    from noa.tools.google_auth import GoogleAuthClient

    auth = GoogleAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=os.environ.get(
            "GOOGLE_REDIRECT_URI",
            "http://localhost:8000/auth/google/callback",
        ),
    )
    # Pre-set the refresh token so the client can auto-refresh
    auth.set_tokens(access_token="", refresh_token=refresh_token)

    _register_calendar(gateway, auth)
    _register_gmail(gateway, auth)


def _register_calendar(
    gateway: ToolGateway, auth: object
) -> None:
    """Register the calendar tool."""
    from noa.tools.calendar import CalendarTool
    from noa.tools.google_calendar_client import GoogleCalendarClient

    api_client = GoogleCalendarClient(auth_client=auth)
    tool = CalendarTool(api_client=api_client)
    adapter = DirectApiAdapter(tool=tool)
    gateway.register("calendar", adapter)
    logger.info("Registered calendar tool (Google Calendar API v3)")


def _register_gmail(
    gateway: ToolGateway, auth: object
) -> None:
    """Register the gmail tool."""
    from noa.tools.gmail import GmailTool
    from noa.tools.google_gmail_client import GmailClient

    api_client = GmailClient(auth_client=auth)
    tool = GmailTool(api_client=api_client)
    adapter = DirectApiAdapter(tool=tool)
    gateway.register("gmail", adapter)
    logger.info("Registered gmail tool (Gmail API v1)")


def _register_notion(gateway: ToolGateway) -> None:
    """Register notion if NOTION_TOKEN is set."""
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        logger.info("NOTION_TOKEN not set — skipping notion")
        return

    from noa.tools.notion import NotionTool
    from noa.tools.notion_client import NotionClient

    api_client = NotionClient(token=token)
    tool = NotionTool(api_client=api_client)
    adapter = DirectApiAdapter(tool=tool)
    gateway.register("notion", adapter)
    logger.info("Registered notion tool (Notion API v1)")
