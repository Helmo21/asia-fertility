# STRR + Rényi efficiency metrics (optional moat)

Status: pending (v0.4 optional)
Tags: `metrics`, `strr`, `renyi`, `tokenizer-efficiency`, `optional`
Depends on: #018, #024
Blocks: None

## Scope

Add two additional tokenizer quality metrics that go **beyond fertility**, addressing the Nayeem 2025 critique ("Beyond Fertility"). STRR (Subword Token Reuse Rate) credits reuse; Rényi efficiency measures the smoothness of the token-frequency distribution.

This is afri-fertility-overtaking territory.

### Files to create

- `src/fertiscope/core/strr.py`
- `src/fertiscope/core/renyi.py`
- `tests/unit/test_strr.py`
- `tests/unit/test_renyi.py`
- `docs/methodology.md` — add a section explaining when to use STRR/Rényi vs fertility.

### Files to modify

- `src/fertiscope/core/__init__.py` — export `strr`, `renyi_efficiency`.
- `src/fertiscope/study/runner.py` — add `strr` and `renyi` columns to Row.
- `src/fertiscope/study/row.py` — add fields.

### Interface and contract

`src/fertiscope/core/strr.py`:

```python
"""STRR — Subword Token Reuse Rate (Nayeem et al. 2025, arXiv 2510.09947).

Higher = better. STRR measures how many subwords are reused across a corpus,
crediting tokenizers that develop a small core vocabulary for the target
language rather than fragmenting everything into byte fallbacks.

STRR(L, T) = (1 - unique_tokens / total_tokens) ∈ [0, 1]
"""
from __future__ import annotations
from collections import Counter
from fertiscope.tokenizers.base import Tokenizer


def strr(texts: list[str], tokenizer: Tokenizer) -> float:
    """Subword Token Reuse Rate over a list of sentences.

    Returns a value in [0, 1]. Higher = better reuse of vocabulary.

    Note: requires .encode() — not available for API count-only tokenizers
    (Anthropic, Gemini). Raises NotImplementedError for those.
    """
    if not texts:
        return 0.0
    try:
        all_ids: list[int] = []
        for t in texts:
            all_ids.extend(tokenizer.encode(t))
    except NotImplementedError:
        raise NotImplementedError(
            f"STRR requires .encode(); tokenizer '{tokenizer.info.id}' is count-only."
        )
    if not all_ids:
        return 0.0
    unique = len(set(all_ids))
    total  = len(all_ids)
    return 1.0 - (unique / total)
```

`src/fertiscope/core/renyi.py`:

```python
"""Rényi efficiency of a token distribution (Zouhar et al. 2023).

Higher Rényi efficiency (alpha=2.5 is standard) indicates a more uniform
token-frequency distribution, which correlates with better downstream LM
performance. Uniform → max efficiency; one token dominating → low.

efficiency = Rényi entropy / log(|vocab_in_corpus|)
"""
from __future__ import annotations
import math
from collections import Counter
from fertiscope.tokenizers.base import Tokenizer


def renyi_entropy(probs: list[float], alpha: float = 2.5) -> float:
    """H_alpha(p) = 1/(1-alpha) · log(sum p_i^alpha) for alpha != 1.

    Returns nats (base e).
    """
    if alpha == 1.0:
        # Limit: Shannon entropy
        return -sum(p * math.log(p) for p in probs if p > 0)
    s = sum(p ** alpha for p in probs)
    return math.log(s) / (1.0 - alpha)


def renyi_efficiency(texts: list[str], tokenizer: Tokenizer, *, alpha: float = 2.5) -> float:
    """Rényi efficiency for the token distribution over `texts`."""
    if not texts:
        return 0.0
    try:
        ids: list[int] = []
        for t in texts:
            ids.extend(tokenizer.encode(t))
    except NotImplementedError:
        raise NotImplementedError(
            f"Rényi efficiency requires .encode(); '{tokenizer.info.id}' is count-only."
        )
    if not ids:
        return 0.0
    counts = Counter(ids)
    total = sum(counts.values())
    probs = [c / total for c in counts.values()]
    H = renyi_entropy(probs, alpha)
    max_H = math.log(len(probs)) if len(probs) > 1 else 1e-9
    return H / max_H
```

`tests/unit/test_strr.py`:

