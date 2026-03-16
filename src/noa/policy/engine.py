"""Risk tier classification & policy rules — SPEC.md §21."""

from __future__ import annotations

from typing import Any

# Action → risk tier mappings per §21 tables
_LOW_ACTIONS = frozenset(
    [
        "web_search",
        "memory_recall",
        "memory_store",
        "read_email",
        "read_calendar",
        "read_notion",
        "local_summarization",
        "draft_generation",
        "read_only_query",
        # Actual function names from TOOL_SCHEMAS
        "list_events",
        "search_emails",
        "search_pages",
        "read_page",
        "draft_email",
        # Memory tool functions
        "remember",
        "recall",
        "auto_extract",
    ]
)

_MEDIUM_ACTIONS = frozenset(
    [
        "send_email",
        "create_calendar_event",
        "update_calendar_event",
        "create_notion_page",
        "update_notion_page",
        "repo_modification",
        # Actual function names from TOOL_SCHEMAS
        "create_event",
        "create_page",
    ]
)

_HIGH_ACTIONS = frozenset(
    [
        "delete_email",
        "delete_calendar_event",
        "delete_notion_page",
        "modify_system_file",
        "dependency_change",
        "financial_transaction",
        "merge_to_main",
        "delete_data",
    ]
)


class PolicyEngine:
    """Classifies actions into risk tiers and determines approval needs."""

    def classify(self, action: str, args: dict[str, Any]) -> str:
        """Classify an action into a risk tier per §21.

        Returns 'low', 'medium', or 'high'. Unknown actions default to 'high'.
        """
        if action in _LOW_ACTIONS:
            return "low"
        if action in _MEDIUM_ACTIONS:
            return "medium"
        if action in _HIGH_ACTIONS:
            return "high"
        # Unknown actions default to high for safety
        return "high"

    def requires_approval(self, risk_tier: str) -> bool:
        """Check if a risk tier requires user approval per §21."""
        return risk_tier in ("medium", "high")

    def requires_step_up_auth(self, risk_tier: str) -> bool:
        """Check if a risk tier requires step-up authentication per §21."""
        return risk_tier == "high"

    def requires_preview(self, risk_tier: str) -> bool:
        """Check if a risk tier requires dry-run preview per §19.2."""
        return risk_tier in ("medium", "high")
