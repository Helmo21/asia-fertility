"""ParallelCorpus protocol + Sentence dataclass."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Sentence:
    id: str
    lang: str
    text: str
    meta: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class ParallelCorpus(Protocol):
    name: str
    languages: list[str]

    def iter_sentences(self, lang: str, limit: int | None = None) -> Iterator[Sentence]: ...
    def parallel_pairs(
        self, lang_a: str, lang_b: str, limit: int | None = None
    ) -> Iterator[tuple[Sentence, Sentence]]: ...
