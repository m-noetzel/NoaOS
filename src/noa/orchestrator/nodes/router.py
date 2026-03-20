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

from noa.config import DEFAULT_EXTERNAL_MODEL, DEFAULT_PRIVATE_MODEL
from noa.orchestrator.model_config import ModelConfig
from noa.orchestrator.state import AgentState
from noa.privacy.classifier import PrivacyClassifier
from noa.types import PrivacyMode

# Legacy model selections per domain (kept for selected_model backward compat).
_LOCAL_MODEL = DEFAULT_PRIVATE_MODEL
_EXTERNAL_MODEL = DEFAULT_EXTERNAL_MODEL

# Shared classifier instance.
_classifier = PrivacyClassifier()


def router_node(state: AgentState) -> dict[str, Any]:
    """Classify the request and select model. Returns state update dict."""
    # Pass only messages and requested_tools to the classifier.
    classify_state: dict[str, Any] = {
        "messages": state.get("messages", []),
    }
    if "requested_tools" in state:
        classify_state["requested_tools"] = state["requested_tools"]
    if "user_privacy_override" in state:
        classify_state["privacy_mode"] = state["user_privacy_override"]
    private_available = state.get("private_available", True)
    result = _classifier.classify(classify_state, private_available=private_available)
    privacy_mode = result.domain

    # Respect user's explicit model/provider choice if provided.
    user_model = state.get("user_model_override")
    user_provider = state.get("user_provider_override")

    if privacy_mode == PrivacyMode.PRIVATE:
        # Private mode always uses local model, regardless of user choice.
        selected_model = _LOCAL_MODEL
    elif user_provider and user_model:
        # User explicitly chose provider + model — use them.
        selected_model = f"{user_provider}/{user_model}"
    elif user_model:
        selected_model = user_model
    else:
        selected_model = _EXTERNAL_MODEL

    # Build default model_config from privacy mode.
    model_config = ModelConfig.for_privacy_mode(privacy_mode)
    # Override agent model to match the selected model.
    model_config.agent = selected_model

    # MC1: Merge with user-configured node_models (already in state.model_config).
    # User preferences seed the initial state; router only overrides "agent"
    # (since privacy_mode drives that choice). Classifier and other nodes
    # use whatever the user configured if present, otherwise router defaults.
    existing_config: dict[str, str] = state.get("model_config") or {}
    router_config = model_config.to_dict()
    # Start from router defaults, then let user settings override non-agent keys.
    # Router always enforces the "agent" model (privacy_mode is authoritative).
    merged: dict[str, str] = {**router_config, **existing_config}
    # Always enforce router's agent model (privacy_mode is authoritative for agent)
    merged["agent"] = router_config["agent"]

    return {
        "privacy_mode": privacy_mode,
        "selected_model": selected_model,
        "model_config": merged,
    }
