# Haystack builder with real-tokenizer sizing

Status: pending
Tags: `niah`, `haystack`, `tokenizer-accurate-sizing`
Depends on: #006, #012, #027
Blocks: #030

## Scope

Build a language-specific haystack at a target token count with a marker inserted at a specified percentile position. Uses **the real tokenizer for sizing**, fixing Miles' v1 limitation (`len(text)//4` estimation).

### Files to create

- `src/fertiscope/niah/haystack.py`
- `tests/unit/test_niah_haystack.py`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/niah/haystack.py`:

```python
"""Build NIAH haystacks at target token sizes with markers at specified positions.

Sizing uses the real tokenizer (not len/4 estimation) so the percentile
position is accurate. Returns the actual marker position (in tokens) for
audit; the runner records this in result rows.
"""
from __future__ import annotations
from dataclasses import dataclass
from fertiscope.corpora.base import Sentence
from fertiscope.tokenizers.base import Tokenizer


@dataclass(frozen=True)
class Haystack:
    text: str
    target_tokens: int
    actual_tokens: int
    marker: str
    position_pct: float
    marker_position_tokens: int
    n_sentences_used: int


def build_haystack(
    sentences: list[Sentence],
    *,
    target_tokens: int,
    tokenizer: Tokenizer,
    marker: str,
    position_pct: float,
    sentence_separator: str = " ",
) -> Haystack:
    """Build a haystack of ~target_tokens with `marker` inserted at position_pct.

    Args:
        sentences: list of sentences in the target language. Cycled if not enough.
        target_tokens: desired total token count.
        tokenizer: the tokenizer used for sizing (and for the model's input).
        marker: the needle string.
        position_pct: 0.0 to 1.0. 0.05 = near start, 0.95 = near end.

    Returns:
        Haystack with the actual built text + audit info.

    Raises:
        ValueError if target_tokens < tokenizer.count(marker) * 4 (haystack too small).
    """
    if not 0.0 < position_pct < 1.0:
        raise ValueError(f"position_pct must be in (0,1), got {position_pct}")
    if not sentences:
        raise ValueError("Cannot build haystack from empty sentence list")

    marker_tokens = tokenizer.count(marker)
    if target_tokens < marker_tokens * 4:
        raise ValueError(f"target_tokens={target_tokens} too small for marker of {marker_tokens} tokens (need at least 4x)")

    # Build pre-marker chunk
    pre_target = int(target_tokens * position_pct) - (marker_tokens // 2)
    pre_target = max(1, pre_target)
    post_target = target_tokens - pre_target - marker_tokens
    post_target = max(1, post_target)

    pre_text, n_pre  = _fill_to_tokens(sentences, pre_target,  tokenizer, sentence_separator, start_idx=0)
    post_text, n_post = _fill_to_tokens(sentences, post_target, tokenizer, sentence_separator, start_idx=n_pre)

    full_text = f"{pre_text}{sentence_separator}{marker}{sentence_separator}{post_text}"
    actual_tokens = tokenizer.count(full_text)
    marker_position_tokens = tokenizer.count(f"{pre_text}{sentence_separator}{marker}")

    return Haystack(
        text=full_text,
        target_tokens=target_tokens,
        actual_tokens=actual_tokens,
        marker=marker,
        position_pct=position_pct,
        marker_position_tokens=marker_position_tokens,
        n_sentences_used=n_pre + n_post,
    )


def _fill_to_tokens(
    sentences: list[Sentence],
    target: int,
    tokenizer: Tokenizer,
    sep: str,
    *,
    start_idx: int,
) -> tuple[str, int]:
    """Concatenate sentences (cycling from start_idx) until token count >= target.
    Returns (text, n_sentences_consumed).
    """
    parts: list[str] = []
    n = 0
    accum_tokens = 0
    n_sentences = len(sentences)
    idx = start_idx % n_sentences
    while accum_tokens < target:
        sent_text = sentences[idx].text
        parts.append(sent_text)
        n += 1
        # Estimate; re-count after every 5 sentences to avoid quadratic blowup
        if n % 5 == 0 or n == 1:
            accum_tokens = tokenizer.count(sep.join(parts))
        else:
            accum_tokens += tokenizer.count(sent_text) + tokenizer.count(sep)
        idx = (idx + 1) % n_sentences
    return sep.join(parts), n
```

`tests/unit/test_niah_haystack.py`:

```python
import pytest
from fertiscope.corpora.base import Sentence
from fertiscope.tokenizers import get_tokenizer
from fertiscope.niah.haystack import build_haystack, Haystack

SENTENCES = [
    Sentence(id=f"s{i}", lang="eng", text=f"The quick brown fox number {i} jumped over a lazy dog and ran into the forest near the mountain.")
    for i in range(50)
]

def test_haystack_basic():
    tok = get_tokenizer("openai/o200k_base")
    h = build_haystack(SENTENCES, target_tokens=500, tokenizer=tok,
                      marker="MARKER-AURORA-9241", position_pct=0.5)
    assert isinstance(h, Haystack)
    assert h.target_tokens == 500
    assert 450 <= h.actual_tokens <= 600   # within 20%
    assert "MARKER-AURORA-9241" in h.text
    # marker_position_tokens should be near 50% of actual_tokens
    expected_pos = h.actual_tokens * 0.5
    assert abs(h.marker_position_tokens - expected_pos) <= h.actual_tokens * 0.15

def test_haystack_position_5pct():
    tok = get_tokenizer("openai/o200k_base")
    h = build_haystack(SENTENCES, target_tokens=1000, tokenizer=tok,
                      marker="MARKER-X-001", position_pct=0.05)
    # marker should be in the first 15% of tokens
    assert h.marker_position_tokens <= h.actual_tokens * 0.15

def test_haystack_position_95pct():
    tok = get_tokenizer("openai/o200k_base")
    h = build_haystack(SENTENCES, target_tokens=1000, tokenizer=tok,
                      marker="MARKER-X-099", position_pct=0.95)
    assert h.marker_position_tokens >= h.actual_tokens * 0.85

def test_haystack_invalid_pct():
    tok = get_tokenizer("openai/o200k_base")
    with pytest.raises(ValueError, match="position_pct"):
        build_haystack(SENTENCES, target_tokens=500, tokenizer=tok,
                       marker="X", position_pct=0.0)
    with pytest.raises(ValueError, match="position_pct"):
        build_haystack(SENTENCES, target_tokens=500, tokenizer=tok,
                       marker="X", position_pct=1.0)

def test_haystack_too_small_for_marker():
    tok = get_tokenizer("openai/o200k_base")
    huge_marker = "X" * 10000
    with pytest.raises(ValueError, match="too small"):
        build_haystack(SENTENCES, target_tokens=100, tokenizer=tok,
                       marker=huge_marker, position_pct=0.5)

def test_haystack_empty_sentences():
    tok = get_tokenizer("openai/o200k_base")
    with pytest.raises(ValueError, match="empty"):
        build_haystack([], target_tokens=500, tokenizer=tok,
                       marker="X", position_pct=0.5)

def test_marker_substring_unique():
    """The marker shouldn't appear elsewhere by accident (would confuse recall)."""
    tok = get_tokenizer("openai/o200k_base")
    h = build_haystack(SENTENCES, target_tokens=500, tokenizer=tok,
                      marker="MARKER-XYZ-12345", position_pct=0.5)
    assert h.text.count("MARKER-XYZ-12345") == 1
```

### Notes

- The `actual_tokens / target_tokens` ratio should fall within ±20% for typical inputs. Wider deviations mean either the sentence list is too short (cycled too much) or the marker is too large for the haystack.
- The amortized re-counting in `_fill_to_tokens` (every 5 sentences) avoids O(n²) tokenization while still being reasonably accurate.
- Sentence ordering: sentences are added in their input order. For NIAH purposes, this is fine — we're not optimizing distractor relevance, just sizing.
- The Latin marker case (English haystack) uses Latin markers from `SCRIPT_MARKERS["Latn"]`. The runner (#030) joins the language → script lookup and passes the right marker.
- Returning a `Haystack` dataclass with audit fields lets the runner log "intended position 50%, actual 48.3%" → debuggable.

## Acceptance Criteria

- [ ] `build_haystack(sentences, target_tokens=500, ...)` produces a `Haystack` with `450 <= actual_tokens <= 600`.
- [ ] Marker is present in `h.text` exactly once.
- [ ] At `position_pct=0.05`, marker token position is in the first 15% of actual tokens.
- [ ] At `position_pct=0.95`, marker token position is in the last 15%.
- [ ] At `position_pct=0.5`, marker is within ±15% of midpoint.
- [ ] `position_pct=0.0` or `1.0` raises ValueError.
- [ ] Marker bigger than 25% of target_tokens raises ValueError ("too small").
- [ ] Empty sentence list raises ValueError.
- [ ] All 7 unit tests pass.
- [ ] `mypy --strict src/fertiscope/niah/haystack.py` passes.

## User Stories

### Story: Researcher builds a 64k Tamil haystack

1. Calls `build_haystack(tam_flores_sents, target_tokens=65536, tokenizer=cl100k_base, marker=tamil_marker, position_pct=0.5)`.
2. Returns Haystack with ~65k actual tokens, marker at ~32.5k token depth.
3. Sends to model, asks for recall.

### Story: Reproducibility check

1. Same input → same Haystack? Almost — sentences-list traversal order is deterministic, so the output is byte-stable given a fixed sentence order and tokenizer version.
2. Runner records `actual_tokens` and `marker_position_tokens` in the result CSV for audit.

### Story: Reviewer compares to Miles' v1

1. v1 used `len(text)//4` for sizing → marker at 50% by char count, actual token-depth varied wildly.
2. v2 uses real tokenizer → marker depth controlled to within ±5%.
3. Position-conditioned recall measurements are now meaningful.

---

Blocked by: #006, #012, #027
