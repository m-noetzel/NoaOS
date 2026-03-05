"""Tests for Phase TI1: Memory Tool (Remember/Recall).

Covers: remember(fact) storage, recall(query) retrieval, deduplication,
auto-extraction guardrails, fact schema, RPC integration, and limits.

Spec refs: SPEC.md §12.5, §13.2, §13.3, §19.1
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.ti1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fact(
    fact: str = "User prefers dark mode",
    category: str = "preference",
    *,
    auto_extracted: bool = False,
    status: str = "approved",
    source_thread_id: str | None = None,
) -> dict[str, Any]:
    """Create a fact dict matching the §13.2 schema."""
    return {
        "id": str(uuid.uuid4()),
        "fact": fact,
        "category": category,
        "embedding": [0.01, -0.02, 0.03],
        "created_at": "2026-03-05T10:00:00Z",
        "source_thread_id": source_thread_id or f"thread-{uuid.uuid4().hex[:8]}",
        "status": status,
        "auto_extracted": auto_extracted,
    }


# ---------------------------------------------------------------------------
# Memory Tool — remember()
# ---------------------------------------------------------------------------


class TestRemember:
    """Tests for the remember(fact) function per SPEC.md §12.5, §13.2."""

    @pytest.mark.asyncio
    async def test_remember_stores_fact_via_rpc(self):
        """remember() must send a 'remember' RPC request to the private worker.

        SPEC.md §12.5 — Memory tool accessed via RPC contract.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "stored"},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        result = await tool.remember(
            fact="User prefers dark mode",
            category="preference",
            source_thread_id="thread-abc",
        )

        mock_rpc.assert_called_once()
        call_args = mock_rpc.call_args[0][0]
        assert call_args["task_type"] == "remember"
        assert call_args["payload"]["fact"] == "User prefers dark mode"
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_remember_includes_category(self):
        """remember() must include the category tag per §13.2 schema.

        SPEC.md §13.2 — Each fact tagged with a category.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "stored"},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        await tool.remember(
            fact="Likes hiking",
            category="habit",
            source_thread_id="thread-abc",
        )

        call_args = mock_rpc.call_args[0][0]
        assert call_args["payload"]["category"] == "habit"

    @pytest.mark.asyncio
    async def test_remember_includes_idempotency_key(self):
        """remember() must include an idempotency_key per §9.1.

        SPEC.md §9.1 — idempotency_key required in every RPC request.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "stored"},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        await tool.remember(
            fact="Test fact",
            category="preference",
            source_thread_id="thread-abc",
        )

        call_args = mock_rpc.call_args[0][0]
        assert "idempotency_key" in call_args
        assert len(call_args["idempotency_key"]) > 0

    @pytest.mark.asyncio
    async def test_remember_includes_source_thread_id(self):
        """remember() must track the source thread per §13.2 schema.

        SPEC.md §13.2 — source_thread_id in fact schema.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "stored"},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        await tool.remember(
            fact="Test fact",
            category="preference",
            source_thread_id="thread-xyz",
        )

        call_args = mock_rpc.call_args[0][0]
        assert call_args["payload"]["source_thread_id"] == "thread-xyz"

    @pytest.mark.asyncio
    async def test_remember_risk_tier_is_low(self):
        """Memory remember is Low risk per §12.5.

        SPEC.md §12.5 — Memory tool risk tier is Low.
        """
        from noa.tools.memory import MemoryTool

        assert MemoryTool.risk_tier == "low"


# ---------------------------------------------------------------------------
# Memory Tool — recall()
# ---------------------------------------------------------------------------


class TestRecall:
    """Tests for the recall(query) function per SPEC.md §12.5, §13.2."""

    @pytest.mark.asyncio
    async def test_recall_sends_rpc_request(self):
        """recall() must send a 'recall' RPC request to the private worker.

        SPEC.md §12.5 — recall accessed via RPC.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {
                "answer": "",
                "facts": [_make_fact()],
            },
            "sensitivity_label": "low",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        result = await tool.recall(query="dark mode")

        mock_rpc.assert_called_once()
        call_args = mock_rpc.call_args[0][0]
        assert call_args["task_type"] == "recall"
        assert call_args["payload"]["query"] == "dark mode"

    @pytest.mark.asyncio
    async def test_recall_returns_facts(self):
        """recall() must return matching facts from the private store.

        SPEC.md §12.5 — recall returns semantic search results.
        """
        from noa.tools.memory import MemoryTool

        facts = [_make_fact(fact="User prefers dark mode")]
        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "", "facts": facts},
            "sensitivity_label": "low",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        result = await tool.recall(query="dark mode")

        assert len(result["facts"]) == 1
        assert result["facts"][0]["fact"] == "User prefers dark mode"

    @pytest.mark.asyncio
    async def test_recall_respects_n_results(self):
        """recall() must pass n_results to the RPC request.

        SPEC.md §12.5 — recall(query, n_results?).
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "", "facts": []},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        await tool.recall(query="test", n_results=10)

        call_args = mock_rpc.call_args[0][0]
        assert call_args["payload"]["n_results"] == 10

    @pytest.mark.asyncio
    async def test_recall_n_results_capped_at_20(self):
        """recall() must cap n_results at 20 per §9.1 MAX_N_RESULTS.

        SPEC.md §9.1 — n_results max 20.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "", "facts": []},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        await tool.recall(query="test", n_results=50)

        call_args = mock_rpc.call_args[0][0]
        assert call_args["payload"]["n_results"] == 20

    @pytest.mark.asyncio
    async def test_recall_default_n_results_is_5(self):
        """recall() defaults to 5 results when n_results not specified.

        SPEC.md §12.5 — recall(query, n_results?).
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "", "facts": []},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        await tool.recall(query="test")

        call_args = mock_rpc.call_args[0][0]
        assert call_args["payload"]["n_results"] == 5

    @pytest.mark.asyncio
    async def test_recall_includes_idempotency_key(self):
        """recall() must include an idempotency_key per §9.1.

        SPEC.md §9.1 — idempotency_key required.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "", "facts": []},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        await tool.recall(query="test")

        call_args = mock_rpc.call_args[0][0]
        assert "idempotency_key" in call_args


