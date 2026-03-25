"""Provider pricing tables for cost estimation — SPEC.md §24.

Pricing per 1M tokens for supported providers/models.
Returns Decimal("0") for unknown models (safe fallback).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

_MILLION = Decimal("1000000")


@dataclass(frozen=True)
class ModelPricing:
    """Per-million-token pricing for a model."""

    input_per_million: Decimal
    output_per_million: Decimal


# Pricing tables — updated periodically.
# Key format: (provider, model)
PRICING_TABLE: dict[tuple[str, str], ModelPricing] = {
    # OpenAI
    ("openai", "gpt-4o"): ModelPricing(
        input_per_million=Decimal("2.50"),
        output_per_million=Decimal("10.00"),
    ),
    ("openai", "gpt-4o-mini"): ModelPricing(
        input_per_million=Decimal("0.15"),
        output_per_million=Decimal("0.60"),
    ),
    ("openai", "gpt-4.1"): ModelPricing(
        input_per_million=Decimal("2.00"),
        output_per_million=Decimal("8.00"),
    ),
    ("openai", "gpt-4.1-mini"): ModelPricing(
        input_per_million=Decimal("0.40"),
        output_per_million=Decimal("1.60"),
    ),
    ("openai", "gpt-4-turbo"): ModelPricing(
        input_per_million=Decimal("10.00"),
        output_per_million=Decimal("30.00"),
    ),
    # Anthropic
    ("anthropic", "claude-sonnet"): ModelPricing(
        input_per_million=Decimal("3.00"),
        output_per_million=Decimal("15.00"),
    ),
    ("anthropic", "claude-sonnet-4-20250514"): ModelPricing(
        input_per_million=Decimal("3.00"),
        output_per_million=Decimal("15.00"),
    ),
    ("anthropic", "claude-haiku"): ModelPricing(
        input_per_million=Decimal("0.25"),
        output_per_million=Decimal("1.25"),
    ),
    ("anthropic", "claude-opus"): ModelPricing(
        input_per_million=Decimal("15.00"),
        output_per_million=Decimal("75.00"),
    ),
    # Google AI
    ("google_ai", "gemini-2.0-flash"): ModelPricing(
        input_per_million=Decimal("0.10"),
        output_per_million=Decimal("0.40"),
    ),
    ("google_ai", "gemini-pro"): ModelPricing(
        input_per_million=Decimal("1.25"),
        output_per_million=Decimal("5.00"),
    ),
    # Kimi (Moonshot AI)
    ("kimi", "kimi-k2"): ModelPricing(
        input_per_million=Decimal("2.00"),
        output_per_million=Decimal("8.00"),
    ),
    ("kimi", "moonshot-v1-128k"): ModelPricing(
        input_per_million=Decimal("0.84"),
        output_per_million=Decimal("0.84"),
    ),
    # Local (Ollama) — free
    ("ollama", "llama3.1"): ModelPricing(
        input_per_million=Decimal("0"),
        output_per_million=Decimal("0"),
    ),
}


def estimate_cost(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Estimate USD cost from provider pricing tables.

    Returns Decimal("0") for unknown provider/model combinations.
    """
    prov = provider.lower()
    mod = model.lower()
    key = (prov, mod)
    pricing = PRICING_TABLE.get(key)

    # Fallback: strip date suffix (e.g. "gpt-4.1-mini-2025-04-14" → "gpt-4.1-mini")
    if pricing is None:
        for (p, m), pr in PRICING_TABLE.items():
            if p == prov and mod.startswith(m):
                pricing = pr
                break

    if pricing is None:
        return Decimal("0")

    input_cost = pricing.input_per_million * Decimal(input_tokens) / _MILLION
    output_cost = pricing.output_per_million * Decimal(output_tokens) / _MILLION

    return input_cost + output_cost
