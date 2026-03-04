"""Router node — classifies privacy mode and selects model.

Spec refs: SPEC.md S2.1 (privacy routing enforced before execution),
           SPEC.md S6.1 (separation of concerns).

The router is a pure function: it takes state and returns a partial
state update dict. It never mutates the input state.
"""

from __future__ import annotations

from typing import Any

from noa.orchestrator.state import AgentState

# Keywords that signal private / personal data access.
_PRIVATE_KEYWORDS: frozenset[str] = frozenset(
    [
        "journal",
        "diary",
        "private",
        "personal",
        "my notes",
        "my files",
        "secret",
        "password",
        "confidential",
    ]
)

# Model selections per domain.
_LOCAL_MODEL = "ollama/llama3"
_EXTERNAL_MODEL = "anthropic/claude-haiku"


def _classify_privacy(messages: list[dict[str, Any]]) -> str:
    """Return 'private' if the latest user message references personal data."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "").lower()
            if any(kw in content for kw in _PRIVATE_KEYWORDS):
                return "private"
            return "external"
    return "external"


def router_node(state: AgentState) -> dict[str, Any]:
    """Classify the request and select model. Returns state update dict."""
    privacy_mode = _classify_privacy(state.get("messages", []))
    selected_model = _LOCAL_MODEL if privacy_mode == "private" else _EXTERNAL_MODEL
    return {
        "privacy_mode": privacy_mode,
        "selected_model": selected_model,
    }
