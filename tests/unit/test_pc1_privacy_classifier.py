"""Tests for PC1: Configurable Privacy Classifier + Semantic Scoring.

Spec refs: SPEC.md §14.2, §14.3, §18
Phase: PC1

Covers:
- Keyword matching with built-in and custom keywords
- Semantic scoring (mocked Ollama embeddings)
- Combined OR logic (keyword OR semantic)
- Graceful fallback when Ollama is unavailable
- Settings round-trip for custom keywords (service layer)
- API schema: private_keywords accepted in PATCH /settings
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.pc1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_msg(text: str) -> dict:
    return {"role": "user", "content": text}


def _state(text: str) -> dict:
    return {"messages": [_user_msg(text)]}


# ---------------------------------------------------------------------------
# 1. Keyword matching
# ---------------------------------------------------------------------------

class TestKeywordClassification:
    """Classifier routes private messages based on keyword matching."""

    def test_builtin_keyword_triggers_private(self):
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier()
        result = clf.classify(_state("my diary entry today"))
        assert result.domain == "private"

    def test_no_keyword_returns_external(self):
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier()
        result = clf.classify(_state("what is the weather today?"))
        assert result.domain == "external"

    def test_custom_keyword_triggers_private(self):
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier(custom_keywords=["medications", "therapy"])
        result = clf.classify(_state("add medications to my list"))
        assert result.domain == "private"

    def test_custom_keyword_case_insensitive(self):
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier(custom_keywords=["MEDICATIONS"])
        result = clf.classify(_state("track my medications"))
        assert result.domain == "private"

    def test_custom_keyword_merges_with_builtins(self):
        """Custom keywords are added to built-ins, not replacing them."""
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier(custom_keywords=["meds"])
        # Built-in keyword still works
        assert clf.classify(_state("my journal")).domain == "private"
        # Custom keyword also works
        assert clf.classify(_state("update my meds")).domain == "private"

    def test_empty_custom_keywords_uses_builtins(self):
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier(custom_keywords=[])
        result = clf.classify(_state("my diary notes"))
        assert result.domain == "private"

    def test_none_custom_keywords_uses_builtins(self):
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier(custom_keywords=None)
        result = clf.classify(_state("personal files"))
        assert result.domain == "private"


# ---------------------------------------------------------------------------
# 2. Semantic scoring
# ---------------------------------------------------------------------------

class TestSemanticClassification:
    """Classifier uses Ollama embeddings for semantic private-intent detection."""

    @pytest.mark.asyncio
    async def test_high_similarity_returns_private(self):
        """Message embedding similar to private intent text → private domain."""
        from noa.privacy.classifier import PrivacyClassifier

        # reference and msg embeddings that produce high cosine similarity
        ref_vec = [1.0, 0.0, 0.0]
        msg_vec = [0.95, 0.1, 0.1]

        clf = PrivacyClassifier()

        with patch(
            "noa.privacy.classifier.OllamaClient"
        ) as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            # Reset reference cache so our mock is used
            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            result = await clf.classify_async(
                {"messages": [_user_msg("track my health data")]},
            )

        assert result.domain == "private"
        assert "semantic similarity" in result.reasoning

    @pytest.mark.asyncio
    async def test_low_similarity_returns_external(self):
        """Message embedding dissimilar to private intent text → external domain."""
        from noa.privacy.classifier import PrivacyClassifier

        # Orthogonal vectors → cosine similarity = 0
        ref_vec = [1.0, 0.0, 0.0]
        msg_vec = [0.0, 1.0, 0.0]

        clf = PrivacyClassifier()

        with patch(
            "noa.privacy.classifier.OllamaClient"
        ) as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            result = await clf.classify_async(
                {"messages": [_user_msg("search the web for news")]},
            )

        assert result.domain == "external"

    @pytest.mark.asyncio
    async def test_uses_cached_reference_embedding(self):
        """Reference embedding is fetched only once per process lifetime."""
        from noa.privacy.classifier import PrivacyClassifier, _reference_cache

        cached_ref = [1.0, 0.0, 0.0]
        _reference_cache.set(cached_ref)

        msg_vec = [0.0, 1.0, 0.0]  # orthogonal → external

        clf = PrivacyClassifier()

        with patch(
            "noa.privacy.classifier.OllamaClient"
        ) as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            # Only the message embed call — reference is from cache
            mock_client.embed.return_value = msg_vec

            result = await clf.classify_async(
                {"messages": [_user_msg("latest news")]},
            )

        # Should call embed once (for message) not twice
        assert mock_client.embed.call_count == 1
        assert result.domain == "external"

    @pytest.mark.asyncio
    async def test_semantic_threshold_configurable(self):
        """Custom threshold is respected."""
        from noa.privacy.classifier import PrivacyClassifier

        # cosine similarity ~0.6 — below default 0.7 but above 0.5
        ref_vec = [1.0, 0.0]
        msg_vec = [0.6, 0.8]  # cos similarity ≈ 0.6

        clf_strict = PrivacyClassifier(semantic_threshold=0.7)
        clf_loose = PrivacyClassifier(semantic_threshold=0.5)

        import math
        # Compute expected similarity
        dot = 0.6 * 1.0 + 0.8 * 0.0
        norm_msg = math.sqrt(0.6**2 + 0.8**2)
        norm_ref = 1.0
        expected_sim = dot / (norm_msg * norm_ref)  # ≈ 0.6

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec, ref_vec, msg_vec]

            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            result_strict = await clf_strict.classify_async(
                {"messages": [_user_msg("neutral message")]},
            )

            clf_module._reference_cache._embedding = None

            result_loose = await clf_loose.classify_async(
                {"messages": [_user_msg("neutral message")]},
            )

        # strict threshold (0.7): similarity ~0.6 → not private
        assert result_strict.domain == "external", (
            f"Expected external with strict threshold, got {result_strict.domain}"
        )
        # loose threshold (0.5): similarity ~0.6 → private
        assert result_loose.domain == "private", (
            f"Expected private with loose threshold, got {result_loose.domain}"
        )


# ---------------------------------------------------------------------------
# 3. Combined OR logic
# ---------------------------------------------------------------------------

class TestCombinedClassification:
    """Keyword OR semantic → private. Both must be absent for external."""

    @pytest.mark.asyncio
    async def test_keyword_alone_triggers_private(self):
        """Low semantic score but keyword match → private."""
        from noa.privacy.classifier import PrivacyClassifier

        ref_vec = [1.0, 0.0]
        msg_vec = [0.0, 1.0]  # orthogonal → low similarity, but keyword matches

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            result = await clf.classify_async(
                {"messages": [_user_msg("write in my diary")]},
            )

        assert result.domain == "private"
        assert "private keywords detected" in result.reasoning

    @pytest.mark.asyncio
    async def test_semantic_alone_triggers_private(self):
        """No keyword match but high semantic score → private."""
        from noa.privacy.classifier import PrivacyClassifier

        ref_vec = [1.0, 0.0]
        msg_vec = [0.99, 0.1]  # very similar to ref → high similarity

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            result = await clf.classify_async(
                {"messages": [_user_msg("show me my health records")]},
            )

        assert result.domain == "private"
        assert "semantic similarity" in result.reasoning

    @pytest.mark.asyncio
    async def test_no_keyword_no_semantic_returns_external(self):
        """Neither keyword nor semantic signal → external."""
        from noa.privacy.classifier import PrivacyClassifier

        ref_vec = [1.0, 0.0]
        msg_vec = [0.0, 1.0]  # orthogonal

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = [ref_vec, msg_vec]

            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            result = await clf.classify_async(
                {"messages": [_user_msg("latest news from CNN")]},
            )

        assert result.domain == "external"


# ---------------------------------------------------------------------------
# 4. Ollama unavailable fallback
# ---------------------------------------------------------------------------

class TestSemanticFallback:
    """When Ollama is unavailable, keyword-only classification is used."""

    @pytest.mark.asyncio
    async def test_fallback_to_keyword_on_connection_error(self):
        """ConnectError from Ollama → keyword-only, no exception raised."""
        from noa.llm.exceptions import ProviderError
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = ProviderError("Ollama unavailable")

            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            # Message has keyword → should still be private despite Ollama failure
            result = await clf.classify_async(
                {"messages": [_user_msg("my secret notes")]},
            )

        assert result.domain == "private"  # keyword matched
        # No exception raised

    @pytest.mark.asyncio
    async def test_fallback_returns_external_for_neutral_message(self):
        """Ollama down + no keyword → external (safe fallback)."""
        from noa.llm.exceptions import ProviderError
        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = ProviderError("Ollama unavailable")

            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            result = await clf.classify_async(
                {"messages": [_user_msg("search for Python tutorials")]},
            )

        assert result.domain == "external"
        # No exception raised

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        """TimeoutError from Ollama → graceful fallback."""

        from noa.privacy.classifier import PrivacyClassifier

        clf = PrivacyClassifier()

        with patch("noa.privacy.classifier.OllamaClient") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.embed.side_effect = TimeoutError("timed out")

            from noa.privacy import classifier as clf_module
            clf_module._reference_cache._embedding = None

            result = await clf.classify_async(
                {"messages": [_user_msg("neutral query")]},
            )

        # Should not raise; returns external since no keyword
        assert result.domain == "external"


# ---------------------------------------------------------------------------
# 5. Cosine similarity utility
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    """Unit tests for the cosine similarity helper."""

    def test_identical_vectors_return_1(self):
        from noa.privacy.classifier import _cosine_similarity

        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors_return_0(self):
        from noa.privacy.classifier import _cosine_similarity

        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_zero_vector_returns_0(self):
        from noa.privacy.classifier import _cosine_similarity

        assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_opposite_vectors_return_minus_1(self):
        from noa.privacy.classifier import _cosine_similarity

        result = _cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert abs(result - (-1.0)) < 1e-6


# ---------------------------------------------------------------------------
# 6. Settings round-trip for custom keywords
# ---------------------------------------------------------------------------

class TestSettingsKeywordsRoundTrip:
    """SettingsService stores and retrieves private_keywords correctly."""

    @pytest.mark.asyncio
    async def test_update_settings_stores_keywords(self):
        """Saving private_keywords encodes them as JSON in the DB."""
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()

        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = None  # no existing row
        mock_row = MagicMock()
        mock_row.private_keywords = json.dumps(["fitness", "therapy"])

        # After upsert, get_by_user_id returns the new row
        for field_name in [
            "default_model", "default_provider", "default_privacy_mode",
            "budget_daily_usd", "budget_monthly_usd", "temperature",
            "max_tokens", "anthropic_api_key", "openai_api_key",
            "google_client_id", "google_client_secret", "notion_token",
            "tavily_api_key", "ollama_base_url", "approvals_enabled",
            "max_tool_calls", "max_retries", "timeout_seconds",
            "node_models",
        ]:
            setattr(mock_row, field_name, None)

        mock_repo.get_by_user_id.side_effect = [None, mock_row]
        mock_repo.upsert.return_value = mock_row

        service = SettingsService(mock_repo)
        await service.update_settings(user_id, {"private_keywords": ["fitness", "therapy"]})

        # Verify upsert was called with JSON-encoded keywords
        call_args = mock_repo.upsert.call_args
        upserted_fields = call_args[0][1]  # positional arg
        assert "private_keywords" in upserted_fields
        stored = upserted_fields["private_keywords"]
        assert json.loads(stored) == ["fitness", "therapy"]

    @pytest.mark.asyncio
    async def test_get_settings_decodes_keywords(self):
        """Keywords stored as JSON are decoded to list on read."""
        from noa.settings.models import UserSettings
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        mock_row = MagicMock(spec=UserSettings)

        # Set all expected fields
        for field_name in [
            "default_model", "default_provider", "default_privacy_mode",
            "budget_daily_usd", "budget_monthly_usd", "temperature",
            "max_tokens", "anthropic_api_key", "openai_api_key",
            "google_client_id", "google_client_secret", "notion_token",
            "tavily_api_key", "ollama_base_url", "approvals_enabled",
            "max_tool_calls", "max_retries", "timeout_seconds",
            "node_models", "scope_overrides",
        ]:
            setattr(mock_row, field_name, None)

        mock_row.private_keywords = json.dumps(["fitness", "therapy"])

        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = mock_row

        service = SettingsService(mock_repo)

        with patch("noa.settings.service.read_system_prompt", return_value=""):
            result = await service.get_settings(user_id)

        assert result.get("private_keywords") == ["fitness", "therapy"]

    @pytest.mark.asyncio
    async def test_get_settings_returns_none_for_no_keywords(self):
        """When no keywords are stored, private_keywords is None."""
        from noa.settings.models import UserSettings
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        mock_row = MagicMock(spec=UserSettings)

        for field_name in [
            "default_model", "default_provider", "default_privacy_mode",
            "budget_daily_usd", "budget_monthly_usd", "temperature",
            "max_tokens", "anthropic_api_key", "openai_api_key",
            "google_client_id", "google_client_secret", "notion_token",
            "tavily_api_key", "ollama_base_url", "approvals_enabled",
            "max_tool_calls", "max_retries", "timeout_seconds",
            "node_models", "scope_overrides",
        ]:
            setattr(mock_row, field_name, None)

        mock_row.private_keywords = None

        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = mock_row

        service = SettingsService(mock_repo)

        with patch("noa.settings.service.read_system_prompt", return_value=""):
            result = await service.get_settings(user_id)

        assert result.get("private_keywords") is None

    @pytest.mark.asyncio
    async def test_empty_list_clears_keywords(self):
        """Saving an empty list sets private_keywords to None."""
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_row = MagicMock()
        mock_row.private_keywords = None

        for field_name in [
            "default_model", "default_provider", "default_privacy_mode",
            "budget_daily_usd", "budget_monthly_usd", "temperature",
            "max_tokens", "anthropic_api_key", "openai_api_key",
            "google_client_id", "google_client_secret", "notion_token",
            "tavily_api_key", "ollama_base_url", "approvals_enabled",
            "max_tool_calls", "max_retries", "timeout_seconds",
            "node_models",
        ]:
            setattr(mock_row, field_name, None)

        mock_repo.get_by_user_id.side_effect = [None, mock_row]
        mock_repo.upsert.return_value = mock_row

        service = SettingsService(mock_repo)
        await service.update_settings(user_id, {"private_keywords": []})

        call_args = mock_repo.upsert.call_args
        upserted_fields = call_args[0][1]
        # Empty list → None stored (no point serializing [])
        assert upserted_fields.get("private_keywords") is None


# ---------------------------------------------------------------------------
# 7. Settings API schema
# ---------------------------------------------------------------------------

class TestSettingsApiSchema:
    """UpdateSettingsRequest accepts private_keywords field."""

    def test_private_keywords_accepted_in_schema(self):
        from noa.api.v1.settings import UpdateSettingsRequest

        req = UpdateSettingsRequest(private_keywords=["fitness", "health"])
        assert req.private_keywords == ["fitness", "health"]

    def test_private_keywords_optional(self):
        from noa.api.v1.settings import UpdateSettingsRequest

        req = UpdateSettingsRequest(default_model="claude-sonnet-4-20250514")
        assert req.private_keywords is None

    def test_private_keywords_none_default(self):
        from noa.api.v1.settings import UpdateSettingsRequest

        req = UpdateSettingsRequest()
        assert req.private_keywords is None

    def test_private_keywords_in_model_dump_when_set(self):
        from noa.api.v1.settings import UpdateSettingsRequest

        req = UpdateSettingsRequest(private_keywords=["therapy"])
        updates = req.model_dump(exclude_unset=True)
        assert "private_keywords" in updates
        assert updates["private_keywords"] == ["therapy"]

    def test_private_keywords_excluded_when_not_set(self):
        """exclude_unset=True should omit private_keywords if not provided."""
        from noa.api.v1.settings import UpdateSettingsRequest

        req = UpdateSettingsRequest(default_model="gpt-4o")
        updates = req.model_dump(exclude_unset=True)
        assert "private_keywords" not in updates


# ---------------------------------------------------------------------------
# 8. Integration: classifier uses settings-derived keywords
# ---------------------------------------------------------------------------

class TestClassifierIntegration:
    """Full flow: custom keyword stored in settings → used by classifier."""

    @pytest.mark.asyncio
    async def test_full_flow_keyword_stored_and_used(self):
        """
        Integration test: settings service stores custom keywords,
        classifier uses them to route a private message.
        Uses real service + in-memory repo mock (no external DB needed).
        """
        from noa.privacy.classifier import PrivacyClassifier
        from noa.settings.models import UserSettings
        from noa.settings.service import SettingsService

        user_id = uuid.uuid4()
        stored_keywords = ["fitness", "therapy"]

        # Mock repo returns a row with our keywords
        mock_row = MagicMock(spec=UserSettings)
        for field_name in [
            "default_model", "default_provider", "default_privacy_mode",
            "budget_daily_usd", "budget_monthly_usd", "temperature",
            "max_tokens", "anthropic_api_key", "openai_api_key",
            "google_client_id", "google_client_secret", "notion_token",
            "tavily_api_key", "ollama_base_url", "approvals_enabled",
            "max_tool_calls", "max_retries", "timeout_seconds",
            "node_models", "scope_overrides",
        ]:
            setattr(mock_row, field_name, None)
        mock_row.private_keywords = json.dumps(stored_keywords)

        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = mock_row

        service = SettingsService(mock_repo)

        with patch("noa.settings.service.read_system_prompt", return_value=""):
            settings_data = await service.get_settings(user_id)

        custom_keywords = settings_data.get("private_keywords") or []
        assert custom_keywords == stored_keywords, (
            f"Expected {stored_keywords}, got {custom_keywords}"
        )

        # Now use those keywords in the classifier
        clf = PrivacyClassifier(custom_keywords=custom_keywords)

        # "therapy" is a custom keyword → should be private
        result = clf.classify({"messages": [{"role": "user", "content": "my therapy session notes"}]})
        assert result.domain == "private"

        # Neither built-in nor custom keyword → should be external
        result2 = clf.classify({"messages": [{"role": "user", "content": "search for news"}]})
        assert result2.domain == "external"
