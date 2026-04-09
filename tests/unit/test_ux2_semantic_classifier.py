"""Tests for UX2: Privacy Classifier Semantic Scoring.

Phase: UX2
Spec refs: SPEC.md §14.2, §14.3, §18 — RV-M2

This phase augments the keyword classifier with cosine similarity via
nomic-embed-text (Ollama). The key user-visible improvement: phrases like
"draft my resignation letter" that contain no private keywords are caught
by semantic similarity to the private-intent reference embedding.

Test plan:
- Happy path: "draft my resignation letter" → private via semantic scoring
- Happy path: keyword-only detection still works independently
- Negative path: Ollama unavailable → graceful keyword-only fallback
- Negative path: low semantic similarity + no keyword → external
- Integration: OR logic — keyword alone triggers private, semantic alone triggers private
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.ux2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_msg(text: str) -> dict:
    return {"role": "user", "content": text}


def _state(text: str) -> dict:
    return {"messages": [_user_msg(text)]}


# ---------------------------------------------------------------------------
# 1. Semantic scoring catches private intent without keywords
# ---------------------------------------------------------------------------

class TestSemanticScoring:
    """Semantic scoring catches private intent that keywords miss."""

    @pytest.mark.asyncio
    async def test_resignation_letter_detected_as_private(self):
        """'draft my resignation letter' has no private keywords but is private intent.

        The user is writing something personal and sensitive — it should route
        to the private domain via semantic similarity, not keyword matching.
        """
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        # Simulate high cosine similarity: resignation letter → private intent
        # Use nearly identical vectors to produce cos_sim ≈ 0.999
        ref_vec = [0.8, 0.6, 0.0]   # reference private-intent embedding
        msg_vec = [0.79, 0.61, 0.0]  # very close → high cosine similarity

        clf = PrivacyClassifier(semantic_threshold=0.7)

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            # Clear reference cache so our mock embedding is fetched
            _reference_cache._embedding = None

            result = await clf.classify_async(
                _state("draft my resignation letter"),
            )

        assert result.domain == "private", (
            f"Expected 'private' for resignation letter, got '{result.domain}'. "
            "Semantic scoring should detect private personal intent without keywords."
        )
        assert "semantic similarity" in result.reasoning, (
            f"Reasoning should mention semantic similarity. Got: {result.reasoning!r}"
        )

    @pytest.mark.asyncio
    async def test_keep_this_between_us_detected_as_private(self):
        """'keep this between us' has no private keywords but implies confidentiality."""
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        # High similarity: implies confidential/private intent
        ref_vec = [1.0, 0.0, 0.0]
        msg_vec = [0.95, 0.2, 0.0]  # cos_sim ≈ 0.98

        clf = PrivacyClassifier(semantic_threshold=0.7)

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            _reference_cache._embedding = None

            result = await clf.classify_async(
                _state("write something for just me, keep this between us"),
            )

        assert result.domain == "private"
        assert "semantic similarity" in result.reasoning

    @pytest.mark.asyncio
    async def test_public_query_not_classified_private(self):
        """A clearly public query stays external even with semantic scoring."""
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        # Orthogonal vectors → cosine similarity = 0 (completely unrelated)
        ref_vec = [1.0, 0.0]
        msg_vec = [0.0, 1.0]

        clf = PrivacyClassifier(semantic_threshold=0.7)

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            _reference_cache._embedding = None

            result = await clf.classify_async(
                _state("what is the capital of France?"),
            )

        assert result.domain == "external", (
            f"Public query should route to external, got '{result.domain}'"
        )


# ---------------------------------------------------------------------------
# 2. Keyword override — always works
# ---------------------------------------------------------------------------

class TestKeywordOverride:
    """Explicit keywords always trigger private classification, regardless of embeddings."""

    def test_builtin_keyword_private_sync(self):
        """Synchronous classify() uses keyword matching — no Ollama needed."""
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier()
        result = clf.classify(_state("write in my diary"))
        assert result.domain == "private"
        assert "private keywords detected" in result.reasoning

    def test_custom_keyword_private_sync(self):
        """User-configured custom keywords trigger private via sync classify()."""
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier(custom_keywords=["resignation"])
        result = clf.classify(_state("draft my resignation letter"))
        assert result.domain == "private"
        assert "private keywords detected" in result.reasoning

    @pytest.mark.asyncio
    async def test_keyword_triggers_private_when_semantic_low(self):
        """Keyword match is sufficient even if semantic score is below threshold (OR logic)."""
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        # Orthogonal vectors → zero semantic similarity
        ref_vec = [1.0, 0.0]
        msg_vec = [0.0, 1.0]

        clf = PrivacyClassifier(semantic_threshold=0.7)

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            _reference_cache._embedding = None

            # "secret" is a built-in keyword
            result = await clf.classify_async(
                _state("my secret project notes"),
            )

        assert result.domain == "private"
        assert "private keywords detected" in result.reasoning


# ---------------------------------------------------------------------------
# 3. Graceful fallback when Ollama unavailable
# ---------------------------------------------------------------------------

class TestOllamaFallback:
    """When Ollama is unavailable, classifier falls back to keyword-only, no exception."""

    @pytest.mark.asyncio
    async def test_ollama_unavailable_falls_back_to_keyword_private(self):
        """Connection error → keyword matching used; private keyword → private."""
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = ConnectionError("Ollama not reachable")

            _reference_cache._embedding = None

            result = await clf.classify_async(
                _state("my personal diary entry"),
            )

        # Should not raise; "diary" is a built-in keyword → private
        assert result.domain == "private"
        assert result.action != "error"

    @pytest.mark.asyncio
    async def test_ollama_unavailable_falls_back_to_keyword_external(self):
        """Connection error + no keyword → external (safe fallback, not error)."""
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = ConnectionError("Ollama not reachable")

            _reference_cache._embedding = None

            result = await clf.classify_async(
                _state("draft my resignation letter"),
            )

        # No keyword match, Ollama down → external (no crash)
        assert result.domain == "external"
        assert result.action != "error"

    @pytest.mark.asyncio
    async def test_ollama_timeout_no_exception_raised(self):
        """TimeoutError during embed → graceful fallback, no exception propagates."""
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = TimeoutError("embed timed out")

            _reference_cache._embedding = None

            # Should not raise even though Ollama is timing out
            result = await clf.classify_async(
                _state("what's the weather?"),
            )

        assert result.domain == "external"

    @pytest.mark.asyncio
    async def test_ollama_unavailable_resignation_letter_no_keyword(self):
        """Critical case: Ollama down + no keyword → external (not a crash)."""
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = RuntimeError("Ollama service unavailable")

            _reference_cache._embedding = None

            result = await clf.classify_async(
                _state("draft my resignation letter"),
            )

        # Without semantic scoring and no keyword, falls back to external
        # This is documented behavior: semantic scoring is best-effort
        assert result.domain == "external", (
            "Without Ollama and without keywords, should fall back to external "
            "(documented best-effort behavior — not a crash)."
        )
        # No exception raised
