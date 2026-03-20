"""Task handler dispatch for the 6 RPC task types per SPEC.md §9.1.

Handlers for remember and recall delegate to MemoryStore (§13.2).
VM1: Real Ollama embeddings via nomic-embed-text (768-dim).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from noa.llm.providers.ollama import OllamaClient
from noa.private_worker.memory_store import MemoryStore

logger = logging.getLogger(__name__)

HandlerFunc = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

# Shared in-process memory store instance.
# Persists facts as JSON files under the private-data Docker volume.
_memory_store = MemoryStore(data_dir=Path("/data/memory"))

# Ollama client for real embeddings (VM1).
# The private worker runs on noa-internal which can reach the ollama service.
_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
_ollama_client = OllamaClient(base_url=_OLLAMA_BASE_URL)


async def _get_embedding(text: str) -> list[float]:
    """Get embedding vector from Ollama, falling back to empty list on error."""
    from noa.llm.exceptions import ProviderError  # noqa: PLC0415

    try:
        return await _ollama_client.embed(text, model=_EMBED_MODEL)
    except ProviderError as exc:
        logger.warning(
            "vm1_embed_fallback: ollama unavailable, using empty embedding: %s", exc
        )
        return []


async def _handle_remember(payload: dict[str, Any]) -> dict[str, Any]:
    """Store a fact in the private memory store per §13.2.

    VM1: generates real Ollama embedding for the fact text.
    Falls back to empty embedding if Ollama unavailable.
    """
    fact = payload.get("fact", "")
    category = payload.get("category", "preference")
    source_thread_id = payload.get("source_thread_id", "")
    auto_extracted = payload.get("auto_extracted", False)
    user_id = payload.get("user_id")

    # VM1: Use real Ollama embedding; fall back to empty vector on error
    embedding = await _get_embedding(fact)

    fact_id = _memory_store.store(
        fact=fact,
        category=category,
        embedding=embedding,
        source_thread_id=source_thread_id,
        auto_extracted=auto_extracted,
        user_id=user_id,
    )

    if fact_id is None:
        return {"status": "duplicate"}

    return {"status": "stored", "fact_id": fact_id}


async def _handle_recall(payload: dict[str, Any]) -> dict[str, Any]:
    """Retrieve facts from the private memory store per §13.2.

    VM1: generates real Ollama embedding for the query and uses
    cosine similarity search. Falls back to empty vector (returns
    all approved facts sorted by creation order) on error.
    """
    query = payload.get("query", "")
    n_results = payload.get("n_results", 5)
    user_id = payload.get("user_id")

    # VM1: Embed the query for vector search
    query_embedding = await _get_embedding(query)

    facts = _memory_store.recall(
        query_embedding=query_embedding,
        n_results=n_results,
        user_id=user_id,
    )

    return {"status": "recalled", "facts": facts}


async def _handle_rag_query(payload: dict[str, Any]) -> dict[str, Any]:
    """Query the RAG index — cosine similarity search over stored facts."""
    query = payload.get("query", "")
    n_results = payload.get("n_results", 5)
    user_id = payload.get("user_id")
    if not query:
        return {"status": "queried", "results": []}

    query_embedding = await _get_embedding(query)
    facts = _memory_store.recall(
        query_embedding=query_embedding,
        n_results=n_results,
        user_id=user_id,
    )
    return {"status": "queried", "results": facts}


async def _handle_rag_ingest(payload: dict[str, Any]) -> dict[str, Any]:
    """Ingest a document into memory with embedding."""
    content = payload.get("content", "")
    category = payload.get("category", "document")
    user_id = payload.get("user_id")
    if not content:
        return {"status": "error", "message": "No content provided"}

    embedding = await _get_embedding(content)
    fact_id = _memory_store.store(
        fact=content,
        category=category,
        embedding=embedding,
        source_thread_id=payload.get("source_thread_id", ""),
        user_id=user_id,
    )
    if fact_id is None:
        return {"status": "duplicate"}
    return {"status": "ingested", "fact_id": fact_id}


async def _handle_summarize(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize text using the local Ollama LLM."""
    text = payload.get("text", "")
    if not text:
        return {"status": "error", "message": "No text provided"}

    try:
        result = await _ollama_client.complete(
            messages=[{
                "role": "user",
                "content": f"Summarize the following text concisely:\n\n{text}",
            }],
            model=os.getenv("OLLAMA_CHAT_MODEL", "llama3.2"),
        )
        summary = result.get("content", "") if isinstance(result, dict) else str(result)
        return {"status": "summarized", "summary": summary}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Summarize failed: %s", exc)
        return {"status": "error", "message": str(exc)}


async def _handle_search(payload: dict[str, Any]) -> dict[str, Any]:
    """Search the private knowledge base via vector similarity."""
    query = payload.get("query", "")
    n_results = payload.get("n_results", 10)
    user_id = payload.get("user_id")
    if not query:
        return {"status": "searched", "results": []}

    query_embedding = await _get_embedding(query)
    facts = _memory_store.recall(
        query_embedding=query_embedding,
        n_results=n_results,
        user_id=user_id,
    )
    return {"status": "searched", "results": facts}


_HANDLER_MAP: dict[str, HandlerFunc] = {
    "remember": _handle_remember,
    "recall": _handle_recall,
    "rag_query": _handle_rag_query,
    "rag_ingest": _handle_rag_ingest,
    "summarize": _handle_summarize,
    "search": _handle_search,
}


def get_handler(task_type: str) -> HandlerFunc | None:
    """Return the handler function for a task type, or None if unknown."""
    return _HANDLER_MAP.get(task_type)
