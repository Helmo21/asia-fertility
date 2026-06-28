"""Word segmentation per language. Fertility = tokens / words, so 'word' has to be defined."""

from __future__ import annotations

import re
from typing import List


# English: punctuation-stripped whitespace split. Good enough for fertility math.
_EN_TOKEN_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


def segment_en(text: str) -> List[str]:
    """Segment English text into words. Strips punctuation."""
    return _EN_TOKEN_RE.findall(text)


def segment_vi(text: str) -> List[str]:
    """Segment Vietnamese text into words using underthesea.

    underthesea handles multi-syllable Vietnamese words correctly:
      "Việt Nam" -> 1 word (not 2)
      "Hồ Chí Minh" -> 1 word (not 3)
    This is critical for honest fertility numbers - a naive whitespace split
    over-counts words and under-reports fertility ratio.
    """
    from underthesea import word_tokenize

    words = word_tokenize(text)
    # Drop pure-punctuation tokens to keep the metric comparable to English.
    return [w for w in words if re.search(r"[\w]", w, re.UNICODE)]


def count_words(text: str, lang: str) -> int:
    """Word count for a given (text, language) pair."""
    if lang == "en":
        return len(segment_en(text))
    if lang == "vi":
        return len(segment_vi(text))
    raise ValueError(f"v0.1 supports only 'en' and 'vi'; got {lang!r}")
