"""The core math: fertility = tokens / words. Plus all the derived quantities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from fertiscope.context import ContextReport, context_budget
from fertiscope.segmenters import count_words
from fertiscope.tokenizers import TOKENIZERS, TokenizerSpec, get_tokenize_fn


@dataclass(frozen=True)
class LanguageFertility:
    """Fertility numbers for one (text, language, tokenizer) triple."""
    lang: str
    words: int
    tokens: int

    @property
    def fertility(self) -> float:
        return self.tokens / self.words if self.words else 0.0


@dataclass(frozen=True)
class FertilityReport:
    """Full analysis output for one tokenizer over a (en, vi) corpus pair."""
    tokenizer_id: str
    tokenizer_display: str
    en: LanguageFertility
    vi: LanguageFertility
    context_4096: ContextReport
    context_8192: ContextReport
    notes: List[str] = field(default_factory=list)

    @property
    def fertility_ratio(self) -> float:
        """Vietnamese fertility / English fertility. The headline number."""
        if self.en.fertility == 0:
            return 0.0
        return self.vi.fertility / self.en.fertility

    @property
    def cost_multiplier(self) -> float:
        """Vietnamese cost / English cost at the same per-token price.

        This is just fertility_ratio - prices are per-token, so language
        with N x tokens costs N x to send/receive.
        """
        return self.fertility_ratio


def analyze(
    en_text: str,
    vi_text: str,
    tokenizer_id: str,
    context_windows: Tuple[int, ...] = (4096, 8192),
    avg_example_tokens_assumption: int = 100,
    tokens_per_turn_assumption_factor: float = 1.0,
) -> FertilityReport:
    """Compute the full FertilityReport for a (en_text, vi_text) pair under one tokenizer.

    Args:
      en_text: English baseline corpus.
      vi_text: Vietnamese parallel corpus (same content as en_text, translated).
      tokenizer_id: one of TOKENIZERS (see fertiscope.tokenizers).
      context_windows: which context sizes to compute capacity numbers for.
      avg_example_tokens_assumption: assumed size of an in-context example in
        ENGLISH tokens; we scale by fertility_ratio for Vietnamese.
      tokens_per_turn_assumption_factor: multiplier on avg_example_tokens for
        per-turn rate (default 1.0 means each turn ~ one example).

    Returns: FertilityReport.
    """
    spec: TokenizerSpec = TOKENIZERS[tokenizer_id]
    tok = get_tokenize_fn(tokenizer_id)

    en_words = count_words(en_text, "en")
    vi_words = count_words(vi_text, "vi")
    en_tokens = tok(en_text)
    vi_tokens = tok(vi_text)

    en_lf = LanguageFertility(lang="en", words=en_words, tokens=en_tokens)
    vi_lf = LanguageFertility(lang="vi", words=vi_words, tokens=vi_tokens)

    # In-context capacity: use Vietnamese per-turn size since that's what we care about.
    fertility_ratio = vi_lf.fertility / en_lf.fertility if en_lf.fertility else 1.0
    avg_example_tokens_vi = avg_example_tokens_assumption * fertility_ratio
    tokens_per_turn_vi = avg_example_tokens_vi * tokens_per_turn_assumption_factor

    ctx_reports = {
        cw: context_budget(
            context_window=cw,
            avg_tokens_per_example=avg_example_tokens_vi,
            tokens_per_turn=tokens_per_turn_vi,
            max_turns=10,
        )
        for cw in context_windows
    }

    notes: List[str] = []
    if vi_lf.fertility / en_lf.fertility >= 2.0:
        notes.append(
            "Vietnamese fertility is >=2x English under this tokenizer. "
            "Cost-sensitive deployment should consider a SEA-tuned alternative."
        )
    if vi_lf.fertility / en_lf.fertility < 1.2:
        notes.append(
            "Vietnamese fertility is close to English under this tokenizer. "
            "Tokenizer is well-tuned for Vietnamese."
        )

    return FertilityReport(
        tokenizer_id=tokenizer_id,
        tokenizer_display=spec.display_name,
        en=en_lf,
        vi=vi_lf,
        context_4096=ctx_reports[4096],
        context_8192=ctx_reports[8192],
        notes=notes,
    )


def analyze_all(
    en_text: str,
    vi_text: str,
    tokenizer_ids: List[str] = None,
) -> Dict[str, FertilityReport]:
    """Run analyze() across multiple tokenizers; return id -> report."""
    if tokenizer_ids is None:
        tokenizer_ids = list(TOKENIZERS.keys())
    return {tid: analyze(en_text, vi_text, tid) for tid in tokenizer_ids}


# ---------------------------------------------------------------------------
# Multi-turn conversation analysis
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Turn:
    """One conversation turn: role + parallel EN and VI text."""
    role: str  # 'system' | 'user' | 'assistant'
    en: str
    vi: str


@dataclass(frozen=True)
class TurnReport:
    """Per-turn metrics inside a conversation analysis."""
    turn_index: int  # 1-based for display
    role: str
    en_words: int
    en_tokens: int
    vi_words: int
    vi_tokens: int
    cumulative_en_tokens: int
    cumulative_vi_tokens: int
    cumulative_pct_4096: float
    cumulative_pct_8192: float


@dataclass(frozen=True)
class ProjectedPoint:
    """One projected (turn, cum_en, cum_vi) triple beyond the entered turns."""
    turn_index: int
    cumulative_en_tokens: int
    cumulative_vi_tokens: int


@dataclass(frozen=True)
class ConversationReport:
    """One tokenizer's view of a whole conversation."""
    tokenizer_id: str
    tokenizer_display: str
    turns: List[TurnReport]
    total_en_words: int
    total_en_tokens: int
    total_vi_words: int
    total_vi_tokens: int
    fertility_ratio: float
    first_overflow_turn_4096: int  # 0 = never overflows in the given turns
    first_overflow_turn_8192: int  # 0 = never overflows
    # Linear-extrapolation projection past the entered turns. Empty when N<2.
    projection: List[ProjectedPoint] = field(default_factory=list)
    # Predicted future overflow turn from the linear fit. 0 = unpredictable (slope<=0 or N<2).
    predicted_overflow_turn_4096: int = 0
    predicted_overflow_turn_8192: int = 0
    # Slope (avg tokens added per turn) of the linear fit, useful for the chart legend.
    projected_slope_en: float = 0.0
    projected_slope_vi: float = 0.0


