"""Corpus registry."""

from __future__ import annotations

from collections.abc import Callable

from .base import ParallelCorpus
from .exceptions import CorpusNotFound, CorpusUnavailable

_CORPORA: dict[str, Callable[..., ParallelCorpus]] = {}


def register(name: str, loader: Callable[..., ParallelCorpus]) -> None:
    if name in _CORPORA:
        raise ValueError(f"Corpus '{name}' already registered")
    _CORPORA[name] = loader


def load_corpus(name: str, **kwargs) -> ParallelCorpus:
    if name not in _CORPORA:
        raise CorpusNotFound(f"Unknown corpus '{name}'. Registered: {sorted(_CORPORA)}")
    try:
        return _CORPORA[name](**kwargs)
    except ImportError as e:
        raise CorpusUnavailable(name, f"missing extra: {e}") from e


def list_corpora() -> list[str]:
    return sorted(_CORPORA)


def _reset_for_testing() -> None:
    _CORPORA.clear()
