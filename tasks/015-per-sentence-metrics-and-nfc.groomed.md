# Per-sentence metrics + NFC normalization

Status: pending
Tags: `metrics`, `nfc`, `unicode`, `per-sentence`, `core`
Depends on: #006, #010
Blocks: #018, #019

## Scope

The atomic measurement unit: given a `Sentence` and a `Tokenizer`, produce a `PerSentenceMetrics` record with `tokens`, `words`, `chars`, `bytes_`. Words count is deferred to #016/#017 (segmentation) — this task uses a placeholder (whitespace split) so the pipeline compiles end-to-end. NFC normalization is applied before tokenization.

### Files to create

- `src/fertiscope/core/__init__.py`
- `src/fertiscope/core/normalize.py`
- `src/fertiscope/core/metrics.py`
- `tests/unit/test_normalize.py`
- `tests/unit/test_metrics_per_sentence.py`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/core/normalize.py`:

```python
"""Unicode normalization for all measurement paths.

We apply NFC (canonical composition) before tokenization so that user input
with decomposed accents (e.g. 'é' as 'e' + combining acute) matches the canonical
form most tokenizer vocabularies were trained on. This is the same convention
afri-fertility uses.
"""
from __future__ import annotations
import unicodedata

def nfc(text: str) -> str:
    """Return NFC-normalized text."""
    return unicodedata.normalize("NFC", text)

def is_nfc(text: str) -> bool:
    return unicodedata.is_normalized("NFC", text)
```

`src/fertiscope/core/metrics.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from fertiscope.corpora import Sentence
from fertiscope.tokenizers.base import Tokenizer
from fertiscope.core.normalize import nfc


@dataclass(frozen=True)
class PerSentenceMetrics:
    sentence_id: str
    lang: str
    tokenizer_id: str
    tokens: int
    words: int
    chars: int       # unicode codepoint count (after NFC)
    bytes_: int      # UTF-8 byte count (after NFC)


def per_sentence(sentence: Sentence, tokenizer: Tokenizer, *, segmenter=None) -> PerSentenceMetrics:
    """Compute per-sentence metrics for a single (sentence, tokenizer) pair.

    Args:
        sentence: a Sentence from any corpus.
        tokenizer: a registered Tokenizer (real or count-only).
        segmenter: optional callable (text, lang) -> word_count. Defaults to
            whitespace split (PLACEHOLDER — replaced by #016/#017's real
            segmenter once landed). Counting words on spaceless scripts
            without the real segmenter produces incorrect output; we do NOT
            warn here because the segmenter parameter is wired up properly
            in #019.

    Returns:
        PerSentenceMetrics record.
    """
    normalized = nfc(sentence.text)
    tokens = tokenizer.count(normalized)

    if segmenter is None:
        # PLACEHOLDER: whitespace split. Replaced in #019.
        words = max(1, len(normalized.split()))
    else:
        words = max(1, segmenter(normalized, sentence.lang))

    chars = len(normalized)
    bytes_ = len(normalized.encode("utf-8"))

    return PerSentenceMetrics(
        sentence_id=sentence.id,
        lang=sentence.lang,
        tokenizer_id=tokenizer.info.id,
        tokens=tokens,
        words=words,
        chars=chars,
        bytes_=bytes_,
    )
```

`src/fertiscope/core/__init__.py`:

```python
from .normalize import nfc, is_nfc
from .metrics import PerSentenceMetrics, per_sentence

__all__ = ["nfc", "is_nfc", "PerSentenceMetrics", "per_sentence"]
```

`tests/unit/test_normalize.py`:

```python
import pytest
from fertiscope.core.normalize import nfc, is_nfc

def test_nfc_idempotent():
    assert nfc("hello") == "hello"
    assert nfc(nfc("café")) == nfc("café")

def test_nfc_composes_decomposed():
    decomposed = "cafe\u0301"   # e + combining acute
    composed   = "café"          # precomposed é
    assert nfc(decomposed) == composed
    assert is_nfc(composed)
    assert not is_nfc(decomposed)

def test_nfc_vietnamese_diacritics():
    # Vietnamese has tone marks that may be decomposed
    decomposed = "tie\u0301ng Vie\u0323\u0302t"
    composed = nfc(decomposed)
    assert is_nfc(composed)
    assert len(composed) < len(decomposed)   # composed is shorter

def test_nfc_empty_string():
    assert nfc("") == ""
```

`tests/unit/test_metrics_per_sentence.py`:

```python
from fertiscope.corpora import Sentence
from fertiscope.core import per_sentence, PerSentenceMetrics

