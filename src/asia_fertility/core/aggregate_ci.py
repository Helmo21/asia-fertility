"""Aggregate metrics with bootstrap CIs."""
from __future__ import annotations

from dataclasses import dataclass

from .aggregate import bpt_point, context_efficiency, cpt_point, fertility_point
from .bootstrap import bootstrap_ci
from .metrics import PerSentenceMetrics

Triple = tuple[float, float, float]


@dataclass(frozen=True)
class AggregateMetrics:
    lang: str
    tokenizer_id: str
    n_sentences: int
    fertility: Triple
    premium: Triple | None
    cost_ratio: Triple | None
    cpt: Triple
    bpt: Triple
    context_efficiency: dict[int, float]


def aggregate_with_cis(
    target: list[PerSentenceMetrics],
    *,
    baseline: list[PerSentenceMetrics] | None = None,
    n_resamples: int = 1000,
    rng_seed: int = 42,
    windows: list[int] | None = None,
) -> AggregateMetrics:
    if not target:
        raise ValueError("Cannot aggregate empty target metrics")
    if windows is None:
        windows = [4096, 8192, 32768, 131072]

    fert = bootstrap_ci(target, fertility_point, n_resamples=n_resamples, rng_seed=rng_seed)
    cpt = bootstrap_ci(target, cpt_point, n_resamples=n_resamples, rng_seed=rng_seed)
    bpt = bootstrap_ci(target, bpt_point, n_resamples=n_resamples, rng_seed=rng_seed)

    premium = None
    cost_ratio = None
    if baseline:
        base_fert = fertility_point(baseline)

        def _prem_fn(m: list[PerSentenceMetrics]) -> float:
            return fertility_point(m) / base_fert

        premium = bootstrap_ci(target, _prem_fn, n_resamples=n_resamples, rng_seed=rng_seed)

        if len(target) == len(baseline):
            base_tokens = sum(m.tokens for m in baseline)

            def _cr_fn(m: list[PerSentenceMetrics]) -> float:
                return sum(x.tokens for x in m) / base_tokens

            cost_ratio = bootstrap_ci(target, _cr_fn, n_resamples=n_resamples, rng_seed=rng_seed)

    return AggregateMetrics(
        lang=target[0].lang,
        tokenizer_id=target[0].tokenizer_id,
        n_sentences=len(target),
        fertility=fert,
        premium=premium,
        cost_ratio=cost_ratio,
        cpt=cpt,
        bpt=bpt,
        context_efficiency=context_efficiency(cpt[0], windows),
    )
