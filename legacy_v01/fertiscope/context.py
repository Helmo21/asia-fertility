"""Context-window math: max in-context examples + utilization curve."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class ContextReport:
    """Per (context-window, language) capacity numbers."""
    context_window: int
    avg_tokens_per_example: float
    max_examples: int
    # Per-turn utilization curve: (turn_n, % of context used so far)
    utilization_curve: List[Tuple[int, float]]


def max_examples(context_window: int, avg_tokens_per_example: float) -> int:
    """How many <example> blocks fit into a context window."""
    if avg_tokens_per_example <= 0:
        return 0
    return int(context_window // avg_tokens_per_example)


def utilization_curve(
    context_window: int,
    tokens_per_turn: float,
    max_turns: int = 10,
) -> List[Tuple[int, float]]:
    """% of context consumed after N turns.

    This is the HONEST replacement for "predicted quality degradation curve."
    We do NOT predict quality; quality degradation depends on the model + task,
    which FertiScope is deliberately blind to. What we DO know is when you
    run out of context budget. That number is causally upstream of any
    quality degradation argument.
    """
    curve = []
    for turn in range(1, max_turns + 1):
        consumed = tokens_per_turn * turn
        pct = min(100.0, 100.0 * consumed / context_window) if context_window > 0 else 100.0
        curve.append((turn, round(pct, 2)))
    return curve


def context_budget(
    context_window: int,
    avg_tokens_per_example: float,
    tokens_per_turn: float,
    max_turns: int = 10,
) -> ContextReport:
    return ContextReport(
        context_window=context_window,
        avg_tokens_per_example=avg_tokens_per_example,
        max_examples=max_examples(context_window, avg_tokens_per_example),
        utilization_curve=utilization_curve(context_window, tokens_per_turn, max_turns),
    )
