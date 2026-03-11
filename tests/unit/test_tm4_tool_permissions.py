"""Tests for per-task tool permissions & context scoping — Phase TM4.

Spec refs: SPEC.md §2.1 (tool allowlists static per workflow),
           SPEC.md §2.2 (LLM may not execute tools not in allowlist),
           SPEC.md §19 (Tool Governance)
Phase plan: PHASE_DETAILS.md Phase TM4

These tests define the behavioral contract for task-level tool filtering:
- Approval rules can carry allowed_tools lists
- Orchestrator intersects user capabilities with task allowlist
- Predefined scopes map to known tool+function combos
- Tools not in the intersection are never exposed to the LLM
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tm4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scope_registry() -> Any:
    """Build the scope registry with built-in scopes."""
    from noa.tools.scopes import ToolScopeRegistry
    return ToolScopeRegistry()


# ---------------------------------------------------------------------------
# Scope definition tests
# ---------------------------------------------------------------------------

class TestPredefinedScopes:
    """Verify the built-in scope definitions per PHASE_DETAILS TM4."""

    def test_email_draft_scope_contains_gmail_read_and_draft(self):
        """email_draft scope includes gmail read and draft."""
        registry = _make_scope_registry()
        tools = registry.get_scope("email_draft")
        assert "gmail__read_email" in tools
        assert "gmail__draft_email" in tools

    def test_research_scope_contains_web_search_and_notion_read(self):
        """PHASE TM4: research scope includes web_search and notion read."""
        registry = _make_scope_registry()
        tools = registry.get_scope("research")
        assert "web_search__web_search" in tools or "web_search" in tools
        # Notion read should be present in some form
        scope_str = " ".join(tools)
        assert "notion" in scope_str

    def test_scheduling_scope_contains_calendar_and_gmail_read(self):
        """PHASE TM4: scheduling scope includes calendar and gmail read."""
        registry = _make_scope_registry()
        tools = registry.get_scope("scheduling")
        scope_str = " ".join(tools)
        assert "calendar" in scope_str
        assert "gmail" in scope_str

    def test_unknown_scope_raises_key_error(self):
        """PHASE TM4: requesting a non-existent scope raises KeyError."""
        registry = _make_scope_registry()
        with pytest.raises(KeyError):
            registry.get_scope("nonexistent_scope")

    def test_list_scopes_returns_all_predefined(self):
        """PHASE TM4: list_scopes enumerates at least the 3 predefined scopes."""
        registry = _make_scope_registry()
        scopes = registry.list_scopes()
        assert "email_draft" in scopes
        assert "research" in scopes
        assert "scheduling" in scopes


# ---------------------------------------------------------------------------
# Intersection / filtering logic
# ---------------------------------------------------------------------------

class TestToolIntersection:
    """Verify that the orchestrator filters tools by task allowlist.

    SPEC.md §2.1: 'The set of tools available to any given step is defined
    at graph compile time. The LLM cannot invoke tools not in its allowlist.'
    """

    def test_intersection_limits_to_task_allowlist(self):
        """PHASE TM4: user has 4 tools, task allows 2 — only 2 survive."""
        from noa.tools.scopes import filter_tools_by_allowlist

        user_tools = ["gmail__read_email", "gmail__draft_email",
                      "calendar__list_events", "web_search__web_search"]
        task_allowlist = ["gmail__read_email", "gmail__draft_email"]

        result = filter_tools_by_allowlist(user_tools, task_allowlist)
        assert set(result) == {"gmail__read_email", "gmail__draft_email"}

    def test_intersection_with_no_overlap_returns_empty(self):
        """PHASE TM4: if task allows tools user doesn't have, result is empty."""
        from noa.tools.scopes import filter_tools_by_allowlist

        user_tools = ["gmail__read_email"]
        task_allowlist = ["calendar__list_events"]

        result = filter_tools_by_allowlist(user_tools, task_allowlist)
        assert result == []

    def test_intersection_with_none_allowlist_returns_all(self):
        """PHASE TM4: if no task allowlist is set, all user tools pass through."""
        from noa.tools.scopes import filter_tools_by_allowlist

        user_tools = ["gmail__read_email", "calendar__list_events"]
        result = filter_tools_by_allowlist(user_tools, None)
        assert set(result) == set(user_tools)

    def test_intersection_preserves_order(self):
        """PHASE TM4: filtered list preserves the original user_tools order."""
        from noa.tools.scopes import filter_tools_by_allowlist

        user_tools = ["web_search__web_search", "gmail__read_email",
                      "calendar__list_events"]
        task_allowlist = ["calendar__list_events", "web_search__web_search"]

        result = filter_tools_by_allowlist(user_tools, task_allowlist)
        assert result == ["web_search__web_search", "calendar__list_events"]


# ---------------------------------------------------------------------------
# Approval rule with allowed_tools
# ---------------------------------------------------------------------------

class TestApprovalRuleAllowedTools:
    """Verify that approval rules can specify tool allowlists.

    PHASE TM4: 'Approval rules can specify allowed_tools:
    ["gmail__read_email", "gmail__draft_email"]'
    """

    def test_approval_rule_with_allowed_tools_field(self):
        """PHASE TM4: ApprovalRule schema accepts an allowed_tools list."""
        from noa.policy.approval import ApprovalRule

        rule = ApprovalRule(
            risk_tier="medium",
            allowed_tools=["gmail__read_email", "gmail__draft_email"],
        )
        assert rule.allowed_tools == ["gmail__read_email", "gmail__draft_email"]

    def test_approval_rule_without_allowed_tools_defaults_none(self):
        """PHASE TM4: allowed_tools defaults to None (no restriction)."""
        from noa.policy.approval import ApprovalRule

        rule = ApprovalRule(risk_tier="medium")
        assert rule.allowed_tools is None

    def test_approval_rule_empty_allowed_tools_blocks_all(self):
        """PHASE TM4: empty allowed_tools means no tools are permitted."""
        from noa.policy.approval import ApprovalRule

        rule = ApprovalRule(risk_tier="low", allowed_tools=[])
        assert rule.allowed_tools == []


# ---------------------------------------------------------------------------
# Integration: scope-based filtering end-to-end
# ---------------------------------------------------------------------------

class TestScopeFilteringIntegration:
    """Integration test: resolve a scope, then filter user tools through it.

    This calls real code without mocking internal dependencies.
    """

    def test_scope_to_filtered_tools_end_to_end(self):
        """PHASE TM4: resolve 'email_draft' scope and intersect with user tools."""
        from noa.tools.scopes import ToolScopeRegistry, filter_tools_by_allowlist

        registry = ToolScopeRegistry()
        scope_tools = registry.get_scope("email_draft")

        # User has email + calendar + web search
        user_tools = [
            "gmail__read_email", "gmail__draft_email",
            "gmail__send_email", "calendar__list_events",
            "web_search__web_search",
        ]

        filtered = filter_tools_by_allowlist(user_tools, scope_tools)

        # Only gmail read + draft should survive
        assert "gmail__read_email" in filtered
        assert "gmail__draft_email" in filtered
        assert "calendar__list_events" not in filtered
        assert "web_search__web_search" not in filtered
        # send_email is NOT in email_draft scope (draft only)
        assert "gmail__send_email" not in filtered