def analyze_conversation(
    turns: List[Turn],
    tokenizer_id: str,
) -> ConversationReport:
    """Walk a multi-turn EN<->VI conversation and accumulate fertility + context numbers.

    Cost model assumption: every turn re-sends the entire prior history (the
    standard stateless-API contract). So total tokens spent ~ sum over turns of
    cumulative_tokens_at_turn. We don't model that explicit sum here - the
    per-turn cumulative column is what callers need for cost + overflow.
    """
    if not turns:
        raise ValueError("at least one turn is required")

    spec = TOKENIZERS[tokenizer_id]
    tok = get_tokenize_fn(tokenizer_id)

    turn_reports: List[TurnReport] = []
    cum_en = 0
    cum_vi = 0
    first_overflow_4096 = 0
    first_overflow_8192 = 0

    for i, t in enumerate(turns, start=1):
        en_words = count_words(t.en, "en") if t.en else 0
        vi_words = count_words(t.vi, "vi") if t.vi else 0
        en_tokens = tok(t.en) if t.en else 0
        vi_tokens = tok(t.vi) if t.vi else 0

        cum_en += en_tokens
        cum_vi += vi_tokens
        pct_4096 = min(999.0, 100.0 * cum_vi / 4096)
        pct_8192 = min(999.0, 100.0 * cum_vi / 8192)

        if first_overflow_4096 == 0 and cum_vi > 4096:
            first_overflow_4096 = i
        if first_overflow_8192 == 0 and cum_vi > 8192:
            first_overflow_8192 = i

        turn_reports.append(TurnReport(
            turn_index=i,
            role=t.role,
            en_words=en_words,
            en_tokens=en_tokens,
            vi_words=vi_words,
            vi_tokens=vi_tokens,
            cumulative_en_tokens=cum_en,
            cumulative_vi_tokens=cum_vi,
            cumulative_pct_4096=round(pct_4096, 2),
            cumulative_pct_8192=round(pct_8192, 2),
        ))

    total_en_words = sum(t.en_words for t in turn_reports)
    total_vi_words = sum(t.vi_words for t in turn_reports)
    en_fertility = cum_en / total_en_words if total_en_words else 0.0
    vi_fertility = cum_vi / total_vi_words if total_vi_words else 0.0
    ratio = vi_fertility / en_fertility if en_fertility else 0.0

    # ------------------------------------------------------------------
    # Linear-extrapolation projection
    # ------------------------------------------------------------------
    n = len(turn_reports)
    projection: List[ProjectedPoint] = []
    pred_4096 = 0
    pred_8192 = 0
    slope_en = 0.0
    slope_vi = 0.0
    if n >= 2:
        xs = [float(t.turn_index) for t in turn_reports]
        en_ys = [float(t.cumulative_en_tokens) for t in turn_reports]
        vi_ys = [float(t.cumulative_vi_tokens) for t in turn_reports]
        slope_en, intercept_en = _linear_fit(xs, en_ys)
        slope_vi, intercept_vi = _linear_fit(xs, vi_ys)
        pred_4096 = _predict_overflow_turn(slope_vi, intercept_vi, 4096)
        pred_8192 = _predict_overflow_turn(slope_vi, intercept_vi, 8192)
        end_turn = max(n + 15, (pred_8192 + 2) if pred_8192 else 0, 30)
        end_turn = min(end_turn, 50)
        for t in range(n + 1, end_turn + 1):
            en_proj = max(0, int(round(slope_en * t + intercept_en)))
            vi_proj = max(0, int(round(slope_vi * t + intercept_vi)))
            projection.append(ProjectedPoint(
                turn_index=t,
                cumulative_en_tokens=en_proj,
                cumulative_vi_tokens=vi_proj,
            ))

    return ConversationReport(
        tokenizer_id=tokenizer_id,
        tokenizer_display=spec.display_name,
        turns=turn_reports,
        total_en_words=total_en_words,
        total_en_tokens=cum_en,
        total_vi_words=total_vi_words,
        total_vi_tokens=cum_vi,
        fertility_ratio=round(ratio, 3),
        first_overflow_turn_4096=first_overflow_4096,
        first_overflow_turn_8192=first_overflow_8192,
        projection=projection,
        predicted_overflow_turn_4096=pred_4096,
        predicted_overflow_turn_8192=pred_8192,
        projected_slope_en=round(slope_en, 2),
        projected_slope_vi=round(slope_vi, 2),
    )


def _linear_fit(xs: List[float], ys: List[float]) -> tuple[float, float]:
    """Simple ordinary-least-squares linear regression. Returns (slope, intercept).
    Degenerate cases (n<2 or zero x-variance) return slope=0."""
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return 0.0, mean_y
    slope = num / den
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _predict_overflow_turn(slope: float, intercept: float, target: int) -> int:
    """First positive integer turn t where slope*t + intercept >= target. 0 if not predictable
    (slope<=0, or the predicted overflow is in the past)."""
    if slope <= 0:
        return 0
    import math
    t = (target - intercept) / slope
    if t <= 0:
        return 0
    return max(1, math.ceil(t))
