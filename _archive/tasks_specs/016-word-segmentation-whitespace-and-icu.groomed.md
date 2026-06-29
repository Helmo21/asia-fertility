# Word segmentation: whitespace + ICU for non-spaceless scripts

Status: pending
Tags: `segmentation`, `icu`, `intl-segmenter`, `unicode`
Depends on: #011, #015
Blocks: #019

## Scope

Wire word-boundary segmentation for the 12 non-spaceless target languages using ICU (the Python equivalent of JS `Intl.Segmenter`). Falls back to regex if `pyicu`/`icu-tokenizer` is unavailable. Spaceless scripts (Thai, Khmer, Burmese, Lao) are handled in #017.

### Files to create

- `src/fertiscope/core/segmentation.py`
- `tests/unit/test_segmentation_whitespace.py`
- `tests/unit/test_segmentation_icu.py`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/core/segmentation.py`:

```python
"""Word-boundary segmentation per language.

Two paths:
1. NON-SPACELESS scripts (Latin, Devanagari, Bengali, Sinhala, Tamil, Telugu,
   Kannada, Malayalam): ICU BreakIterator (mirror of JS Intl.Segmenter). Falls
   back to a Unicode-aware regex if ICU is unavailable.

2. SPACELESS scripts (Thai, Khmer, Burmese, Lao): handled in #017's
   spaceless module. This file delegates via `_spaceless_segment`.
"""
from __future__ import annotations
import logging
import re
from typing import Callable

from fertiscope.languages import get_language

_log = logging.getLogger(__name__)

# Unicode-aware word regex: matches sequences of letters + marks + numbers.
# Excludes punctuation and whitespace.
_WORD_RE = re.compile(r"[\w\u0300-\u036f\u0900-\u097f\u0980-\u09ff\u0a00-\u0a7f\u0b00-\u0b7f\u0b80-\u0bff\u0c00-\u0c7f\u0c80-\u0cff\u0d00-\u0d7f\u0d80-\u0dff]+", re.UNICODE)


def _segment_icu(text: str, locale: str) -> int:
    """Use ICU BreakIterator if available; else regex fallback."""
    try:
        from icu import BreakIterator, Locale            # type: ignore
    except ImportError:
        _log.debug("pyicu not available; using regex fallback")
        return len(_WORD_RE.findall(text))

    bi = BreakIterator.createWordInstance(Locale(locale))
    bi.setText(text)
    count = 0
    start = bi.first()
    end = bi.next()
    while end != BreakIterator.DONE:
        chunk = text[start:end]
        # ICU breaks include whitespace runs — only count chunks that have a letter
        if any(c.isalpha() for c in chunk):
            count += 1
        start = end
        end = bi.next()
    return count


# Mapping from ISO 639-3 to ICU locale id
_ICU_LOCALES = {
    "eng": "en", "vie": "vi", "ind": "id", "zsm": "ms", "tgl": "tl",
    "hin": "hi", "ben": "bn", "sin": "si",
    "tam": "ta", "tel": "te", "kan": "kn", "mal": "ml",
}


def count_words(text: str, lang: str) -> int:
    """Return the word count for `text` in language `lang`.

    Routes to the correct segmenter:
    - Spaceless (Thai/Khmer/Burmese/Lao) → #017's segmenters
    - Non-spaceless → ICU (with regex fallback)
    """
    if not text:
        return 0

    try:
        language = get_language(lang)
    except KeyError:
        # Unknown lang — best-effort whitespace + regex
        return max(1, len(_WORD_RE.findall(text)))

    if language.spaceless:
        from fertiscope.core.spaceless import segment_spaceless   # implemented in #017
        return segment_spaceless(text, lang)

    locale = _ICU_LOCALES.get(lang, "en")
    return max(1, _segment_icu(text, locale))


def has_icu() -> bool:
    """Diagnostic — is pyicu installed?"""
    try:
        import icu                                # type: ignore # noqa: F401
        return True
    except ImportError:
        return False