```python
import pytest
from fertiscope.core.strr import strr
from fertiscope.tokenizers import get_tokenizer

def test_strr_zero_for_unique_tokens():
    """If every token is unique, STRR = 0."""
    class FakeTok:
        info = type("I", (), {"id": "fake"})
        _next = [0]
        def encode(self, t):
            ids = list(range(self._next[0], self._next[0] + len(t)))
            self._next[0] += len(t)
            return ids
        def count(self, t): return len(self.encode(t))
    assert strr(["abc", "def"], FakeTok()) == 0.0

def test_strr_one_for_all_same():
    """If all tokens are the same id, STRR → 1 (limit)."""
    class FakeTok:
        info = type("I", (), {"id": "fake"})
        def encode(self, t): return [42] * len(t)
        def count(self, t): return len(t)
    s = strr(["abc", "def"], FakeTok())
    assert s > 0.99

def test_strr_real_tiktoken():
    tok = get_tokenizer("openai/o200k_base")
    # English short repetitive text should show some reuse
    texts = ["the cat sat on the mat", "the dog sat on the floor", "the bird sat on the wire"]
    s = strr(texts, tok)
    assert 0.0 < s < 1.0

def test_strr_count_only_raises():
    """Anthropic / Gemini are count-only — STRR unavailable."""
    class FakeAPI:
        info = type("I", (), {"id": "anthropic/claude"})
        def encode(self, t): raise NotImplementedError("count-only")
        def count(self, t): return 10
    with pytest.raises(NotImplementedError, match="count-only"):
        strr(["hello"], FakeAPI())
```

`tests/unit/test_renyi.py`:

```python
import math, pytest
from fertiscope.core.renyi import renyi_efficiency, renyi_entropy

def test_renyi_entropy_uniform():
    probs = [0.25] * 4
    H = renyi_entropy(probs, alpha=2.0)
    # For uniform, Rényi entropy = log(n) for any alpha
    assert H == pytest.approx(math.log(4), rel=1e-9)

def test_renyi_efficiency_uniform():
    class FakeTok:
        info = type("I", (), {"id": "x"})
        def encode(self, t): return [0, 1, 2, 3]   # uniform across 4 ids
        def count(self, t): return 4
    e = renyi_efficiency(["x"], FakeTok())
    assert e == pytest.approx(1.0, rel=1e-9)

def test_renyi_efficiency_skewed():
    class FakeTok:
        info = type("I", (), {"id": "x"})
        def encode(self, t): return [0]*100 + [1]*1
        def count(self, t): return 101
    e = renyi_efficiency(["x"], FakeTok())
    assert e < 0.5
```

### Notes

- STRR ranges [0, 1]; afri-fertility doesn't report this — clear differentiation.
- Rényi alpha=2.5 is the convention from Zouhar et al. — document why.
- Both metrics require `encode()`, not just `count()`. API tokenizers raise NotImplementedError, and the study runner records NaN for those rows.
- The study runner (#024) sums per-sentence token-ID lists across a language to feed STRR/Rényi — this changes the runner contract slightly. Refactor: instead of `aggregate_with_cis(metrics)` operating on per-sentence aggregates, pass the raw sentence-level token-ID lists for STRR/Rényi. Alternative: keep aggregates, compute STRR/Rényi in a separate pass.

## Acceptance Criteria

- [ ] `from fertiscope.core import strr, renyi_efficiency` works.
- [ ] `strr([], tok)` returns 0.0.
- [ ] `strr` returns 0 for unique-only tokens.
- [ ] `strr` returns near-1 for all-same tokens.
- [ ] `renyi_efficiency` returns 1.0 for uniform distribution.
- [ ] `renyi_efficiency` returns < 0.5 for highly skewed distribution.
- [ ] Both raise `NotImplementedError` for count-only tokenizers.
- [ ] Study runner Row dataclass has `strr` and `renyi` fields.
- [ ] Study output (CSV/parquet/JSON) includes both columns.
- [ ] All 7 unit tests pass.
- [ ] Methodology doc updated.
- [ ] `mypy --strict src/fertiscope/core/strr.py src/fertiscope/core/renyi.py` passes.

## User Stories

### Story: Researcher uses STRR to compare tokenizers

1. Runs the study; `runs/main/results.parquet` has `strr` column.
2. Filters Tamil rows.
3. cl100k_base STRR = 0.15, o200k_base STRR = 0.42.
4. Concludes: o200k_base reuses more Tamil subwords → better.

### Story: Paper v2 reviewer asks "did you address Nayeem?"

1. Reviewer: "Fertility-alone-is-incomplete (Nayeem 2025)."
2. Author cites paper §X with STRR + Rényi column added to Table 1.
3. Reviewer satisfied.

### Story: API tokenizer comparison gracefully skips

1. Study includes `anthropic/claude`.
2. STRR column for Claude rows = NaN.
3. Skip reason recorded: "count-only — STRR unavailable".

---

Blocked by: #018, #024
