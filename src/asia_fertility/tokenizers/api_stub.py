"""Fallback stub for API count-only tokenizers when [api] extra is not installed."""
from __future__ import annotations

from .base import Tokenizer, TokenizerInfo
from .exceptions import TokenizerUnavailable
from .registry import register

_API_STUB_ROWS = [
    ("anthropic/claude", "anthropic"),
    ("google/gemini", "google"),
]


def _make_failing_loader(tid: str):
    def _load() -> Tokenizer:
        raise TokenizerUnavailable(tid, "missing extra 'api'")

    return _load


def register_all() -> None:
    for tid, family in _API_STUB_ROWS:
        info = TokenizerInfo(
            id=tid,
            family=family,  # type: ignore[arg-type]
            backend="api",
            gated=True,
            extra="api",
            notes="count-only; requires [api] extra",
        )
        register(info, _make_failing_loader(tid))


register_all()
