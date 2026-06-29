"""Latency benchmark — measure wall-clock penalty of high-fertility languages.

The "input-side UX twin" of the cost-ratio dimension. While cost_ratio
quantifies how many more *dollars* high-fertility languages spend per
request, latency_penalty quantifies how many more *seconds* the user
waits. Empirically, the two correlate (afri-fertility reports r ≈ 0.94)
because input tokens dominate prefill, which dominates TTFT, which
dominates wall-clock.

Public surface:

    from asia_fertility.latency import LatencyConfig, run_latency, latency_report

The CLI wraps both: `asia-fertility latency run --config …`.
"""

from __future__ import annotations

from .runner import (
    LatencyConfig,
    LatencyRow,
    estimate_cost_usd,
    latency_report,
    run_latency,
)

__all__ = [
    "LatencyConfig",
    "LatencyRow",
    "estimate_cost_usd",
    "latency_report",
    "run_latency",
]
