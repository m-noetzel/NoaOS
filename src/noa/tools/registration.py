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
