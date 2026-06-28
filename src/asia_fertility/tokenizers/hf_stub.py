"""Fallback HF stub — registers TokenizerInfo rows that always fail with TokenizerUnavailable.

Used when `transformers` is not installed. Lets `list_tokenizers()` show the full
registry even without the [hf] extra.
"""
from __future__ import annotations

from .base import Tokenizer, TokenizerInfo
from .exceptions import TokenizerUnavailable
from .registry import register

_HF_STUB_ROWS = [
    ("meta/llama-3.1", "meta", True, "Llama-3.1 tokenizer (requires [hf] extra)"),
    ("mistral/tekken", "mistral", False, "Tekken tokenizer (requires [hf] extra)"),
    ("qwen/qwen3", "qwen", False, "Qwen3 tokenizer (requires [hf] extra)"),
    ("deepseek/v3", "deepseek", False, "DeepSeek v3 tokenizer (requires [hf] extra)"),
    ("bigscience/bloom", "bigscience", False, "BLOOM tokenizer (requires [hf] extra)"),
    ("cohere/aya-expanse", "cohere", True, "Aya Expanse tokenizer (requires [hf] extra)"),
    ("google/gemma-2", "google", True, "Gemma 2 tokenizer (requires [hf] extra)"),
]


def _make_failing_loader(tid: str):
    def _load() -> Tokenizer:
        raise TokenizerUnavailable(tid, "missing extra 'hf'")

    return _load


def register_all() -> None:
    for tid, family, gated, notes in _HF_STUB_ROWS:
        info = TokenizerInfo(
            id=tid,
            family=family,  # type: ignore[arg-type]
            backend="hf",
            gated=gated,
            extra="hf",
            notes=notes,
        )
        register(info, _make_failing_loader(tid))


register_all()