class FakeTok:
    info = type("I", (), {"id": "fake/tok"})()
    def count(self, t: str) -> int:
        return len(t) // 4 + 1
    def encode(self, t: str) -> list[int]:
        return list(range(self.count(t)))

def test_per_sentence_basic():
    s = Sentence(id="t:1", lang="eng", text="hello world")
    m = per_sentence(s, FakeTok())
    assert isinstance(m, PerSentenceMetrics)
    assert m.sentence_id == "t:1"
    assert m.lang == "eng"
    assert m.tokenizer_id == "fake/tok"
    assert m.tokens == FakeTok().count("hello world")
    assert m.words == 2
    assert m.chars == 11
    assert m.bytes_ == 11   # ASCII = 1 byte/char

def test_per_sentence_nfc_applied():
    decomposed = "cafe\u0301"
    s = Sentence(id="x", lang="fra", text=decomposed)
    m = per_sentence(s, FakeTok())
    # chars after NFC is 4, not 5
    assert m.chars == 4

def test_per_sentence_utf8_bytes_for_tamil():
    # Each Tamil character is 3 UTF-8 bytes
    s = Sentence(id="x", lang="tam", text="தமிழ்")    # 5 chars
    m = per_sentence(s, FakeTok())
    assert m.chars == 5
    assert m.bytes_ == len("தமிழ்".encode("utf-8"))   # typically 14-15 bytes

def test_per_sentence_custom_segmenter():
    def seg(text, lang):
        return 99   # deliberately bonkers
    s = Sentence(id="x", lang="vie", text="hello")
    m = per_sentence(s, FakeTok(), segmenter=seg)
    assert m.words == 99

def test_per_sentence_min_one_word():
    """Empty-words segmenter falls back to 1 to avoid div-by-zero downstream."""
    def seg(t, l): return 0
    s = Sentence(id="x", lang="vie", text="foo")
    m = per_sentence(s, FakeTok(), segmenter=seg)
    assert m.words == 1
```

### Notes

- **NFC is applied EVERYWHERE** — at the tokenizer boundary and at the segmenter boundary. The metric chars/bytes counts are of the NFC form, not the input form.
- The whitespace-split placeholder is intentional: it lets every later task compile and write meaningful tests *before* #016/#017 land. Once segmentation arrives, the placeholder is never used because every measure path passes `segmenter=`.
- `max(1, words)` prevents division-by-zero in aggregation (fertility = tokens/words). For spaceless scripts where the whitespace placeholder would return 1 (single "word"), the fertility number is meaningless but the pipeline still produces a row. The honest output happens in #017 when real segmentation lands.
- `chars` is **Unicode codepoint count** (`len(str)`). Cluster-aware char counting would be more accurate for Indic scripts, but codepoint count is what afri-fertility uses for CPT — match them.
- `bytes_` underscore suffix avoids shadowing the builtin `bytes`.

## Acceptance Criteria

- [ ] `from fertiscope.core import nfc, PerSentenceMetrics, per_sentence` works.
- [ ] `PerSentenceMetrics` is frozen (dataclass `frozen=True`).
- [ ] `per_sentence` applies NFC before counting (decomposed `cafe\u0301` becomes `café` of 4 chars).
- [ ] Tamil sentence (5 chars) → `bytes_ == 14-15` (3 bytes/char for Tamil Brahmic).
- [ ] Custom segmenter callable is honored.
- [ ] Empty-or-zero word count falls back to 1.
- [ ] All 9 unit tests pass.
- [ ] `mypy --strict src/fertiscope/core/` passes.
- [ ] No use of `numpy` in this module (keep base deps minimal — numpy is for aggregation only).

## User Stories

### Story: Implementer wires #016 segmenter without breaking #015

1. #016 lands `count_words(text, lang)`.
2. Caller does `per_sentence(s, tok, segmenter=count_words)`.
3. Real word count replaces placeholder. #015 logic untouched.

### Story: Reviewer asks "do you normalize?"

1. Reviewer: "What if my user input is decomposed?"
2. Answer: "We NFC-normalize before tokenizing — see `core/normalize.py:nfc()`."
3. Reviewer satisfied.

### Story: BPT calculation chain begins

1. `per_sentence` returns `bytes_`.
2. Aggregation (#018) sums bytes and tokens.
3. BPT = sum(bytes) / sum(tokens).
4. Cross-script-fair metric is now achievable.

---

Blocked by: #006, #010