```

`tests/unit/test_segmentation_whitespace.py`:

```python
import pytest
from fertiscope.core.segmentation import count_words

def test_english_simple():
    assert count_words("hello world", "eng") == 2

def test_english_punctuation():
    assert count_words("Hello, world!", "eng") == 2

def test_vietnamese_diacritics():
    # 'tiếng Việt' should count as 2 words in the simple ICU segmenter
    assert count_words("tiếng Việt", "vie") == 2

def test_empty_string():
    assert count_words("", "eng") == 0

def test_unknown_lang_fallback():
    assert count_words("hello world", "xyz") == 2

def test_min_one_word():
    # Even with no whitespace, return >= 1 for non-empty text
    assert count_words("helloworld", "eng") >= 1
```

`tests/unit/test_segmentation_icu.py`:

```python
import pytest
from fertiscope.core.segmentation import count_words, has_icu

pytestmark = pytest.mark.skipif(not has_icu(), reason="pyicu not installed")

def test_tamil_short():
    # தமிழ் ஒரு செம்மொழி = "Tamil is a classical language", 3 words
    assert count_words("தமிழ் ஒரு செம்மொழி", "tam") == 3

def test_hindi_short():
    assert count_words("नमस्ते दुनिया", "hin") == 2

def test_bengali_short():
    assert count_words("বাংলা ভাষা", "ben") == 2

def test_malayalam_short():
    assert count_words("നമസ്കാരം ലോകം", "mal") == 2
```

### Notes

- **`pyicu` install is platform-specific.** macOS: `brew install icu4c && PATH="/opt/homebrew/opt/icu4c/bin:$PATH" pip install pyicu`. Linux: `apt install libicu-dev && pip install pyicu`. Document in `docs/methodology.md` (#037).
- The regex fallback is **not Unicode-perfect** — it groups some clusters incorrectly for complex scripts. Document this honestly: "pyicu provides higher accuracy; regex fallback yields a usable approximation".
- `Intl.Segmenter` from JS maps to `BreakIterator.createWordInstance` from ICU — they share the underlying ICU library. Match the JS analyzer's behavior closely.
- The `_WORD_RE` includes Unicode ranges for the target scripts so the regex fallback doesn't lose Indic/SE-Asian letters in greedy alphanumeric matching.
- `has_icu()` is exposed so the CLI and study runner can record whether the ICU path was used → reproducibility.

## Acceptance Criteria

- [ ] `from fertiscope.core.segmentation import count_words` works.
- [ ] English "hello world" → 2 words (works regardless of ICU availability).
- [ ] Tamil "தமிழ் ஒரு செம்மொழி" → 3 words (ICU required for accuracy).
- [ ] Empty string → 0 words.
- [ ] Non-empty unknown-language input → ≥ 1 word.
- [ ] Vietnamese "tiếng Việt" → 2 words.
- [ ] `has_icu()` returns the correct boolean.
- [ ] Without `pyicu`: the ICU-marked tests are SKIPPED (not failed); whitespace tests still pass.
- [ ] All 6 whitespace tests + 4 ICU tests pass (10 total when ICU available).
- [ ] `mypy --strict src/fertiscope/core/segmentation.py` passes.

## User Stories

### Story: Researcher with full ICU install

1. Installs `pip install fertiscope[hf]` (transitively pulls pyicu via system check).
2. `count_words("தமிழ் ஒரு செம்மொழி", "tam")` returns 3.
3. Fertility numbers match published references.

### Story: User on a constrained system

1. Cannot install `pyicu` (build deps blocked).
2. `count_words("தமிழ் ஒரு செம்மொழி", "tam")` returns 3 via regex fallback.
3. Possibly drifts by ±1 on edge cases; warning logged once.
4. Study runner records `segmenter=regex_fallback` in manifest.

### Story: JS analyzer parity check

1. The Next.js web app uses `Intl.Segmenter({granularity:'word'})`.
2. The Python package uses ICU `BreakIterator.createWordInstance`.
3. Both produce the same word counts for the same text. Critical for cross-tool consistency.

---

Blocked by: #011, #015
