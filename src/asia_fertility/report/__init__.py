"""Report module: figures + leaderboard JSON."""

from __future__ import annotations

from .figures import (
    fig1_heatmap,
    fig2_premium_by_script,
    fig3_cost,
    fig4_context_exhaustion,
    fig5_in_context_capacity,
    fig6_premium_vs_recall,
    fig7_cost_vs_latency,
)
from .leaderboard import emit_leaderboard, write_leaderboard

__all__ = [
    "emit_leaderboard",
    "fig1_heatmap",
    "fig2_premium_by_script",
    "fig3_cost",
    "fig4_context_exhaustion",
    "fig5_in_context_capacity",
    "fig6_premium_vs_recall",
    "fig7_cost_vs_latency",
    "write_leaderboard",
]
