# Spaceless segmentation (Thai, Khmer, Burmese, Lao)

Status: pending
Tags: `segmentation`, `spaceless`, `thai`, `khmer`, `burmese`, `lao`, `pythainlp`
Depends on: #011, #016
Blocks: #019

## Scope

Word segmentation for the four scripts that don't use whitespace delimiters. Each uses a dedicated library when available, with a documented regex fallback for environments where the library isn't installable.

### Files to create

- `src/fertiscope/core/spaceless.py`
- `tests/unit/test_spaceless_thai.py`
- `tests/unit/test_spaceless_khmer.py`
- `tests/unit/test_spaceless_burmese.py`
- `tests/unit/test_spaceless_lao.py`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/core/spaceless.py`:

```python
"""Word segmentation for the four spaceless scripts.

Library-of-record (preferred) and regex fallback (documented degradation):

    Thai     → pythainlp                       fallback: Thai-character runs
    Khmer    → khmer-nltk (if installable)     fallback: Khmer-character runs
    Burmese  → simple syllable regex           (no robust library; documented)
    Lao      → Lao-character runs              (no robust library; documented)

Each segmenter logs a one-time WARNING when falling back.
"""
from __future__ import annotations
import logging
import re
from functools import lru_cache
from typing import Callable

_log = logging.getLogger(__name__)

# Unicode block patterns
_THAI_RUN  = re.compile(r"[\u0e00-\u0e7f]+", re.UNICODE)
_KHMER_RUN = re.compile(r"[\u1780-\u17ff]+", re.UNICODE)
_BURMESE_SYLL = re.compile(r"[\u1000-\u109f]+", re.UNICODE)
_LAO_RUN = re.compile(r"[\u0e80-\u0eff]+", re.UNICODE)


def _has_library(name: str) -> bool:
    import importlib
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def _thai_segmenter() -> Callable[[str], int]:
    if _has_library("pythainlp"):
        from pythainlp.tokenize import word_tokenize         # type: ignore
        return lambda t: sum(1 for w in word_tokenize(t, engine="newmm") if w.strip())
    _log.warning("pythainlp not installed; Thai segmentation uses regex fallback (less accurate)")
    return lambda t: len(_THAI_RUN.findall(t))


@lru_cache(maxsize=1)
def _khmer_segmenter() -> Callable[[str], int]:
    if _has_library("khmernltk"):
        from khmernltk import word_tokenize                   # type: ignore
        return lambda t: sum(1 for w in word_tokenize(t) if w.strip())
    _log.warning("khmer-nltk not installed; Khmer segmentation uses regex fallback")
    return lambda t: len(_KHMER_RUN.findall(t))


@lru_cache(maxsize=1)
def _burmese_segmenter() -> Callable[[str], int]:
    # No widely-installable library exists in 2026; document the regex as canonical.
    return lambda t: len(_BURMESE_SYLL.findall(t))


@lru_cache(maxsize=1)
def _lao_segmenter() -> Callable[[str], int]:
    if _has_library("laonlp"):
        from laonlp.tokenize import word_tokenize             # type: ignore
        return lambda t: sum(1 for w in word_tokenize(t) if w.strip())
    _log.debug("laonlp not installed; Lao segmentation uses regex fallback")
    return lambda t: len(_LAO_RUN.findall(t))


_SEGMENTERS = {
    "tha": _thai_segmenter,
    "khm": _khmer_segmenter,
    "mya": _burmese_segmenter,
    "lao": _lao_segmenter,
}


def segment_spaceless(text: str, lang: str) -> int:
    """Return the word/syllable count for spaceless text in `lang`."""
    if not text:
        return 0
    if lang not in _SEGMENTERS:
        raise ValueError(f"Language '{lang}' is not a spaceless script segmenter target. Spaceless: {list(_SEGMENTERS)}")
    segmenter = _SEGMENTERS[lang]()
    return max(1, segmenter(text))


