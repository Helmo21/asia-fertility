"""tiktoken adapter — OpenAI o200k_base, o200k_harmony, cl100k_base."""

from __future__ import annotations

from .base import Tokenizer, TokenizerInfo
from .exceptions import TokenizerUnavailable
from .registry import register

_TIKTOKEN_ENCODINGS: dict[str, tuple[str, TokenizerInfo]] = {
    "openai/o200k_base": (
        "o200k_base",
        TokenizerInfo(
            id="openai/o200k_base",
            family="openai",
            backend="tiktoken",
            gated=False,
            extra="oai",
            notes="GPT-4o, GPT-4.1, o-series, GPT-5",
        ),
    ),
    "openai/cl100k_base": (
        "cl100k_base",
        TokenizerInfo(
            id="openai/cl100k_base",
            family="openai",
            backend="tiktoken",
            gated=False,
            extra="oai",
            notes="GPT-3.5, GPT-4 (legacy)",
        ),
    ),
    "openai/o200k_harmony": (
        "o200k_harmony",
        TokenizerInfo(
            id="openai/o200k_harmony",
            family="openai",
            backend="tiktoken",
            gated=False,
            extra="oai",
            notes="gpt-oss open-weight family",
        ),
    ),
}


class TiktokenTokenizer:
    def __init__(self, info: TokenizerInfo, encoding_name: str) -> None:
        try:
            import tiktoken
        except ImportError as e:
            raise TokenizerUnavailable(info.id, f"missing extra 'oai': {e}") from e
        self.info = info
        try:
            self._enc = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            raise TokenizerUnavailable(
                info.id, f"tiktoken encoding '{encoding_name}' unavailable: {e}"
            ) from e

    def encode(self, text: str) -> list[int]:
        return self._enc.encode(text)

    def count(self, text: str) -> int:
        return len(self._enc.encode(text))


def _make_loader(info: TokenizerInfo, encoding_name: str):
    def _load() -> Tokenizer:
        return TiktokenTokenizer(info, encoding_name)

    return _load


def register_all() -> None:
    for _, (enc_name, info) in _TIKTOKEN_ENCODINGS.items():
        register(info, _make_loader(info, enc_name))


register_all()
