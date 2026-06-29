"""Bootstrap confidence intervals at the sentence level."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from .metrics import PerSentenceMetrics


def bootstrap_ci(
    metrics: list[PerSentenceMetrics],
    stat_fn: Callable[[list[PerSentenceMetrics]], float],
    *,
    n_resamples: int = 1000,
    ci: float = 0.95,
    rng_seed: int = 42,
) -> tuple[float, float, float]:
    """Sentence-level bootstrap. Returns (point, low, high)."""
    if not metrics:
        raise ValueError("Cannot bootstrap an empty metrics list")
    point = stat_fn(metrics)
    if len(metrics) == 1:
        return (point, point, point)

    rng = np.random.default_rng(rng_seed)
    n = len(metrics)
    samples = np.empty(n_resamples, dtype=np.float64)
    for i in range(n_resamples):
        idx = rng.integers(0, n, n)
        resampled = [metrics[j] for j in idx]
        try:
            samples[i] = stat_fn(resampled)
        except ValueError:
            samples[i] = np.nan

    valid = samples[~np.isnan(samples)]
    if len(valid) == 0:
        return (point, float("nan"), float("nan"))
    alpha = (1.0 - ci) / 2.0
    low = float(np.quantile(valid, alpha))
    high = float(np.quantile(valid, 1.0 - alpha))
    return (point, low, high)