def segmenter_in_use(lang: str) -> str:
    """For manifest provenance — returns 'pythainlp', 'regex', 'khmer-nltk', etc."""
    if lang == "tha":
        return "pythainlp" if _has_library("pythainlp") else "regex"
    if lang == "khm":
        return "khmer-nltk" if _has_library("khmernltk") else "regex"
    if lang == "mya":
        return "regex (no library available)"
    if lang == "lao":
        return "laonlp" if _has_library("laonlp") else "regex"
    raise ValueError(f"'{lang}' is not a spaceless language")
```

`tests/unit/test_spaceless_thai.py`:

```python
import pytest
from fertiscope.core.spaceless import segment_spaceless, segmenter_in_use

def test_thai_short_string():
    # "สวัสดีชาวโลก" = "hello world" (5 syllables / ~2 words depending on segmenter)
    count = segment_spaceless("สวัสดีชาวโลก", "tha")
    assert count >= 1

def test_thai_empty():
    assert segment_spaceless("", "tha") == 0

def test_thai_segmenter_reported():
    s = segmenter_in_use("tha")
    assert s in {"pythainlp", "regex"}

@pytest.mark.skipif(segmenter_in_use("tha") != "pythainlp", reason="needs pythainlp")
def test_thai_pythainlp_accurate():
    # pythainlp newmm should return 2 for "สวัสดี ชาวโลก" with space
    assert segment_spaceless("สวัสดี ชาวโลก", "tha") == 2
```

`tests/unit/test_spaceless_khmer.py`, `test_spaceless_burmese.py`, `test_spaceless_lao.py`: same pattern. Burmese has no library skipif (regex is the official path).

### Notes

- **Burmese has no widely-installable library in 2026**: `myanmar-tools` is Google's heuristic library, not stable for word segmentation. The regex syllable count is the documented canonical path. Disclose in `docs/methodology.md`.
- **pythainlp `newmm` engine** is the best balance of speed and quality for Thai. Pin `pythainlp>=5.0` in `[hf]` extras.
- **khmer-nltk** has unstable releases — falls back to regex gracefully.
- **laonlp** is small but works; pin if you want CI to install it.
- Segmenter calls are `lru_cache`d so the import happens once per process.
- The `segmenter_in_use` function is consumed by the manifest builder (#025) so every run records which segmenter computed its word counts.

## Acceptance Criteria

- [ ] `segment_spaceless("สวัสดีชาวโลก", "tha") >= 1`.
- [ ] `segment_spaceless("មិនមានបញ្ហា", "khm") >= 1`.
- [ ] `segment_spaceless("မင်္ဂလာပါ", "mya") >= 1`.
- [ ] `segment_spaceless("ສະບາຍດີ", "lao") >= 1`.
- [ ] `segment_spaceless("", "tha") == 0`.
- [ ] `segment_spaceless("foo", "eng")` raises `ValueError`.
- [ ] `segmenter_in_use("tha")` returns `"pythainlp"` when pythainlp is installed, `"regex"` otherwise.
- [ ] `count_words` from #016 routes Thai input to this module without circular import.
- [ ] All 4 test modules pass (with appropriate skipif markers when libraries missing).
- [ ] Fallback WARNING is logged exactly once per language per process (verify with caplog).
- [ ] `mypy --strict src/fertiscope/core/spaceless.py` passes.

## User Stories

### Story: Tamil fertility comes out right because Burmese fertility comes out right

1. User runs the study on all 16 languages.
2. Burmese row uses the regex segmenter; manifest records `segmenter="regex (no library available)"`.
3. The number ~10 tokens/syllable for Burmese matches the paper.
4. Reviewer reads manifest, understands the choice.

### Story: Thai user with pythainlp

1. Installs `pip install fertiscope[hf]`.
2. Runs Thai measurement.
3. pythainlp's `newmm` engine produces 2 words for "สวัสดี ชาวโลก".
4. Manifest records `segmenter="pythainlp"`.

### Story: CI without spaceless libraries

1. CI uses minimum install.
2. Thai test passes via regex fallback.
3. One WARNING in test output: "pythainlp not installed; Thai segmentation uses regex fallback".
4. Test still passes — just less accurate.

---

Blocked by: #011, #016
