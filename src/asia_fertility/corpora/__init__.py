"""Corpus registry — parallel-corpus loaders behind a uniform interface."""
from __future__ import annotations

from .base import ParallelCorpus, Sentence
from .exceptions import CorpusError, CorpusNotFound, CorpusUnavailable, LanguageNotInCorpus
from .registry import list_corpora, load_corpus, register

# Side-effect imports for registration
from . import custom as _custom  # noqa: F401,E402

try:
    from . import flores as _flores  # noqa: F401
except ImportError:
    pass

__all__ = [
    "Sentence",
    "ParallelCorpus",
    "register",
    "load_corpus",
    "list_corpora",
    "CorpusError",
    "CorpusNotFound",
    "CorpusUnavailable",
    "LanguageNotInCorpus",
]