# ---------------------------------------------------------------------------
# Deduplication per §19.1
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Tests for fact deduplication per SPEC.md §19.1."""

    @pytest.mark.asyncio
    async def test_duplicate_fact_rejected(self):
        """Exact duplicate facts must be rejected per §19.1.

        SPEC.md §19.1 — Memory remember: de-duplicate by exact fact text.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "duplicate",
            "result": {"answer": "duplicate fact"},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        result = await tool.remember(
            fact="User prefers dark mode",
            category="preference",
            source_thread_id="thread-abc",
        )

        assert result["status"] == "duplicate"


# ---------------------------------------------------------------------------
# Memory Store — private-side implementation
# ---------------------------------------------------------------------------


class TestMemoryStore:
    """Tests for the private-side memory store per SPEC.md §13.2."""

    def test_store_fact_schema(self):
        """Stored facts must match the §13.2 schema.

        SPEC.md §13.2 — fact schema: id, fact, category, embedding,
        created_at, source_thread_id, status, auto_extracted.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        fact_id = store.store(
            fact="User prefers dark mode",
            category="preference",
            embedding=[0.01, -0.02],
            source_thread_id="thread-abc",
        )

        retrieved = store.get_by_id(fact_id)
        assert retrieved is not None
        required_keys = {
            "id", "fact", "category", "embedding",
            "created_at", "source_thread_id", "status",
            "auto_extracted",
        }
        assert required_keys.issubset(set(retrieved.keys()))

    def test_store_fact_default_status_approved(self):
        """Manually stored facts default to 'approved' status.

        SPEC.md §13.2 — Explicit remember -> approved.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        fact_id = store.store(
            fact="Test fact",
            category="preference",
            embedding=[0.01],
            source_thread_id="thread-abc",
        )

        retrieved = store.get_by_id(fact_id)
        assert retrieved["status"] == "approved"

    def test_store_auto_extracted_defaults_pending(self):
        """Auto-extracted facts default to 'pending' status.

        SPEC.md §13.2 — Auto-extracted facts held in pending state.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        fact_id = store.store(
            fact="Test fact",
            category="preference",
            embedding=[0.01],
            source_thread_id="thread-abc",
            auto_extracted=True,
        )

        retrieved = store.get_by_id(fact_id)
        assert retrieved["status"] == "pending"
        assert retrieved["auto_extracted"] is True

    def test_store_deduplicates_exact_match(self):
        """Exact duplicate facts must be rejected.

        SPEC.md §19.1 — De-duplicate by exact fact text match.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        id1 = store.store(
            fact="User prefers dark mode",
            category="preference",
            embedding=[0.01],
            source_thread_id="thread-abc",
        )
        id2 = store.store(
            fact="User prefers dark mode",
            category="preference",
            embedding=[0.02],
            source_thread_id="thread-def",
        )

        assert id2 is None  # Duplicate rejected

    def test_recall_semantic_search(self):
        """recall must return facts ranked by cosine similarity.

        SPEC.md §13.2 — Semantic search over stored facts.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        store.store(
            fact="User prefers dark mode",
            category="preference",
            embedding=[1.0, 0.0, 0.0],
            source_thread_id="thread-1",
        )
        store.store(
            fact="User likes hiking on weekends",
            category="habit",
            embedding=[0.0, 1.0, 0.0],
            source_thread_id="thread-2",
        )

        # Query embedding close to first fact
        results = store.recall(
            query_embedding=[0.9, 0.1, 0.0],
            n_results=5,
        )

        assert len(results) >= 1
        assert results[0]["fact"] == "User prefers dark mode"

    def test_recall_respects_n_results_limit(self):
        """recall must return at most n_results facts.

        SPEC.md §9.1 — n_results capped at 20.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        for i in range(10):
            store.store(
                fact=f"Fact number {i}",
                category="preference",
                embedding=[float(i) / 10],
                source_thread_id=f"thread-{i}",
            )

        results = store.recall(
            query_embedding=[0.5],
            n_results=3,
        )

        assert len(results) <= 3

    def test_recall_returns_only_approved_facts(self):
        """recall must only return approved facts, not pending ones.

        SPEC.md §13.2 — Pending facts require approval before use.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        store.store(
            fact="Approved fact",
            category="preference",
            embedding=[1.0, 0.0],
            source_thread_id="thread-1",
        )
        store.store(
            fact="Pending fact",
            category="preference",
            embedding=[0.9, 0.1],
            source_thread_id="thread-2",
            auto_extracted=True,
        )

        results = store.recall(
            query_embedding=[1.0, 0.0],
            n_results=10,
        )

        fact_texts = [r["fact"] for r in results]
        assert "Approved fact" in fact_texts
        assert "Pending fact" not in fact_texts

    def test_delete_fact(self):
        """User must be able to delete any fact at any time.

        SPEC.md §13.2 — Purge: immediate removal from database.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        fact_id = store.store(
            fact="To be deleted",
            category="preference",
            embedding=[0.01],
            source_thread_id="thread-abc",
        )

        deleted = store.delete(fact_id)
        assert deleted is True
        assert store.get_by_id(fact_id) is None

    def test_approve_pending_fact(self):
        """Pending facts can be approved by the user.

        SPEC.md §13.2 — User approval moves pending to approved.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        fact_id = store.store(
            fact="Auto-extracted fact",
            category="preference",
            embedding=[0.01],
            source_thread_id="thread-abc",
            auto_extracted=True,
        )

        store.update_status(fact_id, "approved")
        retrieved = store.get_by_id(fact_id)
        assert retrieved["status"] == "approved"

    def test_reject_pending_fact(self):
        """Pending facts can be rejected by the user.

        SPEC.md §13.2 — User can discard each fact.
        """
        from noa.private_worker.memory_store import MemoryStore

        store = MemoryStore()
        fact_id = store.store(
            fact="Auto-extracted fact",
            category="preference",
            embedding=[0.01],
            source_thread_id="thread-abc",
            auto_extracted=True,
        )

        store.update_status(fact_id, "rejected")
        retrieved = store.get_by_id(fact_id)
        assert retrieved["status"] == "rejected"

    def test_valid_categories(self):
        """Facts must have valid categories per §13.2.

        SPEC.md §13.2 — Categories: preference, habit,
        project context, personal info.
        """
        from noa.private_worker.memory_store import VALID_CATEGORIES

        expected = {"preference", "habit", "project_context", "personal_info"}
        assert expected == VALID_CATEGORIES


# ---------------------------------------------------------------------------
# Auto-extraction guardrails
# ---------------------------------------------------------------------------


class TestAutoExtraction:
    """Tests for auto-extraction guardrails per SPEC.md §13.2."""

    def test_auto_extraction_off_by_default(self):
        """Auto-extraction must be off by default.

        SPEC.md §13.2 — Off by default.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock()
        tool = MemoryTool(rpc_client=mock_rpc)
        assert tool.auto_extraction_enabled is False

    @pytest.mark.asyncio
    async def test_auto_extract_creates_pending_fact(self):
        """Auto-extracted facts must be created with pending status.

        SPEC.md §13.2 — Auto-extracted facts held in pending state.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "stored"},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(
            rpc_client=mock_rpc,
            auto_extraction_enabled=True,
        )
        await tool.auto_extract(
            fact="User mentioned they like coffee",
            category="preference",
            source_thread_id="thread-abc",
        )

        call_args = mock_rpc.call_args[0][0]
        assert call_args["payload"]["auto_extracted"] is True


# ---------------------------------------------------------------------------
# Privacy domain enforcement
# ---------------------------------------------------------------------------


class TestPrivacyDomain:
    """Tests for privacy domain enforcement per SPEC.md §12.5."""

    def test_memory_tool_domain_is_private(self):
        """Memory tool must be private domain only.

        SPEC.md §12.5 — Privacy: private.
        """
        from noa.tools.memory import MemoryTool

        assert MemoryTool.domain == "private"

    @pytest.mark.asyncio
    async def test_rpc_goes_through_private_worker(self):
        """All memory operations must go through the private worker RPC.

        SPEC.md §12.5 — Accessed via RPC contract.
        """
        from noa.tools.memory import MemoryTool

        mock_rpc = AsyncMock(return_value={
            "request_id": "req-1",
            "status": "success",
            "result": {"answer": "stored"},
            "sensitivity_label": "none",
        })
        tool = MemoryTool(rpc_client=mock_rpc)
        await tool.remember(
            fact="Test",
            category="preference",
            source_thread_id="thread-abc",
        )

        # Verify the RPC client was called (not a direct DB access)
        assert mock_rpc.call_count == 1


# ---------------------------------------------------------------------------
# Handler integration
# ---------------------------------------------------------------------------


class TestHandlerIntegration:
    """Tests for memory handler wiring in private_worker/handlers.py."""

    @pytest.mark.asyncio
    async def test_remember_handler_stores_fact(self):
        """The remember handler must store facts via MemoryStore.

        SPEC.md §13.2 — remember stores fact with embedding.
        """
        from noa.private_worker.handlers import get_handler

        handler = get_handler("remember")
        assert handler is not None

        result = await handler({
            "fact": "User prefers dark mode",
            "category": "preference",
            "source_thread_id": "thread-abc",
        })

        assert result["status"] in ("stored", "duplicate")

    @pytest.mark.asyncio
    async def test_recall_handler_returns_facts(self):
        """The recall handler must search and return facts.

        SPEC.md §13.2 — recall performs semantic search.
        """
        from noa.private_worker.handlers import get_handler

        handler = get_handler("recall")
        assert handler is not None

        result = await handler({
            "query": "dark mode",
            "n_results": 5,
        })

        assert "facts" in result
        assert isinstance(result["facts"], list)
