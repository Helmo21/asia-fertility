"""Spaceless segmentation: Thai, Khmer, Burmese, Lao."""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Callable

_log = logging.getLogger(__name__)

_THAI_RUN = re.compile(r"[\u0e00-\u0e7f]+", re.UNICODE)
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
def _thai() -> Callable[[str], int]:
    if _has_library("pythainlp"):
        from pythainlp.tokenize import word_tokenize  # type: ignore
        return lambda t: sum(1 for w in word_tokenize(t, engine="newmm") if w.strip())
    _log.warning("pythainlp not installed; Thai uses regex fallback (less accurate)")
    return lambda t: len(_THAI_RUN.findall(t))


@lru_cache(maxsize=1)
def _khmer() -> Callable[[str], int]:
    if _has_library("khmernltk"):
        from khmernltk import word_tokenize  # type: ignore
        return lambda t: sum(1 for w in word_tokenize(t) if w.strip())
    return lambda t: len(_KHMER_RUN.findall(t))


@lru_cache(maxsize=1)
def _burmese() -> Callable[[str], int]:
    return lambda t: len(_BURMESE_SYLL.findall(t))


@lru_cache(maxsize=1)
def _lao() -> Callable[[str], int]:
    if _has_library("laonlp"):
        from laonlp.tokenize import word_tokenize  # type: ignore
        return lambda t: sum(1 for w in word_tokenize(t) if w.strip())
    return lambda t: len(_LAO_RUN.findall(t))


_SEGMENTERS = {"tha": _thai, "khm": _khmer, "mya": _burmese, "lao": _lao}


def segment_spaceless(text: str, lang: str) -> int:
    if not text:
        return 0
    if lang not in _SEGMENTERS:
        raise ValueError(f"'{lang}' is not a spaceless language. Spaceless: {list(_SEGMENTERS)}")
    return max(1, _SEGMENTERS[lang]()(text))


def segmenter_in_use(lang: str) -> str:
    if lang == "tha":
        return "pythainlp" if _has_library("pythainlp") else "regex"
    if lang == "khm":
        return "khmer-nltk" if _has_library("khmernltk") else "regex"
    if lang == "mya":
        return "regex (no library available)"
    if lang == "lao":
        return "laonlp" if _has_library("laonlp") else "regex"
    raise ValueError(f"'{lang}' is not a spaceless language")
