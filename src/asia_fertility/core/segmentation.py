"""Word segmentation per language."""
from __future__ import annotations

import logging
import re

from asia_fertility.languages import get_language

_log = logging.getLogger(__name__)

# Unicode word regex covering target scripts
_WORD_RE = re.compile(
    r"[\w\u0300-\u036f\u0900-\u097f\u0980-\u09ff\u0a00-\u0a7f"
    r"\u0b00-\u0b7f\u0b80-\u0bff\u0c00-\u0c7f\u0c80-\u0cff"
    r"\u0d00-\u0d7f\u0d80-\u0dff]+",
    re.UNICODE,
)


def _segment_icu(text: str, locale: str) -> int:
    try:
        from icu import BreakIterator, Locale  # type: ignore
    except ImportError:
        return len(_WORD_RE.findall(text))

    bi = BreakIterator.createWordInstance(Locale(locale))
    bi.setText(text)
    count = 0
    start = bi.first()
    end = bi.next()
    while end != BreakIterator.DONE:
        chunk = text[start:end]
        if any(c.isalpha() for c in chunk):
            count += 1
        start = end
        end = bi.next()
    return count


_ICU_LOCALES = {
    "eng": "en", "vie": "vi", "ind": "id", "zsm": "ms", "tgl": "tl",
    "hin": "hi", "ben": "bn", "sin": "si",
    "tam": "ta", "tel": "te", "kan": "kn", "mal": "ml",
}


def count_words(text: str, lang: str) -> int:
    """Return the word count for `text` in language `lang`."""
    if not text:
        return 0

    try:
        language = get_language(lang)
    except KeyError:
        return max(1, len(_WORD_RE.findall(text)))

    if language.spaceless:
        from .spaceless import segment_spaceless
        return segment_spaceless(text, lang)

    locale = _ICU_LOCALES.get(lang, "en")
    return max(1, _segment_icu(text, locale))


def has_icu() -> bool:
    try:
        import icu  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return False
