"""Shared LLM provider clients — domain-neutral location per C2.

OllamaClient lives here so both private_worker and external_worker
can use it without cross-domain imports.
"""

from __future__ import annotations

from noa.llm.providers.ollama import OllamaClient

__all__ = ["OllamaClient"]
