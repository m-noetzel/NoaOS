"""Privacy classifier — routes requests to private or external domain.

Spec refs: SPEC.md §14.2, §14.3, §18

Routing priority (highest to lowest):
1. Explicit user override (privacy_mode in state)
2. Tool-based routing
3. Content analysis (keyword-based + semantic)
4. Low-confidence fail-safe
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from noa.llm.providers.ollama import OllamaClient

logger = logging.getLogger(__name__)

# Built-in keywords that signal private / personal data access.
_BUILTIN_PRIVATE_KEYWORDS: frozenset[str] = frozenset(
    [
        "journal",
        "diary",
        "private",
        "personal",
        "my notes",
        "my files",
        "secret",
        "password",
        "confidential",
    ]
)

# Tools that belong to external domain.
_EXTERNAL_TOOLS: frozenset[str] = frozenset(
    ["calendar", "gmail", "notion", "web_search"]
)

# Tools that belong to private domain.
_PRIVATE_TOOLS: frozenset[str] = frozenset(["memory"])

# Reference text for semantic "private intent" embedding.
_PRIVATE_INTENT_TEXT = (
    "personal private confidential medical financial secret diary journal password"
)

# Cosine similarity threshold for semantic classification.
_SEMANTIC_THRESHOLD = 0.7


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class ClassificationResult:
    """Result of privacy classification."""

    domain: str  # "private" or "external"
    confidence: float = 1.0
    reasoning: str = ""
    override: bool = False
    requires_user_confirmation: bool = False
    action: str = "route"  # "route", "queue", or "error"


@dataclass
class _EmbeddingCache:
    """Thread-safe in-process cache for the reference embedding."""

    _embedding: list[float] | None = field(default=None, init=False)

    def get(self) -> list[float] | None:
        return self._embedding

    def set(self, embedding: list[float]) -> None:
        self._embedding = embedding


_reference_cache = _EmbeddingCache()


class PrivacyClassifier:
    """Classifies requests into private or external domain.

    Implements the routing rules from SPEC.md §14.2, §14.3, §18.

    Args:
        custom_keywords: Optional list of additional keywords to treat as
            private signals. Merged with built-in defaults (not replaced).
        ollama_base_url: Base URL for the Ollama API used for semantic scoring.
            Defaults to the standard private-worker URL.
        semantic_threshold: Cosine similarity threshold above which a message
            is classified private via semantic scoring (default 0.7).
    """

    def __init__(
        self,
        custom_keywords: list[str] | None = None,
        ollama_base_url: str = "http://private-worker:11434",
        semantic_threshold: float = _SEMANTIC_THRESHOLD,
    ) -> None:
        extra = frozenset(kw.lower() for kw in (custom_keywords or []))
        self._private_keywords: frozenset[str] = _BUILTIN_PRIVATE_KEYWORDS | extra
        self._ollama_base_url = ollama_base_url
        self._semantic_threshold = semantic_threshold

    def classify(
        self,
        state: dict[str, Any],
        *,
        private_available: bool = True,
        external_available: bool = True,
    ) -> ClassificationResult:
        """Classify a request state into a privacy domain.

        Uses keyword-based content analysis only (sync).
        For full semantic scoring, use ``classify_async``.

        Args:
            state: Agent state dict with messages, privacy_mode, requested_tools.
            private_available: Whether the private domain is available.
            external_available: Whether the external domain is available.

        Returns:
            ClassificationResult with domain, confidence, reasoning, and action.
        """
        privacy_mode = state.get("privacy_mode")
        messages = state.get("messages", [])
        requested_tools = state.get("requested_tools")

        # 1. Explicit user override — always respected (§18, §14.4)
        if privacy_mode is not None:
            result = self._handle_explicit_override(
                privacy_mode, messages, private_available, external_available
            )
            return result

        # 2. Tool-based routing (§18)
        if requested_tools:
            tool_result = self._handle_tool_routing(
                requested_tools, messages, private_available, external_available
            )
            if tool_result is not None:
                return tool_result

        # 3. Content analysis + fail-safe (§14.3, §18)
        raw = self._raw_classify(messages)
        return self._apply_fail_safe(
            raw, private_available, external_available
        )

    async def classify_async(
        self,
        state: dict[str, Any],
        *,
        private_available: bool = True,
        external_available: bool = True,
    ) -> ClassificationResult:
        """Classify with semantic scoring via Ollama embeddings.

        Falls back gracefully to keyword-only if Ollama is unavailable.
        Semantic scoring is applied to the final user message in ``state``.

        Returns a ClassificationResult. Domain is private if keyword OR
        semantic similarity > threshold.
        """
        privacy_mode = state.get("privacy_mode")
        messages = state.get("messages", [])
        requested_tools = state.get("requested_tools")

        # 1. Explicit user override
        if privacy_mode is not None:
            return self._handle_explicit_override(
                privacy_mode, messages, private_available, external_available
            )

        # 2. Tool-based routing
        if requested_tools:
            tool_result = self._handle_tool_routing(
                requested_tools, messages, private_available, external_available
            )
            if tool_result is not None:
                return tool_result

        # 3. Content analysis: keyword + semantic (OR logic)
        keyword_domain = self._content_domain(messages)
        semantic_private = await self._semantic_is_private(messages)

        if keyword_domain == "private" or semantic_private:
            domain = "private"
            parts: list[str] = []
            if keyword_domain == "private":
                parts.append("private keywords detected")
            if semantic_private:
                parts.append("semantic similarity above threshold")
            reasoning = "Content analysis: " + "; ".join(parts) + "."
            raw = ClassificationResult(
                domain=domain,
                confidence=0.85,
                reasoning=reasoning,
            )
        else:
            raw = ClassificationResult(
                domain="external",
                confidence=0.8,
                reasoning="Content analysis: no private signals detected.",
            )

        return self._apply_fail_safe(raw, private_available, external_available)

    async def _semantic_is_private(
        self, messages: list[dict[str, Any]]
    ) -> bool:
        """Return True if the last user message is semantically private.

        Uses Ollama embeddings. Returns False (not private) on any failure,
        so keyword-only classification remains operative as a fallback.
        """
        # Find the last user message
        user_text: str | None = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
                break

        if not user_text:
            return False

        try:
            client = OllamaClient(base_url=self._ollama_base_url)

            # Fetch (or use cached) reference embedding
            ref_embedding = _reference_cache.get()
            if ref_embedding is None:
                ref_embedding = await client.embed(_PRIVATE_INTENT_TEXT)
                _reference_cache.set(ref_embedding)

            msg_embedding = await client.embed(user_text)
            similarity = _cosine_similarity(msg_embedding, ref_embedding)
            logger.debug(
                "Privacy semantic score: %.3f (threshold=%.2f)",
                similarity,
                self._semantic_threshold,
            )
            return similarity > self._semantic_threshold

        except Exception:  # noqa: BLE001
            logger.debug(
                "Semantic privacy check failed (Ollama unavailable), "
                "falling back to keyword-only",
                exc_info=True,
            )
            return False

    def _handle_explicit_override(
        self,
        privacy_mode: str,
        messages: list[dict[str, Any]],
        private_available: bool,
        external_available: bool,
    ) -> ClassificationResult:
        """Handle explicit user privacy_mode override."""
        domain = privacy_mode

        # Check if this overrides what auto-classification would say
        auto_domain = self._content_domain(messages)
        is_override = auto_domain != domain

        # Domain unavailability handling (§14.2)
        if domain == "private" and not private_available:
            return ClassificationResult(
                domain="private",
                confidence=1.0,
                reasoning=(
                    f"Explicit override to {domain};"
                    " private unavailable, queued."
                ),
                override=is_override,
                action="queue",
            )
        if domain == "external" and not external_available:
            return ClassificationResult(
                domain="external",
                confidence=1.0,
                reasoning=f"Explicit override to {domain}; external unavailable.",
                override=is_override,
                action="error",
            )

        return ClassificationResult(
            domain=domain,
            confidence=1.0,
            reasoning=f"Explicit user override to {domain}.",
            override=is_override,
            action="route",
        )

    def _handle_tool_routing(
        self,
        requested_tools: list[str],
        messages: list[dict[str, Any]],
        private_available: bool,
        external_available: bool,
    ) -> ClassificationResult | None:
        """Route based on requested tools. Returns None if no tool signal."""
        tool_set = set(requested_tools)
        has_private = bool(tool_set & _PRIVATE_TOOLS)
        has_external = bool(tool_set & _EXTERNAL_TOOLS)

        if has_private and has_external:
            # Mixed -> conservative private (§18)
            domain = "private"
            reasoning = (
                "Mixed tools (private + external);"
                " routing to private (conservative)."
            )
        elif has_private:
            domain = "private"
            reasoning = f"Private tool(s) requested: {tool_set & _PRIVATE_TOOLS}."
        elif has_external:
            domain = "external"
            reasoning = f"External tool(s) requested: {tool_set & _EXTERNAL_TOOLS}."
        else:
            return None  # Unknown tools, fall through to content analysis

        # Domain unavailability
        if domain == "private" and not private_available:
            return ClassificationResult(
                domain="private",
                confidence=0.95,
                reasoning=reasoning + " Private unavailable, queued.",
                action="queue",
            )
        if domain == "external" and not external_available:
            return ClassificationResult(
                domain="external",
                confidence=0.95,
                reasoning=reasoning + " External unavailable.",
                action="error",
            )

        return ClassificationResult(
            domain=domain,
            confidence=0.95,
            reasoning=reasoning,
            action="route",
        )

    def _raw_classify(
        self, messages: list[dict[str, Any]]
    ) -> ClassificationResult:
        """Classify based on content analysis (keyword-based).

        This is the internal classification method that can be patched
        in tests for controlling confidence values.
        """
        domain = self._content_domain(messages)
        confidence = 0.85 if domain == "private" else 0.8
        if domain == "private":
            reasoning = "Content analysis: private keywords detected."
        else:
            reasoning = "Content analysis: no private signals detected."
        return ClassificationResult(
            domain=domain,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _content_domain(self, messages: list[dict[str, Any]]) -> str:
        """Determine domain from message content keywords."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                if any(kw in content for kw in self._private_keywords):
                    return "private"
                return "external"
        return "external"

    def _apply_fail_safe(
        self,
        raw: ClassificationResult,
        private_available: bool,
        external_available: bool,
    ) -> ClassificationResult:
        """Apply fail-safe logic for low-confidence classifications (§14.3).

        Also handles domain unavailability for content-classified results.
        """
        confidence = raw.confidence
        domain = raw.domain

        # Low confidence fail-safe (§14.3)
        if confidence < 0.7:
            if private_available:
                # Force private when uncertain
                return ClassificationResult(
                    domain="private",
                    confidence=confidence,
                    reasoning=(
                        raw.reasoning
                        + " Low confidence; forced private (fail-safe)."
                    ),
                    action="route",
                )
            else:
                # Cannot force private, require user confirmation
                return ClassificationResult(
                    domain=domain,
                    confidence=confidence,
                    reasoning=(
                        raw.reasoning
                        + " Low confidence; private unavailable;"
                        " user confirmation required."
                    ),
                    requires_user_confirmation=True,
                    action="route",
                )

        # High confidence — route as classified
        # But handle domain unavailability
        if domain == "private" and not private_available:
            return ClassificationResult(
                domain="private",
                confidence=confidence,
                reasoning=raw.reasoning + " Private unavailable, queued.",
                requires_user_confirmation=True,
                action="queue",
            )
        if domain == "external" and not external_available:
            return ClassificationResult(
                domain="external",
                confidence=confidence,
                reasoning=raw.reasoning + " External unavailable.",
                action="error",
            )

        return ClassificationResult(
            domain=domain,
            confidence=confidence,
            reasoning=raw.reasoning,
            action="route",
        )
