"""Re-export OllamaClient from its canonical shared location.

The actual implementation lives in noa.llm.providers.ollama (per C2).
This module exists for backward compatibility with existing imports.
"""

from noa.llm.providers.ollama import OllamaClient

__all__ = ["OllamaClient"]
