"""ST5: VM1 completion & quick fixes.

Resolves W24-M4 (OllamaEmbedder), W24-M5 (source_thread_id already done),
W24-M6 (IdempotencyKey export already done), W25B-L1 (Kimi context windows).
"""

from __future__ import annotations

import pytest


class TestOllamaEmbedder:
    """W24-M4: OllamaEmbedder class exists and is importable."""

    def test_importable(self) -> None:
        from noa.memory.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()
        assert embedder.model == "nomic-embed-text"
        assert embedder.base_url == "http://localhost:11434"

    def test_custom_config(self) -> None:
        from noa.memory.embedder import OllamaEmbedder

        embedder = OllamaEmbedder(
            base_url="http://ollama:11434",
            model="all-minilm",
            timeout=10.0,
        )
        assert embedder.model == "all-minilm"
        assert embedder.base_url == "http://ollama:11434"
        assert embedder.timeout == 10.0

    @pytest.mark.asyncio
    async def test_embed_raises_on_connection_error(self) -> None:
        from noa.memory.embedder import OllamaEmbedder

        embedder = OllamaEmbedder(base_url="http://localhost:1")
        with pytest.raises(RuntimeError, match="Ollama embed request failed"):
            await embedder.embed("test text")


class TestIdempotencyKeyExport:
    """W24-M6: IdempotencyKey importable from noa.db.models."""

    def test_importable_from_models(self) -> None:
        from noa.db.models import IdempotencyKey

        assert IdempotencyKey is not None


class TestSourceThreadId:
    """W24-M5: source_thread_id is wired through memory tool."""

    def test_memory_tool_accept_source_thread_id(self) -> None:
        import inspect

        from noa.tools.memory import MemoryTool

        sig = inspect.signature(MemoryTool.remember)
        assert "source_thread_id" in sig.parameters

    def test_rag_ingest_accepts_source_thread_id(self) -> None:
        import inspect

        from noa.private_worker.handlers import _handle_rag_ingest

        source = inspect.getsource(_handle_rag_ingest)
        assert "source_thread_id" in source


class TestKimiContextWindows:
    """W25B-L1: Kimi models have context window entries."""

    def test_kimi_k2_in_context_windows(self) -> None:
        from noa.orchestrator.token_budget import MODEL_CONTEXT_WINDOWS

        assert "kimi-k2" in MODEL_CONTEXT_WINDOWS
        assert MODEL_CONTEXT_WINDOWS["kimi-k2"] == 131072

    def test_moonshot_v1_128k_in_context_windows(self) -> None:
        from noa.orchestrator.token_budget import MODEL_CONTEXT_WINDOWS

        assert "moonshot-v1-128k" in MODEL_CONTEXT_WINDOWS
        assert MODEL_CONTEXT_WINDOWS["moonshot-v1-128k"] == 131072

    def test_get_context_limit_kimi(self) -> None:
        from noa.orchestrator.token_budget import get_context_limit

        assert get_context_limit("kimi-k2") == 131072
        assert get_context_limit("moonshot/moonshot-v1-128k") == 131072
