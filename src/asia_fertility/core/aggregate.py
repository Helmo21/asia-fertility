"""Sum-then-divide aggregation primitives.

NOT mean-of-ratios — mean(tokens_i/words_i) is biased by Jensen's inequality.
We sum tokens and words across the corpus, then divide. See afri-fertility
and Petrov 2023 for the same convention.
"""

from __future__ import annotations

from .metrics import PerSentenceMetrics


def fertility_point(metrics: list[PerSentenceMetrics]) -> float:
    if not metrics:
        raise ValueError("Cannot aggregate empty metrics list")
    total_tokens = sum(m.tokens for m in metrics)
    total_words = sum(m.words for m in metrics)
    if total_words == 0:
        raise ValueError("Total words is 0")
    return total_tokens / total_words


def premium_point(target: list[PerSentenceMetrics], baseline: list[PerSentenceMetrics]) -> float:
    return fertility_point(target) / fertility_point(baseline)


def cpt_point(metrics: list[PerSentenceMetrics]) -> float:
    if not metrics:
        raise ValueError("Cannot aggregate empty metrics list")
    total_chars = sum(m.chars for m in metrics)
    total_tokens = sum(m.tokens for m in metrics)
    if total_tokens == 0:
        raise ValueError("Total tokens is 0")
    return total_chars / total_tokens


def bpt_point(metrics: list[PerSentenceMetrics]) -> float:
    """UTF-8 bytes per token — cross-script-fair metric."""
    if not metrics:
        raise ValueError("Cannot aggregate empty metrics list")
    total_bytes = sum(m.bytes_ for m in metrics)
    total_tokens = sum(m.tokens for m in metrics)
    if total_tokens == 0:
        raise ValueError("Total tokens is 0")
    return total_bytes / total_tokens


def same_content_cost_ratio(
    target: list[PerSentenceMetrics], baseline: list[PerSentenceMetrics]
) -> float:
    """Billing ratio: tokens for the same content in target / in baseline."""
    if not target or not baseline:
        raise ValueError("Empty metrics list")
    if len(target) != len(baseline):
        raise ValueError(
            f"Parallel corpus misalignment: target={len(target)} baseline={len(baseline)}"
        )
    target_tokens = sum(m.tokens for m in target)
    baseline_tokens = sum(m.tokens for m in baseline)
    if baseline_tokens == 0:
        raise ValueError("Baseline tokens is 0")
    return target_tokens / baseline_tokens


def context_efficiency(cpt: float, windows: list[int]) -> dict[int, float]:
    return {w: w * cpt for w in windows}
