"""Ollama client for local LLM inference per SPEC.md §8.1."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for interacting with a local Ollama instance."""

    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model_manifest: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_manifest = model_manifest or {}

    def build_inference_request(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Build the request body for an Ollama inference call.

        Returns a dict suitable for POSTing to /api/generate.
        """
        return {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

    def is_model_approved(self, model_name: str) -> bool:
        """Check whether a model name is in the approved manifest per §8.1."""
        return model_name in self.model_manifest
