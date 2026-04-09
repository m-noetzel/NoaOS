"""Tests for MEM1 — Proactive Memory Storage system prompt rewrite.

Spec ref: SPEC.md §12.5 / MEM1
Verifies that the system prompt uses PROACTIVE language instead of STRICT
and that it encourages storage of the expected categories.
"""

from __future__ import annotations

from pathlib import Path

SYSTEM_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "system_prompt.txt"


def _load_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def test_mem1_no_strict_label() -> None:
    """The system prompt must not have the 'STRICT' storage label."""
    prompt = _load_prompt()
    # The old heading was "### Storage (STRICT)" — verify it is gone
    assert "### Storage (STRICT)" not in prompt, (
        "Found legacy STRICT storage heading in system prompt"
    )


def test_mem1_proactive_label_present() -> None:
    """The system prompt must use 'PROACTIVE' as the storage label."""
    prompt = _load_prompt()
    assert "PROACTIVE" in prompt, (
        "Expected PROACTIVE label in Memory Usage section"
    )


def test_mem1_personal_facts_category() -> None:
    """Prompt must instruct storage of personal facts (name, location, etc.)."""
    prompt = _load_prompt()
    assert "Personal facts" in prompt or "personal facts" in prompt, (
        "Expected personal facts category in PROACTIVE memory section"
    )


def test_mem1_preferences_category() -> None:
    """Prompt must instruct storage of preferences."""
    prompt = _load_prompt()
    assert "Preferences" in prompt or "preferences" in prompt.lower(), (
        "Expected preferences category in PROACTIVE memory section"
    )


def test_mem1_important_dates_category() -> None:
    """Prompt must instruct storage of important dates."""
    prompt = _load_prompt()
    assert "Important dates" in prompt or "important dates" in prompt.lower(), (
        "Expected important dates category in PROACTIVE memory section"
    )


def test_mem1_project_context_category() -> None:
    """Prompt must instruct storage of project context."""
    prompt = _load_prompt()
    assert "Project context" in prompt or "project context" in prompt.lower(), (
        "Expected project context category in PROACTIVE memory section"
    )


def test_mem1_proactive_auto_extract_instruction() -> None:
    """Prompt must instruct the LLM to call auto_extract proactively."""
    prompt = _load_prompt()
    assert "memory__auto_extract" in prompt, (
        "Expected memory__auto_extract tool call instruction in prompt"
    )
    # Should not require user to ask explicitly
    assert "proactively" in prompt or "Proactively" in prompt, (
        "Expected proactive extraction instruction (do not wait for explicit request)"
    )
