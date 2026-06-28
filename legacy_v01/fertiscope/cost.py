"""Per-tokenizer pricing snapshot. Static table; rev when providers re-price."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PriceRow:
    """Per-1M-token input price snapshot for a (provider, model) pair."""
    provider: str
    model: str
    tokenizer_id: str
    input_per_1m_usd: float
    output_per_1m_usd: float
    notes: str = ""


# v0.1 launch price table. USD per 1M tokens, input/output.
# Sourced from public pricing pages as of 2026-06-20.
# Update when re-running for production-grade output.
PRICES: List[PriceRow] = [
    # cl100k tokenizer family
    PriceRow("OpenAI", "gpt-3.5-turbo", "cl100k", 0.50, 1.50,
             "Legacy chat model; cl100k tokenizer."),
    PriceRow("OpenAI", "gpt-4-turbo", "cl100k", 10.00, 30.00,
             "Pre-4o flagship; cl100k tokenizer."),

    # o200k tokenizer family
    PriceRow("OpenAI", "gpt-4o", "o200k", 2.50, 10.00,
             "GPT-4o; o200k tokenizer."),
    PriceRow("OpenAI", "gpt-4o-mini", "o200k", 0.15, 0.60,
             "Cheap GPT-4o variant; o200k tokenizer."),

    # Llama-3.1 tokenizer family - prices via cloud providers
    PriceRow("AWS Bedrock", "Llama-3.1-70B-Instruct", "llama-3.1", 0.99, 0.99,
             "Bedrock-hosted Llama-3.1-70B."),
    PriceRow("Together AI", "Llama-3.1-70B-Instruct-Turbo", "llama-3.1", 0.88, 0.88,
             "Together AI-hosted Llama-3.1-70B."),
    PriceRow("Self-hosted", "Llama-3.1-8B", "llama-3.1", 0.00, 0.00,
             "Local inference; cost = electricity + GPU amortization."),

    # SEA-LION
    PriceRow("AWS Bedrock", "SEA-LION-v3-8B-IT", "sea-lion-v3", 0.00, 0.00,
             "SEA-LION via self-hosted or AI Singapore endpoint; pricing TBD."),
]


def prices_for_tokenizer(tokenizer_id: str) -> List[PriceRow]:
    """All public price rows that share the given tokenizer."""
    return [p for p in PRICES if p.tokenizer_id == tokenizer_id]


def cost_multiplier(fertility_ratio: float, input_per_1m_usd: float) -> float:
    """Cost multiplier vs English baseline = fertility_ratio (the price stays the same per
    token, but the language uses N times more tokens for the same content)."""
    return fertility_ratio
