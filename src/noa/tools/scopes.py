"""Tool scope registry and filtering — SPEC.md §2.1, §19 (Tool Governance).

Provides predefined task-level scopes that map to known tool+function
combinations, and a filtering function that intersects user capabilities
with a task allowlist so the LLM only sees tools relevant to the current task.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Predefined scope definitions
# ---------------------------------------------------------------------------

_PREDEFINED_SCOPES: dict[str, list[str]] = {
    "email_draft": [
        "gmail__read_email",
        "gmail__draft_email",
    ],
    "research": [
        "web_search__web_search",
        "notion__read_page",
        "notion__search",
    ],
    "scheduling": [
        "calendar__list_events",
        "calendar__create_event",
        "gmail__read_email",
    ],
}


class ToolScopeRegistry:
    """Registry of named tool scopes.

    Each scope maps to a list of tool__function identifiers that are
    permitted when the orchestrator runs a task in that context.
    """

    def __init__(self) -> None:
        self._scopes: dict[str, list[str]] = dict(_PREDEFINED_SCOPES)

    def get_scope(self, name: str) -> list[str]:
        """Return the tool list for a named scope.

        Raises:
            KeyError: If the scope name is not registered.
        """
        if name not in self._scopes:
            raise KeyError(name)
        return list(self._scopes[name])

    def list_scopes(self) -> list[str]:
        """Return all registered scope names."""
        return list(self._scopes.keys())

    def register_scope(self, name: str, tools: list[str]) -> None:
        """Register or overwrite a named scope."""
        self._scopes[name] = list(tools)


def filter_tools_by_allowlist(
    user_tools: list[str],
    task_allowlist: list[str] | None,
) -> list[str]:
    """Intersect user-enabled tools with a task-level allowlist.

    Per SPEC.md §2.1: the set of tools available to any given step is
    defined at graph compile time. The LLM cannot invoke tools not in
    its allowlist.

    Args:
        user_tools: Tools the user has enabled globally.
        task_allowlist: Tools permitted for this task. If ``None``,
            all user tools pass through (no restriction).

    Returns:
        Filtered list preserving the original ``user_tools`` order.
    """
    if task_allowlist is None:
        return list(user_tools)

    allowed_set = set(task_allowlist)
    return [t for t in user_tools if t in allowed_set]
