"""Per-node model routing configuration.

Phase MR8: Different LangGraph nodes have different intelligence requirements.
Router and responder are pure functions (no LLM), agent needs an LLM.
This module provides ModelConfig to map node names to model identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Default models per privacy mode.
_EXTERNAL_AGENT_MODEL = "anthropic/claude-sonnet-4-20250514"
_PRIVATE_AGENT_MODEL = "ollama/llama3.1"
_NO_MODEL = "none"


@dataclass
class ModelConfig:
    """Per-node model configuration.

    Attributes:
        router: Model for the router node (always "none" -- pure function).
        agent: Model for the agent node (the only node that calls an LLM).
        responder: Model for the responder node (always "none" -- pure function).
    """

    router: str = _NO_MODEL
    agent: str = _EXTERNAL_AGENT_MODEL
    responder: str = _NO_MODEL

    def to_dict(self) -> dict[str, str]:
        """Convert to plain dict for AgentState storage."""
        return {
            "router": self.router,
            "agent": self.agent,
            "responder": self.responder,
        }

    @classmethod
    def for_privacy_mode(cls, privacy_mode: str) -> ModelConfig:
        """Create a ModelConfig appropriate for the given privacy mode.

        Args:
            privacy_mode: "private" or "external".

        Returns:
            ModelConfig with the correct agent model for the mode.
        """
        if privacy_mode == "private":
            return cls(agent=_PRIVATE_AGENT_MODEL)
        return cls(agent=_EXTERNAL_AGENT_MODEL)

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> ModelConfig:
        """Create a ModelConfig from user preference overrides.

        Args:
            settings: Dict with optional keys "router", "agent", "responder"
                      whose values are model identifier strings.

        Returns:
            ModelConfig with overrides applied on top of defaults.
        """
        return cls(
            router=settings.get("router", _NO_MODEL),
            agent=settings.get("agent", _EXTERNAL_AGENT_MODEL),
            responder=settings.get("responder", _NO_MODEL),
        )
