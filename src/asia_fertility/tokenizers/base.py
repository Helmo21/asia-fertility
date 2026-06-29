"""Tokenizer protocol + TokenizerInfo dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Backend = Literal["tiktoken", "hf", "api"]
Family = Literal[
    "openai",
    "meta",
    "google",
    "mistral",
    "qwen",
    "deepseek",
    "bigscience",
    "cohere",
    "anthropic",
    "sarvam",
]


@dataclass(frozen=True)
class TokenizerInfo:
    id: str
    family: Family
    backend: Backend
    gated: bool = False
    extra: str | None = None
    notes: str = ""


@runtime_checkable
class Tokenizer(Protocol):
    info: TokenizerInfo

    def encode(self, text: str) -> list[int]: ...
    def count(self, text: str) -> int: ...


@runtime_checkable
class CountOnlyTokenizer(Protocol):
    info: TokenizerInfo

    def count(self, text: str) -> int: ...
