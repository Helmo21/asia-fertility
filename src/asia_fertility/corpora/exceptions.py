"""Corpus exceptions."""

from __future__ import annotations


class CorpusError(Exception): ...


class CorpusNotFound(CorpusError): ...


class CorpusUnavailable(CorpusError):
    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Corpus '{name}' unavailable: {reason}")


class LanguageNotInCorpus(CorpusError): ...
