# Sum-then-divide aggregation (NOT mean-of-ratios)

Status: pending
Tags: `aggregation`, `statistics`, `metrics`, `core`
Depends on: #015
Blocks: #019

## Scope

Implement the aggregation primitives that turn a list of `PerSentenceMetrics` into language-level metrics. Strictly **sum-then-divide**, never mean-of-ratios. Document the Jensen's-inequality reasoning in the docstring so a future contributor doesn't "simplify" it back.

### Files to create

- `src/fertiscope/core/aggregate.py`
- `tests/unit/test_aggregate.py`

### Files to modify

- `src/fertiscope/core/__init__.py` — export aggregation functions.

### Interface and contract

`src/fertiscope/core/aggregate.py`:

```python
"""Sum-then-divide aggregation of per-sentence metrics.

CRITICAL: We sum tokens and words across all sentences, then divide.
We do NOT compute per-sentence ratios and average them.

Why: mean-of-ratios is biased by Jensen's inequality. With variable
sentence lengths (FLORES-200 sentences range from 5 to 50 words),
mean(tokens_i / words_i) != sum(tokens_i) / sum(words_i). The sum-
then-divide form is the unbiased estimator of "tokens per word over
this corpus" and matches the per-million-tokens billing model that
makes the cost ratio meaningful.

afri-fertility uses the same convention. If you find yourself
"simplifying" this, read Petrov et al. 2023 footnote 4 first.
"""
from __future__ import annotations
from fertiscope.core.metrics import PerSentenceMetrics


def fertility_point(metrics: list[PerSentenceMetrics]) -> float:
    """Tokens per word, sum-then-divide.

    Raises ValueError if metrics is empty (caller should handle).
    """
    if not metrics:
        raise ValueError("Cannot aggregate empty metrics list")
    total_tokens = sum(m.tokens for m in metrics)
    total_words  = sum(m.words for m in metrics)
    if total_words == 0:
        raise ValueError("Total words is 0 — segmenter produced no words for this corpus")
    return total_tokens / total_words


def premium_point(target: list[PerSentenceMetrics], baseline: list[PerSentenceMetrics]) -> float:
    """How many times more tokens per word the target language uses vs baseline.

    Both lists must be tokenized by the SAME tokenizer. The runner enforces this.
    Premium = fertility(target) / fertility(baseline).
    """
    return fertility_point(target) / fertility_point(baseline)


def cpt_point(metrics: list[PerSentenceMetrics]) -> float:
    """Characters per token. Higher = tokenizer packs more meaning per token."""
    if not metrics:
        raise ValueError("Cannot aggregate empty metrics list")
    total_chars  = sum(m.chars for m in metrics)
    total_tokens = sum(m.tokens for m in metrics)
    if total_tokens == 0:
        raise ValueError("Total tokens is 0")
    return total_chars / total_tokens


def bpt_point(metrics: list[PerSentenceMetrics]) -> float:
    """UTF-8 bytes per token. Cross-script-fair metric — the only one that
    treats a 3-byte Devanagari character commensurately with a 1-byte ASCII one.
    """
    if not metrics:
        raise ValueError("Cannot aggregate empty metrics list")
    total_bytes  = sum(m.bytes_ for m in metrics)
    total_tokens = sum(m.tokens for m in metrics)
    if total_tokens == 0:
        raise ValueError("Total tokens is 0")
    return total_bytes / total_tokens


def same_content_cost_ratio(target: list[PerSentenceMetrics], baseline: list[PerSentenceMetrics]) -> float:
    """The billing ratio: tokens for the same content in target / in baseline.

    This is what governs API bills directly (per-token pricing is constant
    within a tokenizer). Differs from premium when languages pack different
    amounts of meaning per word — for cost reporting, use this, not premium.
    """
    if not target:
        raise ValueError("target metrics empty")
    if not baseline:
        raise ValueError("baseline metrics empty")
    if len(target) != len(baseline):
        raise ValueError(f"Parallel corpus misalignment: target={len(target)} baseline={len(baseline)}")
    target_tokens   = sum(m.tokens for m in target)
    baseline_tokens = sum(m.tokens for m in baseline)
    if baseline_tokens == 0:
        raise ValueError("Baseline tokens is 0")
    return target_tokens / baseline_tokens


def context_efficiency(cpt: float, windows: list[int]) -> dict[int, float]:
    """For each context window size, return effective real characters."""
    return {w: w * cpt for w in windows}
```

`src/fertiscope/core/__init__.py`:

```python
from .normalize import nfc, is_nfc
from .metrics import PerSentenceMetrics, per_sentence
from .aggregate import (
    fertility_point, premium_point, cpt_point, bpt_point,
    same_content_cost_ratio, context_efficiency,
)

__all__ = [
    "nfc", "is_nfc",
    "PerSentenceMetrics", "per_sentence",
    "fertility_point", "premium_point", "cpt_point", "bpt_point",
    "same_content_cost_ratio", "context_efficiency",
]
```

`tests/unit/test_aggregate.py`:

```python
import math
import pytest
from fertiscope.core import PerSentenceMetrics
from fertiscope.core.aggregate import (
    fertility_point, premium_point, cpt_point, bpt_point,
    same_content_cost_ratio, context_efficiency,
)

def _m(tokens, words, chars=10, bytes_=10, sid="s1", lang="eng", tid="t"):
    return PerSentenceMetrics(sentence_id=sid, lang=lang, tokenizer_id=tid,
                              tokens=tokens, words=words, chars=chars, bytes_=bytes_)

def test_fertility_simple():
    ms = [_m(10, 5), _m(20, 10)]
    assert fertility_point(ms) == 3.0   # (10+20) / (5+10)

def test_fertility_empty_raises():
    with pytest.raises(ValueError):
        fertility_point([])

def test_fertility_zero_words_raises():
    with pytest.raises(ValueError):
        fertility_point([_m(10, 0)])

def test_sum_then_divide_differs_from_mean_of_ratios():
    """The canonical Jensen-inequality demonstration: lengths matter."""
    short = _m(tokens=10, words=2)    # ratio = 5
    long  = _m(tokens=20, words=10)   # ratio = 2
    sum_then_divide = fertility_point([short, long])         # 30/12 = 2.5
    mean_of_ratios  = (10/2 + 20/10) / 2                     # (5+2)/2 = 3.5
    assert sum_then_divide == pytest.approx(2.5)
    assert mean_of_ratios  == pytest.approx(3.5)
    assert sum_then_divide != mean_of_ratios

def test_premium():
    baseline = [_m(10, 5)]    # fertility 2
    target   = [_m(20, 5)]    # fertility 4
    assert premium_point(target, baseline) == 2.0

def test_cpt():
    ms = [_m(tokens=4, words=2, chars=12)]
    assert cpt_point(ms) == 3.0

def test_bpt():
    ms = [_m(tokens=2, words=1, chars=4, bytes_=10)]
    assert bpt_point(ms) == 5.0

def test_same_content_cost_ratio():
    baseline = [_m(10, 5), _m(20, 10)]   # 30 tokens
    target   = [_m(70, 5), _m(80, 10)]   # 150 tokens
    assert same_content_cost_ratio(target, baseline) == 5.0

def test_same_content_misaligned_raises():
    a = [_m(10, 5), _m(20, 10)]
    b = [_m(10, 5)]
    with pytest.raises(ValueError, match="misalignment"):
        same_content_cost_ratio(a, b)

def test_context_efficiency():
    e = context_efficiency(cpt=3.5, windows=[4096, 8192])
    assert e == {4096: 4096*3.5, 8192: 8192*3.5}

def test_real_paper_numbers():
    """Match a hand-computed Tamil/cl100k slice of the paper.

    From paper Table 1: Tamil tokens-per-sentence on cl100k = 7.19x English.
    Synthetic: 50 sentences, English averages 27 tokens, Tamil averages 194 tokens.
    """
    eng = [_m(tokens=27, words=22) for _ in range(50)]      # mean fertility ~1.23
    tam = [_m(tokens=194, words=18) for _ in range(50)]     # mean fertility ~10.78
    assert same_content_cost_ratio(tam, eng) == pytest.approx(7.185, abs=0.01)
```

### Notes

- The aggregate primitives are **pure functions** of lists of `PerSentenceMetrics`. No state, no I/O. They're trivially testable with hypothesis later (#019 adds property tests).
- `same_content_cost_ratio` REQUIRES aligned parallel corpora — its `len()` check enforces this. If you have non-aligned (e.g. custom one-language-only corpus), use `premium_point` against a same-tokenizer baseline computed separately.
- `context_efficiency` is the only function that takes a non-list input; it's purely arithmetic from a single CPT scalar. Window list defaults are set in the study runner (#024), not here.
- The Jensen test case (`test_sum_then_divide_differs_from_mean_of_ratios`) is THE test that prevents drift. If someone refactors and breaks it, that's a load-bearing failure.

## Acceptance Criteria

- [ ] `fertility_point` on `[(10,5), (20,10)]` returns `3.0` (sum-then-divide), not `2.5` (mean-of-ratios).
- [ ] `fertility_point([])` raises `ValueError`.
- [ ] `fertility_point([_m(10, 0)])` raises `ValueError("Total words is 0")`.
- [ ] `premium_point(target, baseline)` matches paper Table 1 within ±1% on the synthetic Tamil slice.
- [ ] `cpt_point` and `bpt_point` both sum-then-divide.
- [ ] `same_content_cost_ratio` requires aligned corpora; misalignment raises `ValueError`.
- [ ] `context_efficiency` returns a dict with the input window keys.
- [ ] All 12 unit tests pass.
- [ ] `mypy --strict src/fertiscope/core/aggregate.py` passes.
- [ ] No imports of `numpy` (kept lean — numpy enters only in #019 for bootstrap).

## User Stories

### Story: Researcher debugs an unexpected number

1. Sees Tamil fertility = 3.6 instead of expected 11.
2. Reads `aggregate.py` docstring → understands sum-then-divide.
3. Checks segmenter output: words count was inflated by counting every syllable.
4. Fix is in `spaceless.py`, not aggregation.

### Story: Code reviewer guards against silent regression

1. Reviewer sees PR refactoring fertility to mean-of-ratios "for elegance".
2. `test_sum_then_divide_differs_from_mean_of_ratios` fails.
3. PR is blocked. Reviewer points to docstring rationale.

---

Blocked by: #015
