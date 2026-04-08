"""Per-node model routing configuration.

Phase MR8: Different LangGraph nodes have different intelligence requirements.
Router is a pure function (no LLM), agent needs an LLM.
This module provides ModelConfig to map node names to model identifiers.

OV3: responder field removed — responder node was deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from noa.config import DEFAULT_EXTERNAL_MODEL, DEFAULT_PRIVATE_MODEL
from noa.types import PrivacyMode

# Default models per privacy mode (aliases from config).
_EXTERNAL_AGENT_MODEL = DEFAULT_EXTERNAL_MODEL
_PRIVATE_AGENT_MODEL = DEFAULT_PRIVATE_MODEL
_NO_MODEL = "none"

_EXTERNAL_CLASSIFIER_MODEL = "openai/gpt-4o-mini"
_PRIVATE_CLASSIFIER_MODEL = DEFAULT_PRIVATE_MODEL
_EXTERNAL_PLANNER_MODEL = "openai/gpt-4o-mini"
_PRIVATE_PLANNER_MODEL = DEFAULT_PRIVATE_MODEL
_EXTERNAL_EVALUATOR_MODEL = "openai/gpt-4o-mini"
_PRIVATE_EVALUATOR_MODEL = DEFAULT_PRIVATE_MODEL


@dataclass
class ModelConfig:
    """Per-node model configuration.

    Attributes:
        router: Model for the router node (always "none" -- pure function).
        agent: Model for the agent node (the only node that calls an LLM).
        classifier: Model for the classifier node (cheap model for task type detection).
        planner: Model for the planner node (cheap model, defaults same as classifier).
        evaluator: Model for the evaluator node (cheap model for response scoring).

    Note: OV3 removed the responder field — responder node was deleted.
    """

    router: str = _NO_MODEL
    agent: str = _EXTERNAL_AGENT_MODEL
    classifier: str = _EXTERNAL_CLASSIFIER_MODEL
    planner: str = _EXTERNAL_PLANNER_MODEL
    evaluator: str = _EXTERNAL_EVALUATOR_MODEL

    def to_dict(self) -> dict[str, str]:
        """Convert to plain dict for AgentState storage."""
        return {
            "router": self.router,
            "agent": self.agent,
            "classifier": self.classifier,
            "planner": self.planner,
            "evaluator": self.evaluator,
        }

    @classmethod
    def for_privacy_mode(cls, privacy_mode: str) -> ModelConfig:
        """Create a ModelConfig appropriate for the given privacy mode.

        Args:
            privacy_mode: "private" or "external".

        Returns:
            ModelConfig with the correct agent model for the mode.
        """
        if privacy_mode == PrivacyMode.PRIVATE:
            return cls(
                agent=_PRIVATE_AGENT_MODEL,
                classifier=_PRIVATE_CLASSIFIER_MODEL,
                planner=_PRIVATE_PLANNER_MODEL,
                evaluator=_PRIVATE_EVALUATOR_MODEL,
            )
        return cls(
            agent=_EXTERNAL_AGENT_MODEL,
            classifier=_EXTERNAL_CLASSIFIER_MODEL,
            planner=_EXTERNAL_PLANNER_MODEL,
            evaluator=_EXTERNAL_EVALUATOR_MODEL,
        )

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> ModelConfig:
        """Create a ModelConfig from user preference overrides.

        Args:
            settings: Dict with optional keys "router", "agent",
                      "classifier", "planner", "evaluator" whose values
                      are model identifier strings.

        Returns:
            ModelConfig with overrides applied on top of defaults.
        """
        return cls(
            router=settings.get("router", _NO_MODEL),
            agent=settings.get("agent", _EXTERNAL_AGENT_MODEL),
            classifier=settings.get("classifier", _EXTERNAL_CLASSIFIER_MODEL),
            planner=settings.get("planner", _EXTERNAL_PLANNER_MODEL),
            evaluator=settings.get("evaluator", _EXTERNAL_EVALUATOR_MODEL),
        )
