"""Tests for Privacy Router & Classification — Phase DW4.

Spec refs: SPEC.md §14.2, §14.3, §18
Phase plan: MASTER_PLAN.md Phase DW4

Tests cover: explicit user override, tool-based routing, content analysis,
fail-safe / low-confidence handling, classification logging & metrics,
and queue-and-wait behaviour when a domain is unavailable.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.dw4


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def classifier():
    """Instantiate the PrivacyClassifier."""
    from noa.privacy.classifier import PrivacyClassifier

    return PrivacyClassifier()


@pytest.fixture()
def metrics():
    """Instantiate the ClassificationMetrics tracker."""
    from noa.privacy.metrics import ClassificationMetrics

    return ClassificationMetrics()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(
    *,
    messages: list[dict] | None = None,
    privacy_mode: str | None = None,
    requested_tools: list[str] | None = None,
) -> dict:
    """Build a minimal AgentState-like dict for the router."""
    state: dict = {}
    if messages is not None:
        state["messages"] = messages
    if privacy_mode is not None:
        state["privacy_mode"] = privacy_mode
    if requested_tools is not None:
        state["requested_tools"] = requested_tools
    return state


# ---------------------------------------------------------------------------
# 1. Explicit Override — user toggle always respected (§18, §14.4)
# ---------------------------------------------------------------------------

class TestExplicitOverride:
    """User-set privacy_mode overrides all automatic classification."""

    def test_explicit_private_routes_to_private(self, classifier):
        """User sets privacy_mode='private' -> always routes to private domain."""
        state = _make_state(
            messages=[{"role": "user", "content": "What is the weather today?"}],
            privacy_mode="private",
        )
        result = classifier.classify(state)
        assert result.domain == "private"

    def test_explicit_external_routes_to_external(self, classifier):
        """User sets privacy_mode='external' -> routes to external domain."""
        state = _make_state(
            messages=[{"role": "user", "content": "Show me my diary entries"}],
            privacy_mode="external",
        )
        result = classifier.classify(state)
        assert result.domain == "external"

    def test_explicit_override_beats_auto_classification(self, classifier):
        """Explicit toggle always overrides auto-classification per §14.4."""
        # Content has private keywords but user explicitly chose external
        state = _make_state(
            messages=[{"role": "user", "content": "Read my personal journal"}],
            privacy_mode="external",
        )
        result = classifier.classify(state)
        assert result.domain == "external"
        assert result.override is True


# ---------------------------------------------------------------------------
# 2. Tool-Based Routing — tools determine domain (§18)
# ---------------------------------------------------------------------------

class TestToolBasedRouting:
    """Tool requirements determine routing when no explicit override."""

    @pytest.mark.parametrize("tool", ["calendar", "gmail", "notion", "web_search"])
    def test_external_tools_route_external(self, classifier, tool):
        """Calendar/Gmail/Notion/Search tools -> external domain per §18."""
        state = _make_state(
            messages=[{"role": "user", "content": "Do something"}],
            requested_tools=[tool],
        )
        result = classifier.classify(state)
        assert result.domain == "external"

    def test_memory_tool_routes_private(self, classifier):
        """Memory tool -> private domain per §18."""
        state = _make_state(
            messages=[{"role": "user", "content": "Remember this fact"}],
            requested_tools=["memory"],
        )
        result = classifier.classify(state)
        assert result.domain == "private"

    def test_mixed_tools_route_private(self, classifier):
        """Mixed tools (private + external) -> private (conservative) per §18."""
        state = _make_state(
            messages=[{"role": "user", "content": "Search and remember"}],
            requested_tools=["memory", "web_search"],
        )
        result = classifier.classify(state)
        assert result.domain == "private"


# ---------------------------------------------------------------------------
# 3. Content Analysis — keyword / LLM-based classification (§18)
# ---------------------------------------------------------------------------

class TestContentAnalysis:
    """Content analysis classifies messages by data sensitivity."""

    def test_personal_data_routes_private(self, classifier):
        """Personal data mentions -> private domain per §18."""
        state = _make_state(
            messages=[{"role": "user", "content": "Open my private journal notes"}],
        )
        result = classifier.classify(state)
        assert result.domain == "private"

    def test_generic_query_routes_external(self, classifier):
        """Generic queries with no private signals -> external (default) per §18."""
        state = _make_state(
            messages=[{"role": "user", "content": "What is the capital of France?"}],
        )
        result = classifier.classify(state)
        assert result.domain == "external"

    def test_ambiguous_content_uses_classifier(self, classifier):
        """Ambiguous content with no tool hints uses the classifier pipeline.

        The classifier should return a result with a confidence score,
        demonstrating that the full classification pipeline was invoked
        rather than a shortcut path.
        """
        state = _make_state(
            messages=[
                {"role": "user", "content": "Help me with that thing we discussed"},
            ],
        )
        result = classifier.classify(state)
        # Must have a confidence score (classifier was invoked)
        assert result.confidence is not None
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# 4. Fail-Safe / Low Confidence — §14.3
# ---------------------------------------------------------------------------

class TestFailSafeLowConfidence:
    """Low-confidence classifications trigger fail-safe behaviour per §14.3."""

    def test_low_confidence_private_available_forces_private(self, classifier):
        """Confidence < 0.7 + private available -> force private per §14.3."""
        state = _make_state(
            messages=[{"role": "user", "content": "Process this data for me"}],
        )
        with patch.object(
            classifier, "_raw_classify",
            return_value=MagicMock(domain="external", confidence=0.55),
        ):
            result = classifier.classify(state, private_available=True)
        assert result.domain == "private"
        assert result.confidence < 0.7

    def test_low_confidence_private_unavailable_prompts_user(self, classifier):
        """Confidence < 0.7 + private unavailable -> prompt user per §14.3."""
        state = _make_state(
            messages=[{"role": "user", "content": "Process this data for me"}],
        )
        with patch.object(
            classifier, "_raw_classify",
            return_value=MagicMock(domain="external", confidence=0.55),
        ):
            result = classifier.classify(state, private_available=False)
        assert result.requires_user_confirmation is True

    def test_high_confidence_routes_as_classified(self, classifier):
        """Confidence >= 0.7 -> route as classified per §14.3."""
        state = _make_state(
            messages=[
                {"role": "user", "content": "Search the web for Python tutorials"},
            ],
        )
        with patch.object(
            classifier, "_raw_classify",
            return_value=MagicMock(domain="external", confidence=0.9),
        ):
            result = classifier.classify(state, private_available=True)
        assert result.domain == "external"
        assert result.confidence >= 0.7

    def test_private_never_silently_routes_to_external(self, classifier):
        """Private tasks never silently fall back to external per §14.2, §18."""
        state = _make_state(
            messages=[{"role": "user", "content": "Read my secret notes"}],
        )
        with patch.object(
            classifier, "_raw_classify",
            return_value=MagicMock(domain="private", confidence=0.95),
        ):
            result = classifier.classify(state, private_available=False)
        # Must NOT silently route to external — either queue or ask user
        assert result.domain != "external" or result.requires_user_confirmation is True


# ---------------------------------------------------------------------------
# 5. Logging & Metrics — §14.3, §18
# ---------------------------------------------------------------------------

class TestLoggingAndMetrics:
    """Classification logging and metrics tracking per §14.3."""

    def test_every_classification_logged(self, classifier):
        """Every classification is logged with confidence + reasoning per §18."""
        state = _make_state(
            messages=[{"role": "user", "content": "What time is it?"}],
        )
        result = classifier.classify(state)
        # Result must contain logging-required fields
        assert result.confidence is not None
        assert result.reasoning is not None
        assert len(result.reasoning) > 0

    def test_drift_detection_false_negative_rate(self, metrics):
        """False negative rate is tracked for drift detection per §14.3."""
        # Record some classifications and their ground-truth labels
        metrics.record(predicted="external", actual="private")  # false negative
        metrics.record(predicted="external", actual="external")  # true negative
        metrics.record(predicted="private", actual="private")  # true positive
        metrics.record(predicted="external", actual="private")  # false negative

        rate = metrics.false_negative_rate()
        # 2 false negatives out of 3 actual-private -> ~0.667
        assert abs(rate - 2 / 3) < 0.01

    def test_drift_alert_on_rate_increase(self, metrics):
        """Alert when false negative rate increases > 2% per §14.3."""
        # Baseline period: 1 false negative out of 100
        for _ in range(99):
            metrics.record(predicted="private", actual="private")
        metrics.record(predicted="external", actual="private")
        metrics.snapshot_baseline()

        # New period: 4 false negatives out of 100
        for _ in range(96):
            metrics.record(predicted="private", actual="private")
        for _ in range(4):
            metrics.record(predicted="external", actual="private")

        alert = metrics.check_drift(threshold=0.02)
        assert alert is not None
        assert alert.drift_amount > 0.02


# ---------------------------------------------------------------------------
# 6. Queue-and-Wait — §14.2
# ---------------------------------------------------------------------------

class TestQueueAndWait:
    """Domain unavailability handling per §14.2."""

    def test_private_unavailable_queues_not_fallback(self, classifier):
        """Private unavailable + private task -> queue, not fallback §14.2."""
        state = _make_state(
            messages=[{"role": "user", "content": "Open my personal diary"}],
            privacy_mode="private",
        )
        result = classifier.classify(state, private_available=False)
        # Must queue — never silently route to external
        assert result.action == "queue"
        assert result.domain == "private"

    def test_external_unavailable_returns_error(self, classifier):
        """External domain unavailable + external task -> error per §14.2."""
        state = _make_state(
            messages=[{"role": "user", "content": "Search the web"}],
            privacy_mode="external",
        )
        result = classifier.classify(state, external_available=False)
        assert result.action == "error"
