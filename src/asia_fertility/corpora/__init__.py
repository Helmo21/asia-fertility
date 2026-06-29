"""Corpus registry — parallel-corpus loaders behind a uniform interface."""

from __future__ import annotations

import contextlib

# Side-effect imports for registration
from . import custom as _custom  # noqa: F401
from .base import ParallelCorpus, Sentence
from .exceptions import CorpusError, CorpusNotFound, CorpusUnavailable, LanguageNotInCorpus
from .registry import list_corpora, load_corpus, register

with contextlib.suppress(ImportError):
    from . import flores as _flores  # noqa: F401

__all__ = [
    "CorpusError",
    "CorpusNotFound",
    "CorpusUnavailable",
    "LanguageNotInCorpus",
    "ParallelCorpus",
    "Sentence",
    "list_corpora",
    "load_corpus",
    "register",
]
