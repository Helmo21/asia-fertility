"""Wide-table row schema for study results."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Row:
    corpus: str
    lang: str
    iso: str
    script: str
    family: str
    tokenizer: str
    tokenizer_family: str
    tokenizer_backend: str

    n_sentences: int = 0
    tokens_sum: int = 0
    words_sum: int = 0
    chars_sum: int = 0
    bytes_sum: int = 0

    fertility: float = float("nan")
    fertility_ci_low: float = float("nan")
    fertility_ci_high: float = float("nan")

    premium: float = float("nan")
    premium_ci_low: float = float("nan")
    premium_ci_high: float = float("nan")

    cost_ratio: float = float("nan")
    cost_ratio_ci_low: float = float("nan")
    cost_ratio_ci_high: float = float("nan")

    cpt: float = float("nan")
    cpt_ci_low: float = float("nan")
    cpt_ci_high: float = float("nan")

    bpt: float = float("nan")
    bpt_ci_low: float = float("nan")
    bpt_ci_high: float = float("nan")

    context_efficiency: dict[int, float] = field(default_factory=dict)

    segmenter_used: str = ""
    tokenizer_unavailable: bool = False
    skip_reason: str | None = None
