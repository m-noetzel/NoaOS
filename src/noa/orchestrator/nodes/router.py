"""Router node — classifies privacy mode and selects model.

Spec refs: SPEC.md S2.1 (privacy routing enforced before execution),
           SPEC.md S6.1 (separation of concerns),
           SPEC.md §14.2, §14.3, §18 (privacy classification).

The router is a pure function: it takes state and returns a partial
state update dict. It never mutates the input state.

Delegates privacy classification to PrivacyClassifier (src/noa/privacy/classifier.py)
to avoid keyword duplication — see Wave 3 retro R3.
"""

from __future__ import annotations

from typing import Any

from noa.orchestrator.state import AgentState
from noa.privacy.classifier import PrivacyClassifier

# Model selections per domain.
_LOCAL_MODEL = "ollama/llama3"
_EXTERNAL_MODEL = "anthropic/claude-haiku"

# Shared classifier instance.
_classifier = PrivacyClassifier()


def router_node(state: AgentState) -> dict[str, Any]:
    """Classify the request and select model. Returns state update dict."""
    # Pass only messages and requested_tools to the classifier.
    # Do NOT pass the existing privacy_mode — the router is the one setting it.
    # An explicit user override would come from the request, not from prior state.
    classify_state: dict[str, Any] = {
        "messages": state.get("messages", []),
    }
    if "requested_tools" in state:
        classify_state["requested_tools"] = state["requested_tools"]
    if "user_privacy_override" in state:
        classify_state["privacy_mode"] = state["user_privacy_override"]
    result = _classifier.classify(classify_state)
    privacy_mode = result.domain
    selected_model = _LOCAL_MODEL if privacy_mode == "private" else _EXTERNAL_MODEL
    return {
        "privacy_mode": privacy_mode,
        "selected_model": selected_model,
    }
