"""OllamaEmbedder — thin wrapper for generating embeddings via Ollama.

W24-M4: Provides a dedicated class for embedding generation, usable
independently from the full OllamaClient LLM interface.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

# Default embedding model and dimension
DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_DIM = 768


class OllamaEmbedder:
    """Generate vector embeddings via Ollama's /api/embed endpoint.

    Args:
        base_url: Ollama server URL (default: http://localhost:11434).
        model: Embedding model name (default: nomic-embed-text).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector for the given text.

        Args:
            text: Input text to embed.

        Returns:
            List of floats (768-dim for nomic-embed-text).

        Raises:
            RuntimeError: If Ollama is unavailable or returns an error.
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            ) as client:
                resp = await client.post(
                    "/api/embed",
                    json={"model": self.model, "input": text},
                )
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings", [])
                if not embeddings:
                    msg = f"No embeddings returned from Ollama for model {self.model}"
                    raise RuntimeError(msg)
                return list(embeddings[0])
        except httpx.HTTPError as exc:
            msg = f"Ollama embed request failed: {exc}"
            raise RuntimeError(msg) from exc
