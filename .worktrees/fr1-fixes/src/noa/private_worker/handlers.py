"""Task handler dispatch for the 6 RPC task types per SPEC.md §9.1.

Handlers for remember and recall delegate to MemoryStore (§13.2).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from noa.private_worker.memory_store import MemoryStore

logger = logging.getLogger(__name__)

HandlerFunc = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

# Shared in-process memory store instance.
# Persists facts as JSON files under the private-data Docker volume.
_memory_store = MemoryStore(data_dir=Path("/data/memory"))


async def _handle_remember(payload: dict[str, Any]) -> dict[str, Any]:
    """Store a fact in the private memory store per §13.2."""
    fact = payload.get("fact", "")
    category = payload.get("category", "preference")
    source_thread_id = payload.get("source_thread_id", "")
    auto_extracted = payload.get("auto_extracted", False)

    # Embedding would come from Ollama in production;
    # for now use empty placeholder
    embedding = payload.get("embedding", [])

    user_id = payload.get("user_id")

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
    """Retrieve facts from the private memory store per §13.2."""
    query_embedding = payload.get("query_embedding", [])
    n_results = payload.get("n_results", 5)
    user_id = payload.get("user_id")

    facts = _memory_store.recall(
        query_embedding=query_embedding,
        n_results=n_results,
        user_id=user_id,
    )

    return {"status": "recalled", "facts": facts}


async def _handle_rag_query(payload: dict[str, Any]) -> dict[str, Any]:
    """Query the RAG index for relevant documents."""
    return {"status": "queried", "results": []}


async def _handle_rag_ingest(payload: dict[str, Any]) -> dict[str, Any]:
    """Ingest a document into the RAG index."""
    return {"status": "ingested"}


async def _handle_summarize(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize text using the local LLM."""
    return {"status": "summarized", "summary": ""}


async def _handle_search(payload: dict[str, Any]) -> dict[str, Any]:
    """Search the private knowledge base."""
    return {"status": "searched", "results": []}


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
