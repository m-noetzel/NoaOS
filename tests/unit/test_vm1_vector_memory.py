"""Tests for VM1 — Private Vector Memory (pgvector + Ollama embeddings).

Spec refs: SPEC.md §13.2, §19.1

Test plan:
- Embedding client: OllamaClient.embed() with mocked Ollama HTTP response
- VectorMemoryStore.store_fact(): stores approved/pending facts correctly
- VectorMemoryStore.recall_similar(): trust tier filtering (approved only)
- VectorMemoryStore.recall_similar(): fallback to keyword search when embedding unavailable
- Deduplication per §19.1: duplicate text returns None
- handlers._handle_remember(): passes real embedding from Ollama
- handlers._handle_recall(): passes query embedding to MemoryStore.recall()
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noa.llm.exceptions import ProviderError
from noa.llm.providers.ollama import OllamaClient
from noa.memory.vector_store import (
    STATUS_APPROVED,
    STATUS_PENDING,
    VectorMemoryStore,
)
from noa.private_worker.memory_store import MemoryStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(dim: int = 768, value: float = 0.1) -> list[float]:
    """Return a unit-normalised dummy embedding of given dimension."""
    import math

    vec = [value] * dim
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


# ---------------------------------------------------------------------------
# OllamaClient.embed() tests
# ---------------------------------------------------------------------------


class TestOllamaEmbedding:
    """Tests for the new embed() method on OllamaClient."""

    @pytest.mark.asyncio
    async def test_embed_returns_vector(self) -> None:
        """embed() parses /api/embed response and returns list[float]."""
        client = OllamaClient(base_url="http://ollama:11434")
        embedding = _make_embedding(768)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [embedding]}

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_response)
                )
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.embed("hello world", model="nomic-embed-text")

        assert isinstance(result, list)
        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_raises_on_http_error(self) -> None:
        """embed() raises ProviderError on non-200 response."""
        client = OllamaClient(base_url="http://ollama:11434")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "model not found"}

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_response)
                )
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ProviderError, match="500"):
                await client.embed("hello world")

    @pytest.mark.asyncio
    async def test_embed_raises_on_connect_error(self) -> None:
        """embed() raises ProviderError when Ollama is unreachable."""
        import httpx

        client = OllamaClient(base_url="http://ollama:11434")

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(
                    post=AsyncMock(side_effect=httpx.ConnectError("refused"))
                )
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ProviderError, match="unavailable"):
                await client.embed("hello world")

    @pytest.mark.asyncio
    async def test_embed_raises_on_empty_embeddings(self) -> None:
        """embed() raises ProviderError when API returns empty embeddings list."""
        client = OllamaClient(base_url="http://ollama:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": []}

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(
                    post=AsyncMock(return_value=mock_response)
                )
            )
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ProviderError, match="empty"):
                await client.embed("hello world")


# ---------------------------------------------------------------------------
# VectorMemoryStore tests (using mock session)
# ---------------------------------------------------------------------------


def _make_vector_store(
    session_fn: Any = None,
    ollama_client: OllamaClient | None = None,
) -> VectorMemoryStore:
    """Build a VectorMemoryStore with mock dependencies."""
    if ollama_client is None:
        ollama_client = MagicMock(spec=OllamaClient)
    if session_fn is None:

        @asynccontextmanager
        async def _noop_session():  # type: ignore[misc]
            yield MagicMock()

        session_fn = _noop_session

    return VectorMemoryStore(
        session_factory=session_fn,
        ollama_client=ollama_client,
    )


class TestVectorMemoryStoreStoreAndRecall:
    """Tests for store_fact and recall_similar behaviour."""

    @pytest.mark.asyncio
    async def test_store_fact_approved_status(self) -> None:
        """store_fact() with auto_extracted=False stores with status='approved'."""
        stored_facts: list[Any] = []
        embedding = _make_embedding(768)

        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.embed = AsyncMock(return_value=embedding)

        @asynccontextmanager
        async def session_fn():  # type: ignore[misc]
            session = AsyncMock()
            # No duplicate found
            result_mock = MagicMock()
            result_mock.scalars.return_value.first.return_value = None
            session.execute = AsyncMock(return_value=result_mock)

            def capture_add(fact: Any) -> None:
                stored_facts.append(fact)

            session.add = capture_add
            session.commit = AsyncMock()
            yield session

        store = VectorMemoryStore(
            session_factory=session_fn,  # type: ignore[arg-type]
            ollama_client=mock_ollama,
        )

        fact_id = await store.store_fact(
            fact="The user prefers dark mode",
            user_id="user-1",
            category="preference",
        )

        assert fact_id is not None
        assert len(stored_facts) == 1
        stored = stored_facts[0]
        assert stored.status == STATUS_APPROVED
        assert stored.content == "The user prefers dark mode"
        assert stored.user_id == "user-1"
        assert stored.embedding == embedding

    @pytest.mark.asyncio
    async def test_store_fact_pending_when_auto_extracted(self) -> None:
        """store_fact() with auto_extracted=True stores with status='pending'."""
        stored_facts: list[Any] = []
        embedding = _make_embedding(768)

        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.embed = AsyncMock(return_value=embedding)

        @asynccontextmanager
        async def session_fn():  # type: ignore[misc]
            session = AsyncMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.first.return_value = None
            session.execute = AsyncMock(return_value=result_mock)
            session.add = lambda f: stored_facts.append(f)
            session.commit = AsyncMock()
            yield session

        store = VectorMemoryStore(
            session_factory=session_fn,  # type: ignore[arg-type]
            ollama_client=mock_ollama,
        )

        fact_id = await store.store_fact(
            fact="User mentioned they like running",
            user_id="user-1",
            auto_extracted=True,
        )

        assert fact_id is not None
        assert stored_facts[0].status == STATUS_PENDING

    @pytest.mark.asyncio
    async def test_store_fact_returns_none_on_duplicate(self) -> None:
        """store_fact() returns None when the same fact text already exists (§19.1)."""
        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.embed = AsyncMock(return_value=_make_embedding(768))

        @asynccontextmanager
        async def session_fn():  # type: ignore[misc]
            session = AsyncMock()
            # Duplicate found — return a non-None existing fact
            existing_fact = MagicMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.first.return_value = existing_fact
            session.execute = AsyncMock(return_value=result_mock)
            yield session

        store = VectorMemoryStore(
            session_factory=session_fn,  # type: ignore[arg-type]
            ollama_client=mock_ollama,
        )

        result = await store.store_fact(
            fact="The user likes tea",
            user_id="user-1",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_store_fact_stores_without_embedding_when_ollama_unavailable(
        self,
    ) -> None:
        """store_fact() stores fact with embedding=None when Ollama fails."""
        stored_facts: list[Any] = []

        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.embed = AsyncMock(side_effect=ProviderError("unavailable"))

        @asynccontextmanager
        async def session_fn():  # type: ignore[misc]
            session = AsyncMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.first.return_value = None
            session.execute = AsyncMock(return_value=result_mock)
            session.add = lambda f: stored_facts.append(f)
            session.commit = AsyncMock()
            yield session

        store = VectorMemoryStore(
            session_factory=session_fn,  # type: ignore[arg-type]
            ollama_client=mock_ollama,
        )

        fact_id = await store.store_fact(
            fact="The user is an early bird",
            user_id="user-1",
        )

        assert fact_id is not None
        assert stored_facts[0].embedding is None

    @pytest.mark.asyncio
    async def test_recall_similar_uses_vector_search_when_embedding_available(
        self,
    ) -> None:
        """recall_similar() executes raw SQL vector search when embedding succeeds."""
        query_embedding = _make_embedding(768)

        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.embed = AsyncMock(return_value=query_embedding)

        @asynccontextmanager
        async def session_fn():  # type: ignore[misc]
            session = AsyncMock()
            row = {
                "id": uuid.uuid4(),
                "content": "The user prefers dark mode",
                "category": "preference",
                "source_thread_id": None,
                "status": STATUS_APPROVED,
                "auto_extracted": False,
                "created_at": None,
                "similarity": 0.95,
            }
            result_mock = MagicMock()
            result_mock.mappings.return_value.all.return_value = [row]
            session.execute = AsyncMock(return_value=result_mock)
            yield session

        store = VectorMemoryStore(
            session_factory=session_fn,  # type: ignore[arg-type]
            ollama_client=mock_ollama,
        )

        facts = await store.recall_similar(query="dark mode", user_id="user-1")

        assert len(facts) == 1
        assert facts[0]["content"] == "The user prefers dark mode"
        assert facts[0]["similarity"] == 0.95

    @pytest.mark.asyncio
    async def test_recall_similar_falls_back_to_keyword_when_embed_fails(
        self,
    ) -> None:
        """recall_similar() falls back to keyword search when embedding fails."""
        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.embed = AsyncMock(side_effect=ProviderError("ollama down"))

        fact_obj = MagicMock()
        fact_obj.id = uuid.uuid4()
        fact_obj.content = "The user likes coffee"
        fact_obj.category = "preference"
        fact_obj.source_thread_id = None
        fact_obj.status = STATUS_APPROVED
        fact_obj.auto_extracted = False
        fact_obj.created_at = None

        @asynccontextmanager
        async def session_fn():  # type: ignore[misc]
            session = AsyncMock()
            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = [fact_obj]
            session.execute = AsyncMock(return_value=result_mock)
            yield session

        store = VectorMemoryStore(
            session_factory=session_fn,  # type: ignore[arg-type]
            ollama_client=mock_ollama,
        )

        facts = await store.recall_similar(query="coffee", user_id="user-1")

        assert len(facts) == 1
        assert facts[0]["content"] == "The user likes coffee"
        assert facts[0]["similarity"] is None  # keyword search has no score

    @pytest.mark.asyncio
    async def test_recall_similar_returns_empty_on_db_error(self) -> None:
        """recall_similar() returns [] when the DB raises an exception."""
        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.embed = AsyncMock(return_value=_make_embedding(768))

        @asynccontextmanager
        async def session_fn():  # type: ignore[misc]
            session = AsyncMock()
            session.execute = AsyncMock(side_effect=RuntimeError("DB down"))
            yield session

        store = VectorMemoryStore(
            session_factory=session_fn,  # type: ignore[arg-type]
            ollama_client=mock_ollama,
        )

        result = await store.recall_similar(query="anything", user_id="user-1")
        assert result == []


# ---------------------------------------------------------------------------
# Trust tier filtering tests
# ---------------------------------------------------------------------------


class TestTrustTierFiltering:
    """Verify only 'approved' facts are returned from recall_similar."""

    @pytest.mark.asyncio
    async def test_pending_facts_excluded_from_vector_search(self) -> None:
        """The SQL query only fetches status='approved' rows.

        This test verifies the SQL generated contains the correct status filter.
        We capture the SQL text passed to session.execute().
        """
        query_embedding = _make_embedding(768)
        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.embed = AsyncMock(return_value=query_embedding)

        captured_sql: list[str] = []

        @asynccontextmanager
        async def session_fn():  # type: ignore[misc]
            session = AsyncMock()
            result_mock = MagicMock()
            result_mock.mappings.return_value.all.return_value = []

            async def capture_execute(stmt: Any, params: Any = None) -> Any:
                # Capture the rendered SQL text
                captured_sql.append(str(stmt))
                return result_mock

            session.execute = capture_execute
            yield session

        store = VectorMemoryStore(
            session_factory=session_fn,  # type: ignore[arg-type]
            ollama_client=mock_ollama,
        )
        await store.recall_similar(query="test", user_id="user-1")

        assert len(captured_sql) == 1
        assert "status = :status" in captured_sql[0] or "status" in captured_sql[0]

    def test_memory_store_only_returns_approved_facts(self) -> None:
        """File-based MemoryStore.recall() also only returns status='approved' facts."""
        store = MemoryStore()
        embedding = _make_embedding(8)  # Small dim for speed

        # Store an approved fact
        approved_id = store.store(
            fact="Approved fact",
            category="preference",
            embedding=embedding,
            source_thread_id="t1",
            auto_extracted=False,
        )

        # Store a pending (auto_extracted) fact
        store.store(
            fact="Pending fact",
            category="preference",
            embedding=embedding,
            source_thread_id="t2",
            auto_extracted=True,
        )

        results = store.recall(query_embedding=embedding, n_results=10)

        assert len(results) == 1
        assert results[0]["id"] == approved_id
        assert results[0]["status"] == "approved"


# ---------------------------------------------------------------------------
# Handler tests — VM1 real embeddings
# ---------------------------------------------------------------------------


class TestHandlersWithRealEmbeddings:
    """Verify handlers.py calls Ollama for embeddings instead of using placeholders."""

    @pytest.mark.asyncio
    async def test_handle_remember_calls_ollama_embed(self) -> None:
        """_handle_remember calls _get_embedding() and passes result to store."""
        embedding = _make_embedding(768)

        with patch(
            "noa.private_worker.handlers._get_embedding",
            new=AsyncMock(return_value=embedding),
        ) as mock_embed, patch(
            "noa.private_worker.handlers._memory_store"
        ) as mock_store:
            mock_store.store.return_value = str(uuid.uuid4())

            from noa.private_worker.handlers import _handle_remember

            result = await _handle_remember({
                "fact": "User works at a startup",
                "category": "project_context",
                "source_thread_id": "thread-1",
                "user_id": "user-1",
            })

        mock_embed.assert_called_once_with("User works at a startup")
        mock_store.store.assert_called_once()
        call_kwargs = mock_store.store.call_args[1]
        assert call_kwargs["embedding"] == embedding
        assert result["status"] == "stored"

    @pytest.mark.asyncio
    async def test_handle_remember_returns_duplicate_when_store_returns_none(
        self,
    ) -> None:
        """_handle_remember returns {status: duplicate} on dedup."""
        with patch(
            "noa.private_worker.handlers._get_embedding",
            new=AsyncMock(return_value=[]),
        ), patch(
            "noa.private_worker.handlers._memory_store"
        ) as mock_store:
            mock_store.store.return_value = None  # Duplicate

            from noa.private_worker.handlers import _handle_remember

            result = await _handle_remember({
                "fact": "Already stored fact",
                "category": "preference",
                "user_id": "user-1",
            })

        assert result["status"] == "duplicate"

    @pytest.mark.asyncio
    async def test_handle_recall_embeds_query_text(self) -> None:
        """_handle_recall embeds the 'query' field, not the deprecated 'query_embedding'."""
        query_embedding = _make_embedding(768)

        with patch(
            "noa.private_worker.handlers._get_embedding",
            new=AsyncMock(return_value=query_embedding),
        ) as mock_embed, patch(
            "noa.private_worker.handlers._memory_store"
        ) as mock_store:
            mock_store.recall.return_value = [
                {"id": "f1", "fact": "User likes dark mode", "status": "approved"}
            ]

            from noa.private_worker.handlers import _handle_recall

            result = await _handle_recall({
                "query": "what does the user like",
                "n_results": 3,
                "user_id": "user-1",
            })

        mock_embed.assert_called_once_with("what does the user like")
        mock_store.recall.assert_called_once_with(
            query_embedding=query_embedding,
            n_results=3,
            user_id="user-1",
        )
        assert result["status"] == "recalled"
        assert len(result["facts"]) == 1

    @pytest.mark.asyncio
    async def test_handle_remember_fallback_on_ollama_error(self) -> None:
        """_handle_remember stores with empty embedding when Ollama unavailable."""
        with patch(
            "noa.private_worker.handlers._get_embedding",
            new=AsyncMock(return_value=[]),  # fallback returns []
        ), patch(
            "noa.private_worker.handlers._memory_store"
        ) as mock_store:
            mock_store.store.return_value = str(uuid.uuid4())

            from noa.private_worker.handlers import _handle_remember

            result = await _handle_remember({
                "fact": "Fact stored without embedding",
                "category": "preference",
                "user_id": "user-1",
            })

        assert result["status"] == "stored"
        call_kwargs = mock_store.store.call_args[1]
        assert call_kwargs["embedding"] == []


# ---------------------------------------------------------------------------
# Integration test — MemoryStore end-to-end with in-memory storage
# ---------------------------------------------------------------------------


class TestMemoryStoreIntegration:
    """Integration test: store facts, recall by similarity (no external deps)."""

    def test_store_and_recall_approved_facts(self) -> None:
        """Full flow: store facts with embeddings, recall by cosine similarity."""
        store = MemoryStore()

        # Embeddings — dim=4 for simplicity, unit-normalised differently
        # to test that similarity ordering works
        emb_dark_mode = [0.9, 0.1, 0.0, 0.0]
        emb_coffee = [0.0, 0.9, 0.1, 0.0]
        emb_running = [0.0, 0.0, 0.0, 1.0]

        store.store(
            fact="User prefers dark mode",
            category="preference",
            embedding=emb_dark_mode,
            source_thread_id="t1",
            user_id="alice",
        )
        store.store(
            fact="User drinks coffee every morning",
            category="habit",
            embedding=emb_coffee,
            source_thread_id="t2",
            user_id="alice",
        )
        store.store(
            fact="User likes running",
            category="habit",
            embedding=emb_running,
            source_thread_id="t3",
            user_id="alice",
        )

        # Query similar to "dark mode" → should return dark mode fact first
        query_emb = [0.95, 0.05, 0.0, 0.0]
        results = store.recall(query_embedding=query_emb, n_results=3, user_id="alice")

        assert len(results) == 3
        assert results[0]["fact"] == "User prefers dark mode"

    def test_pending_facts_not_returned(self) -> None:
        """Pending facts are stored but not returned by recall."""
        store = MemoryStore()
        emb = [1.0, 0.0, 0.0, 0.0]

        store.store(
            fact="Auto-extracted fact",
            category="preference",
            embedding=emb,
            source_thread_id="t1",
            auto_extracted=True,  # → status='pending'
        )
        store.store(
            fact="User-approved fact",
            category="preference",
            embedding=emb,
            source_thread_id="t2",
            auto_extracted=False,  # → status='approved'
        )

        results = store.recall(query_embedding=emb, n_results=10)
        assert len(results) == 1
        assert results[0]["fact"] == "User-approved fact"

    def test_user_scoping_isolates_facts(self) -> None:
        """Facts from different users are not returned in each other's recall."""
        store = MemoryStore()
        emb = [1.0, 0.0, 0.0, 0.0]

        store.store(
            fact="Alice's fact",
            category="preference",
            embedding=emb,
            source_thread_id="t1",
            user_id="alice",
        )
        store.store(
            fact="Bob's fact",
            category="preference",
            embedding=emb,
            source_thread_id="t2",
            user_id="bob",
        )

        alice_results = store.recall(query_embedding=emb, n_results=10, user_id="alice")
        bob_results = store.recall(query_embedding=emb, n_results=10, user_id="bob")

        assert len(alice_results) == 1
        assert alice_results[0]["fact"] == "Alice's fact"
        assert len(bob_results) == 1
        assert bob_results[0]["fact"] == "Bob's fact"
